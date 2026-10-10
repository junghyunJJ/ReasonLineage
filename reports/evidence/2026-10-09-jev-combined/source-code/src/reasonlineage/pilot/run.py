"""Isolated pilot runs; preserve the default engine and selection rules."""

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from ..core.state import EvolutionState, seeds_per_model
from ..checks.gate import Gate
from ..checks.calibration import validate_certificate
from ..diagnose.j2 import run_j2
from ..engine import answer as fmt
from ..engine.calls import CallRecorder
from ..engine.config import RunOptions, Task
from ..engine.errors import RunStopped
from ..engine.events import EventLog, read_events
from ..engine.runner import Runner, Written, WritingFailed, JudgeScore, gather_all
from ..protocol import load_protocol
from .budget import Budget, MeteredBackend, public_data
from .checker import MeteredChecker, CheckerVersionMismatch


def save_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


class PilotRunner(Runner):
    initial = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        pilot = self.protocol.data.get('pilot', {})
        for name in ('initial_population', 'population_limit', 'survivor_count'):
            if name in pilot and (not isinstance(pilot[name], int) or isinstance(pilot[name], bool)):
                raise ValueError(f'pilot {name} must be an integer')
        initial = pilot.get('initial_population')
        population = pilot.get('population_limit', initial)
        if population is not None or 'survivor_count' in pilot:
            population = self.config.population_limit if population is None else population
            self.config = replace(self.config, population_limit=population,
                                  survivor_count=pilot.get('survivor_count', population - 2))
        self.initial_candidate_count = (initial if initial is not None else
                                        len(self.names) * seeds_per_model(len(self.names)))
        if not self.config.survivor_count < self.initial_candidate_count <= self.config.population_limit:
            raise ValueError('pilot initial_population must exceed survivor_count and fit population_limit')
        if self.config.new_candidate_slots != 2:
            raise ValueError('pilot requires two offspring slots for mutation and crossover')

    async def _generation_zero(self):
        population = self.protocol.data.get('pilot', {}).get('initial_population')
        if population is None:
            return await super()._generation_zero()
        offset = 0 if self.task.id == 'als' else 1
        jobs = [(self._new_id(), self.names[(i + offset) % len(self.names)]) for i in range(population)]
        written = await gather_all(self._write_or_substitute(0, 'write', cid, actor, self._seed_prompt(None))
                                  for cid, actor in jobs)
        return EvolutionState(self.config, [self._record_candidate(cid, w, 'seed', (), 0)
                                           for (cid, _), w in zip(jobs, written)])

    async def _write(self, gen, role, cid, author, prompt):
        name = f'g{gen}/{role}/{cid}/{author}'
        data = await self._author_call(name, author, prompt)
        versions = [name]
        anomalies = self._validate_proposal(cid, data)
        if self.gate is not None:
            decision = await self.gate(cid, gen, author, data, 0)
            if decision.rewrite:
                again = f'g{gen}/rewrite/{cid}/{author}'
                data = await self._author_call(again, author, self.protocol.render(
                    'rewrite', question=self.task.question, answer=fmt.render_for_judge(data),
                    reasons='\n'.join('- ' + reason for reason in decision.reasons)))
                versions.append(again)
                anomalies.extend(self._validate_proposal(cid, data))
                await self.gate(cid, gen, author, data, 1)
        return Written(author, data, versions, anomalies)

    def _validate_proposal(self, cid, data):
        issues = fmt.validate_answer(data, None)
        if issues.hard or len(data['ranking']) != 1 or not data['answer'].strip():
            raise WritingFailed('invalid one-hypothesis output')
        low, high = self.protocol.answer_words
        anomalies = []
        if not low <= len(data['answer'].split()) <= high:
            if self.protocol.data['answer'].get('length_enforcement', 'strict') != 'warn':
                raise WritingFailed('proposal outside the agreed 400–800 word range')
            anomalies.append({'kind': 'answer_length', 'candidate': cid,
                              'detail': {'words': len(data['answer'].split()), 'target': [low, high]},
                              'action': 'kept valid hypothesis; length is advisory'})
        if issues.soft:
            anomalies.append({'kind': 'prose_mention', 'candidate': cid,
                              'detail': list(issues.soft), 'action': 'proceed without repair'})
        return anomalies

    def _remember_initial(self, state):
        if state.generation == 0:
            best = state.best
            self.initial = {'id': best.id, 'author': best.author, 'fitness': best.fitness,
                            'scores': best.scores, 'answer': self.answers[best.id]}
            self.events.emit('pilot.initial', **self.initial)

    async def _score(self, state):
        await super()._score(state)
        self._remember_initial(state)

    def _parse_judge(self, judge, data):
        advisory = self.protocol.data.get('pilot', {}).get('critique_count_enforcement') == 'warn'
        points = data.get('critique') if isinstance(data, dict) else None
        if (advisory and isinstance(points, list) and len(points) > 3
                and all(isinstance(point, str) and point.strip() for point in points)):
            # Validate every score with the unchanged parser, then retain every public point.
            score = super()._parse_judge(judge, {**data, 'critique': points[:3]})
            return replace(score, critique=tuple(points))
        return super()._parse_judge(judge, data)

    async def _judge(self, gen, candidate, judge, trace):
        score = await super()._judge(gen, candidate, judge, trace)
        if isinstance(score, JudgeScore) and len(score.critique) > 3:
            self.events.emit('anomaly', kind='critique_count', candidate=candidate.id,
                             detail={'count': len(score.critique), 'target': [1, 3]},
                             action='kept all valid public critique points')
        return score


