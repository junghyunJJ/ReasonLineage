import asyncio
import json
import time
from dataclasses import replace

from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case
from reasonlineage.pilot.study import dry_plan, run_study
from test_pilot_run import FakeBackend, ROOT
from test_pilot_study import Independent


class LongAnswer(FakeBackend):
    async def complete(self, request):
        response = await super().complete(request)
        if 'answer' in request.json_schema['properties']:
            data = dict(response.data)
            data['answer'] += ' An additional control is specified.' * 100
            return replace(response, data=data, text=json.dumps(data))
        return response


def test_relaxed_three_model_run_completes_thirty_calls_and_retains_long_answer(tmp_path):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: LongAnswer(m.name) for m in setup.panel}
    result = asyncio.run(run_case(tmp_path / 'case', 'als', 'reasonlineage', setup, services,
                                 Budget(seconds=100), root=ROOT, protocol_directory='protocol-relaxed'))
    assert result['status'] == 'completed'
    assert result['usage']['backend_calls'] == 30
    assert len(result['final']['answer']['answer'].split()) > 800
    events = read_events(tmp_path / 'case/events.jsonl')
    assert len([e for e in events if e['event'] == 'candidate.created']) == 10
    assert len([e for e in events if e['event'] == 'judge.scored']) == 20
    assert any(e['event'] == 'anomaly' and e['kind'] == 'answer_length' for e in events)
    assert result['header']['budgets']['call_limit'] == 40


def test_relaxed_solo_keeps_four_seeds_two_fresh_critics_and_no_crossover(tmp_path):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {'gpt': LongAnswer('gpt')}
    result = asyncio.run(run_case(tmp_path / 'case', 'als', 'gpt', setup, services,
                                 Budget(seconds=100), root=ROOT, protocol_directory='protocol-relaxed'))
    assert result['status'] == 'completed' and result['usage']['backend_calls'] == 30
    events = read_events(tmp_path / 'case/events.jsonl')
    assert not any(e.get('operator') == 'crossover' for e in events)
    assert {e['judge'] for e in events if e['event'] == 'judge.scored'} == {'gpt-r0', 'gpt-r1'}


def test_relaxed_profile_records_eight_slots_and_expanded_local_limits():
    plan = dry_plan(ROOT, relaxed=True)
    assert len(plan['schedule']) == 8
    assert {s['method'] for s in plan['schedule']} == {'reasonlineage', 'gpt', 'grok', 'glm'}
    assert plan['limits']['run_seconds'] == 2700
    assert plan['limits']['run_tokens'] == 800000
    assert plan['limits']['run_calls'] == 30
    assert plan['limits']['total_seconds'] == 14400


def test_relaxed_parallel_provider_chains_have_one_active_case_per_backend(tmp_path):
    observed = set()
    gate = asyncio.Event()
    class Active(LongAnswer):
        active = peak = 0
        async def complete(self, request):
            self.active += 1
            self.peak = max(self.peak, self.active)
            if (tmp_path / f'study/runs/als-{self.name}/header.json').exists():
                observed.add(self.name)
                if observed == {'gpt', 'grok', 'glm'}:
                    gate.set()
                await asyncio.wait_for(gate.wait(), 2)
            await asyncio.sleep(.001)
            try:
                return await super().complete(request)
            finally:
                self.active -= 1
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: Active(m.name) for m in setup.panel}
    result = asyncio.run(run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                   evaluator=Independent(), relaxed=True))
    assert len(result['runs']) == 8 and all(r['status'] == 'completed' for r in result['runs'])
    assert result['usage']['backend_calls'] == 244
    assert len(result['comparisons']) == 6
    assert all(b.peak <= setup.concurrency for b in services.values())
    assert observed == {'gpt', 'grok', 'glm'}


def test_preflight_usage_and_clock_are_part_of_the_global_rerun_budget(tmp_path):
    preflight = tmp_path / 'preflight'
    preflight.mkdir()
    anchor = time.monotonic()
    (preflight / 'clock.json').write_text(json.dumps({'monotonic': anchor, 'utc': 'test'}))
    for i in range(4):
        (preflight / f'{i}-receipt.json').write_text(json.dumps({'reported_usage': [1, 2, 3]}))
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: LongAnswer(m.name) for m in setup.panel}
    result = asyncio.run(run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                   evaluator=Independent(), relaxed=True, preflight_directory=preflight))
    assert result['usage']['backend_calls'] == 248
    assert result['usage']['reported_tokens'] == 6112
    assert json.loads((tmp_path / 'study/clock.json').read_text())['monotonic'] == anchor
