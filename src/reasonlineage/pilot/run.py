"""Isolated pilot runs; preserve the default engine and selection rules."""

import asyncio
import hashlib
import json
from pathlib import Path

from ..core.state import EvolutionState
from ..engine import answer as fmt
from ..engine.calls import CallRecorder
from ..engine.config import RunOptions, Task
from ..engine.errors import RunStopped
from ..engine.events import EventLog
from ..engine.runner import Runner, Written, WritingFailed, gather_all
from ..protocol import load_protocol
from .budget import Budget, MeteredBackend


def save_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


class PilotRunner(Runner):
    initial = None

    async def _write(self, gen, role, cid, author, prompt):
        name = f'g{gen}/{role}/{cid}/{author}'
        data = await self._author_call(name, author, prompt)
        issues = fmt.validate_answer(data, None)
        if issues.hard or len(data['ranking']) != 1 or not data['answer'].strip():
            raise WritingFailed('invalid one-hypothesis output')
        low, high = self.protocol.answer_words
        if not low <= len(data['answer'].split()) <= high:
            raise WritingFailed('proposal outside the agreed 400–800 word range')
        anomalies = []
        if issues.soft:
            anomalies.append({'kind': 'prose_mention', 'candidate': cid,
                              'detail': list(issues.soft), 'action': 'proceed without repair'})
        return Written(author, data, [name], anomalies)

    def _remember_initial(self, state):
        if state.generation == 0:
            best = state.best
            self.initial = {'id': best.id, 'author': best.author, 'fitness': best.fitness,
                            'scores': best.scores, 'answer': self.answers[best.id]}
            self.events.emit('pilot.initial', **self.initial)

    async def _score(self, state):
        await super()._score(state)
        self._remember_initial(state)


class SoloRunner(PilotRunner):
    async def _generation_zero(self):
        actor = self.names[0]
        jobs = [(self._new_id(), actor) for _ in range(4)]
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
        judges = [f'{actor}-r{i}' for i in range(3)]
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


async def run_case(run_dir, case, method, setup, services, shared, *, root, seconds=1200, tokens=400000):
    if case not in ('als', 'aml') or method not in ('reasonlineage', 'gpt', 'opus', 'grok', 'glm'):
        raise ValueError('unknown pilot case or method')
    run_dir, root = Path(run_dir), Path(root)
    run_dir.mkdir(parents=True, exist_ok=False)
    evidence = (root / f'research/co-scientist-pilot/{case}-evidence.md').read_bytes()
    protocol = load_protocol(root / 'research/co-scientist-pilot/protocol')
    members = setup.panel if method == 'reasonlineage' else tuple(m for m in setup.panel if m.name == method)
    if len(members) != (4 if method == 'reasonlineage' else 1):
        raise ValueError('pilot requires the pinned four-model roster')
    local = Budget(seconds=seconds, tokens=tokens, calls=40, lazy=True)
    backends = {m.name: MeteredBackend(services[m.name], local, shared) for m in members}
    header = {'case': case, 'method': method, 'evidence_sha256': hashlib.sha256(evidence).hexdigest(),
              'protocol_sha256': protocol.hash, 'protocol_version': protocol.version,
              'models': [{'name': m.name, 'model': m.model, 'effort': m.effort} for m in members],
              'options': RunOptions().to_dict(), 'budgets': local.snapshot()}
    save_json(run_dir / 'header.json', header)
    task = Task(case, evidence.decode('utf-8'), None, 'biomedical', 'public')
    events = EventLog(run_dir / 'events.jsonl')
    recorder = CallRecorder(run_dir, events, run_seed=20261005, attempts=1)
    runner_type = PilotRunner if method == 'reasonlineage' else SoloRunner
    runner = runner_type(run_dir=run_dir, run_id=f'{case}-{method}', task=task, members=members,
                         backends=backends, protocol=protocol, options=RunOptions(), events=events, recorder=recorder)
    outcome = {'header': header}
    cancelled = False
    try:
        result = await runner.run()
        outcome.update(status='completed', final=result['best'])
    except RunStopped as error:
        outcome.update(status='failed', reason=str(error))
    except asyncio.CancelledError:
        cancelled = True
        events.stop('cancelled at study deadline or signal')
        outcome.update(status='cutoff', reason='study deadline or signal')
    if runner.initial is not None:
        outcome['initial'] = runner.initial
    outcome['usage'] = local.snapshot()
    save_json(run_dir / 'status.json', outcome)
    if cancelled:
        raise asyncio.CancelledError
    return outcome