class SoloRunner(PilotRunner):
    async def _generation_zero(self):
        actor = self.names[0]
        jobs = [(self._new_id(), actor) for _ in range(self.initial_candidate_count)]
        written = await gather_all(self._write_or_substitute(0, 'write', cid, actor, self._seed_prompt(None))
                                   for cid, actor in jobs)
        seeds = [self._record_candidate(cid, w, 'seed', (), 0) for (cid, _), w in zip(jobs, written)]
        return EvolutionState(self.config, seeds)

    async def _offspring(self, state):
        jobs = [(self._new_id(), parent) for parent in state.population]
        written = await gather_all(self._write_or_substitute(state.generation, 'mutate', cid, parent.author,
                                                            self._mutate_prompt(parent)) for cid, parent in jobs)
        for (cid, parent), proposal in zip(jobs, written):
            state.register(self._record_candidate(cid, proposal, 'mutation', (parent.id,), state.generation))
        state.start_scoring()

    async def _score(self, state):
        # Distinct names create fresh requests, seeds and records for every critic.
        actor = self.names[0]
        count = self.protocol.data.get('pilot', {}).get('self_critics', 3)
        judges = [f'{actor}-r{i}' for i in range(count)]
        for judge in judges:
            self.members[judge] = self.members[actor]
            self.backends[judge] = self.backends[actor]
        pending = list(state.pending)
        jobs = [(candidate, judge) for candidate in pending for judge in judges]
        scores = await gather_all(self._judge(state.generation, candidate, judge, '') for candidate, judge in jobs)
        panels = {c.id: [] for c in pending}
        for (candidate, judge), score in zip(jobs, scores):
            panels[candidate.id].append(score)
            self.events.emit('judge.scored', candidate=candidate.id, judge=judge, author=actor,
                             generation=state.generation, judges_axis='fresh_self_critic', context='isolated',
                             scores=dict(score.scores), critique=list(score.critique))
        for candidate in pending:
            scored = state.record_score(candidate.id, panels[candidate.id])
            self.events.emit('candidate.scored', candidate=candidate.id, judges=judges,
                             scores=scored.scores, fitness=scored.fitness)
        self._remember_initial(state)


