import asyncio
import json
import sys
import time

import pytest

from reasonlineage.backends.base import ModelResponse
from reasonlineage.engine.config import load_setup
from reasonlineage.pilot.study import dry_plan, run_study, supervise
from test_pilot_run import FakeBackend, ROOT


class Independent:
    name = 'independent'

    def __init__(self):
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        ids = request.json_schema['properties']['reviews']['items']['properties']['id']['enum']
        data = {'reviews': [{'id': pid, 'grounding': 3, 'causal_rigor': 3, 'specificity': 3,
                             'testability': 3, 'feasibility': 3, 'reason': 'Specific but speculative.',
                             'novelty_note': 'Not established.'} for pid in ids]}
        return ModelResponse(self.name, request.model, json.dumps(data), data, .01, None,
                             request.prompt_sha256, {'usage': {'input_tokens': 10, 'output_tokens': 15}})


def test_dry_plan_pins_inputs_without_creating_output_or_calling_models(tmp_path):
    plan = dry_plan(ROOT)
    assert len(plan['schedule']) == 10
    assert plan['schedule'][:2] == [{'case': 'als', 'method': 'reasonlineage'}, {'case': 'aml', 'method': 'reasonlineage'}]
    assert plan['limits']['total_seconds'] == 14400
    assert len(plan['evidence_sha256']['als']) == 64
    assert plan['independent_model'] == 'deepseek-v4.1-flash'
    assert not list(tmp_path.iterdir())


def test_full_study_uses_400_generation_and_four_held_out_calls(tmp_path):
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    services = {m.name: FakeBackend(m.name) for m in setup.panel}
    judge = Independent()
    out = tmp_path / 'study'
    result = asyncio.run(run_study(out, ROOT, setup=setup, services=services, evaluator=judge))
    assert [s['status'] for s in result['runs']] == ['completed'] * 10
    assert result['usage']['backend_calls'] == 404
    assert len(judge.requests) == 4
    forward, reverse = judge.requests[:2]
    ids = lambda r: r.json_schema['properties']['reviews']['items']['properties']['id']['enum']
    assert ids(forward) == list(reversed(ids(reverse)))
    assert result['expert_status'] == 'pending'
    assert len(result['comparisons']) == 8
    assert (out / 'clock.json').exists()
    assert len(json.loads((out / 'study.json').read_text())['runs']) == 10
    count = sum(len(b.requests) for b in services.values())
    with pytest.raises(FileExistsError):
        asyncio.run(run_study(out, ROOT, setup=setup, services=services, evaluator=judge))
    assert sum(len(b.requests) for b in services.values()) == count


def test_deadline_preserves_failures_and_marks_remaining_slots_unstarted(tmp_path):
    class Slow(FakeBackend):
        async def complete(self, request):
            self.requests.append(request)
            await asyncio.sleep(2)
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    services = {m.name: Slow(m.name) for m in setup.panel}
    result = asyncio.run(run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                   evaluator=Independent(), generation_seconds=.02, total_seconds=.05))
    assert result['runs'][0]['status'] in ('failed', 'cutoff')
    assert [s['status'] for s in result['runs'][1:]] == ['unstarted'] * 9
    assert result['usage']['unknown_usage_calls'] > 0
    assert result['usage']['backend_calls'] <= 4


def test_supervisor_enforces_deadline_even_when_worker_ignores_sigterm(tmp_path):
    marker = tmp_path / 'clock.json'
    code = ('import json,time,signal,pathlib; '
            'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
            f'pathlib.Path({str(marker)!r}).write_text(json.dumps({{"monotonic":time.monotonic()}})); '
            'time.sleep(10)')
    start = time.monotonic()
    assert supervise([sys.executable, '-c', code], marker, max_seconds=.05, grace_seconds=.05, poll_seconds=.01) != 0
    assert time.monotonic() - start < 2


def test_cancelled_review_preserves_previous_ratings_and_all_review_statuses(tmp_path):
    class CancelSecond(Independent):
        async def complete(self, request):
            if len(self.requests) == 1:
                raise asyncio.CancelledError
            return await super().complete(request)
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    services = {m.name: FakeBackend(m.name) for m in setup.panel}
    out = tmp_path / 'study'
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_study(out, ROOT, setup=setup, services=services, evaluator=CancelSecond()))
    result = json.loads((out / 'study.json').read_text())
    assert [e['status'] for e in result['independent_evaluations']] == ['completed', 'cutoff', 'unstarted', 'unstarted']
    assert result['independent_evaluations'][0]['ratings']