async def run_case(run_dir, case, method, setup, services, shared, *, root, seconds=1200, tokens=400000,
                   protocol_directory='protocol', checker=None):
    if case not in ('als', 'aml') or method not in ('reasonlineage', 'gpt', 'opus', 'grok', 'glm'):
        raise ValueError('unknown pilot case or method')
    run_dir, root = Path(run_dir), Path(root)
    run_dir.mkdir(parents=True, exist_ok=False)
    evidence = (root / f'research/co-scientist-pilot/{case}-evidence.md').read_bytes()
    protocol = load_protocol(root / 'research/co-scientist-pilot' / protocol_directory)
    if protocol.j1['enforce']:
        if checker is None:
            raise ValueError('an enforced pilot requires a checker')
        validate_certificate(protocol)
    members = setup.panel if method == 'reasonlineage' else tuple(m for m in setup.panel if m.name == method)
    policy = protocol.data.get('pilot', {})
    if len(members) != (policy.get('panel_size', 4) if method == 'reasonlineage' else 1):
        raise ValueError('pilot requires the configured model roster')
    local = Budget(seconds=seconds, tokens=tokens, calls=policy.get('call_limit', 40), lazy=True)
    checker_budget = Budget(seconds=seconds, tokens=None, calls=policy.get('checker_call_limit', 50), lazy=True)
    checked = MeteredChecker(checker, checker_budget, shared, local, run_dir) if checker is not None else None
    backends = {m.name: MeteredBackend(services[m.name], local, shared, concurrency=setup.concurrency) for m in members}
    header = {'case': case, 'method': method, 'evidence_sha256': hashlib.sha256(evidence).hexdigest(),
              'protocol_sha256': protocol.hash, 'protocol_version': protocol.version,
              'models': [{'name': m.name, 'model': m.model, 'effort': m.effort} for m in members],
              'options': RunOptions().to_dict(), 'budgets': local.snapshot()}
    save_json(run_dir / 'header.json', header)
    task = Task(case, evidence.decode('utf-8'), None, 'biomedical', 'public')
    events = EventLog(run_dir / 'events.jsonl')
    format_retry = policy.get('format_retry', False)
    recorder = CallRecorder(run_dir, events, run_seed=policy.get('run_seed', 20261005),
                            attempts=2 if format_retry else 1, retry_backend_errors=False,
                            unusable_sanitizer=public_data if format_retry else None)
    runner_type = PilotRunner if method == 'reasonlineage' else SoloRunner
    runner = runner_type(run_dir=run_dir, run_id=f'{case}-{method}', task=task, members=members,
                         backends=backends, protocol=protocol, options=RunOptions(), events=events, recorder=recorder,
                         gate=Gate(run_dir, checked, protocol, task.question, 'experiment') if checked else None)
    if checked:
        header['checker'] = {'name': checked.name, 'version': checked.pinned_version,
                             'j1_enforce': bool(protocol.j1['enforce']), 'thresholds': dict(protocol.j1['thresholds'])}
    header['evolution'] = {'initial_candidates': runner.initial_candidate_count,
                           'population_limit': runner.config.population_limit,
                           'survivor_count': runner.config.survivor_count,
                           'generations': runner.config.generation_limit}
    save_json(run_dir / 'header.json', header)
    outcome = {'header': header}
    cancelled = False
    fatal_checker_error = None
    try:
        result = await runner.run()
        outcome.update(status='completed', final=result['best'])
    except RunStopped as error:
        outcome.update(status='failed', reason=str(error))
        if isinstance(error, CheckerVersionMismatch):
            fatal_checker_error = error
    except asyncio.CancelledError:
        cancelled = True
        events.stop('cancelled at study deadline or signal')
        outcome.update(status='cutoff', reason='study deadline or signal')
    if runner.initial is not None:
        outcome['initial'] = runner.initial
    outcome['usage'] = local.snapshot()
    if checked:
        checks = read_events(run_dir / 'checks.jsonl')
        outcome['j1'] = {'status': 'unstarted' if not checks else
                        'partial' if any(r.get('error') or r.get('needs_review') for r in checks) else 'completed',
                        'unique_checks': len(checks), 'failed_checks': sum(bool(r.get('error')) for r in checks),
                        'needs_review': sum(bool(r.get('needs_review')) for r in checks),
                        'remaining_defects': sum(r['attempt'] == 1 and r['would_rewrite'] for r in checks)}
    save_json(run_dir / 'status.json', outcome)
    if fatal_checker_error is not None:
        outcome['checker_usage'] = checker_budget.snapshot()
        outcome['fatal_checker_error'] = 'version_mismatch'
        save_json(run_dir / 'status.json', outcome)
        raise fatal_checker_error
    if cancelled:
        if checked:
            outcome['checker_usage'] = checker_budget.snapshot()
            save_json(run_dir / 'status.json', outcome)
        raise asyncio.CancelledError
    if checked:
        outcome['diagnostics'] = {'status': 'unstarted', 'outcome_mention': 'skipped: no gold outcome list supplied'}
        if outcome['status'] == 'completed':
            try:
                path = await run_j2(run_dir, checked, protocol, task.question)
                records = read_events(path)
                outcome['diagnostics'].update(status='completed' if all(not r.get('error') for r in records) else 'partial',
                                              records=len(records))
            except BaseException:
                outcome['diagnostics']['status'] = 'interrupted'
                outcome['checker_usage'] = checker_budget.snapshot()
                save_json(run_dir / 'status.json', outcome)
                raise
        outcome['checker_usage'] = checker_budget.snapshot()
        save_json(run_dir / 'status.json', outcome)
    return outcome
