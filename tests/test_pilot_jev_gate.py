import asyncio
import json
import hashlib
import subprocess
import sys
from dataclasses import replace

import pytest

from reasonlineage.checks.base import CheckAnswer, CheckResult, CheckerError
from reasonlineage.checks.calibration import VERSION
from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case
from reasonlineage.pilot.checker import CheckerVersionMismatch
from test_pilot_run import FakeBackend, ROOT


class UniqueBackend(FakeBackend):
    async def complete(self, request):
        response = await super().complete(request)
        if 'answer' in request.json_schema['properties']:
            data = {**response.data, 'answer': self.name + ' proposal. ' + response.data['answer']}
            return replace(response, text=json.dumps(data), data=data)
        data = {**response.data, 'critique': [self.name + ' critique ' + hashlib.sha256(request.prompt.encode()).hexdigest()[:12]]}
        return replace(response, text=json.dumps(data), data=data)


class JevStub:
    name, pinned_version = 'jev', VERSION
    def __init__(self, *, bad_first=False, always_bad=False, model=VERSION):
        self.bad_first, self.always_bad, self.model = bad_first, always_bad, model
        self.asked = []
    async def ask(self, state, questions):
        self.asked.append((state, questions))
        answers = {}
        for q in questions:
            if q.kind == 'noul':
                value = .1 if self.always_bad or self.bad_first and len(self.asked) == 1 else .99
                answers[q.name] = CheckAnswer('noul', {'yes': value, 'no': 1-value})
            elif q.kind == 'score':
                level = '3' if q.name == 'argument_coverage' else '0'
                answers[q.name] = CheckAnswer('score', {level: 1.0})
            else:
                chosen = 'answer' if q.name == 'answer_type' else 'minor'
                answers[q.name] = CheckAnswer('choice', {name: float(name == chosen) for name, _ in q.choices})
        return CheckResult(self.model, answers, {'input_tokens': 11, 'output_tokens': 2})


def execute(tmp_path, checker):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: UniqueBackend(m.name) for m in setup.panel}
    shared = Budget(seconds=100, calls=1000, tokens=None)
    result = asyncio.run(run_case(tmp_path / 'run', 'als', 'reasonlineage', setup, services, shared,
                                  root=ROOT, protocol_directory='protocol-three-initial-jev', checker=checker))
    return result, services, read_events(tmp_path / 'run/events.jsonl'), shared


def test_first_defect_rewrites_same_author_once_and_records_recheck_before_scoring(tmp_path):
    checker = JevStub(bad_first=True)
    result, services, events, shared = execute(tmp_path, checker)
    assert result['status'] == 'completed'
    rewrites = [e for e in events if e['event'] == 'call.completed' and '/rewrite/' in e['name']]
    assert len(rewrites) == 1 and rewrites[0]['name'].endswith('/gpt')
    assert result['usage']['backend_calls'] == 28
    checks = read_events(tmp_path / 'run/checks.jsonl')
    first = [r for r in checks if r['candidate'] == 'c001']
    assert [r['attempt'] for r in first] == [0, 1]
    assert first[0]['would_rewrite'] and not first[1]['would_rewrite']
    assert result['checker_usage']['backend_calls'] == len(checker.asked) == 37
    assert result['diagnostics']['status'] == 'completed'
    assert len(read_events(tmp_path / 'run/diagnostics/j2.jsonl')) == 27
    assert shared.calls_used == 28 + 37
    assert all(e['judge'] != e['author'] for e in events if e['event'] == 'judge.scored')


def test_remaining_defect_is_recorded_after_one_rewrite_and_candidate_is_not_deleted(tmp_path):
    result, _, events, _ = execute(tmp_path, JevStub(always_bad=True))
    assert result['status'] == 'completed'
    created = [e for e in events if e['event'] == 'candidate.created']
    assert len(created) == 9
    assert result['usage']['backend_calls'] == 36
    checks = read_events(tmp_path / 'run/checks.jsonl')
    assert len([r for r in checks if r['attempt'] == 1 and r['would_rewrite']]) == 9
    assert len([e for e in events if e['event'] == 'judge.scored']) == 18


def test_missing_checker_and_version_drift_never_silently_enable_unchecked_execution(tmp_path):
    with pytest.raises(ValueError, match='checker'):
        execute(tmp_path / 'missing', None)
    with pytest.raises(CheckerVersionMismatch, match='version'):
        execute(tmp_path / 'drift', JevStub(model='jev-other-version'))
    result = json.loads((tmp_path / 'drift/run/status.json').read_text())
    events = read_events(tmp_path / 'drift/run/events.jsonl')
    assert result['status'] == 'failed' and 'final' not in result
    assert not [e for e in events if e['event'] == 'judge.scored']


def test_j1_version_drift_stops_the_study_before_later_generation_slots(tmp_path):
    from reasonlineage.pilot import study
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: UniqueBackend(m.name) for m in setup.panel}
    result = asyncio.run(study.run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                        jev=True, checker=JevStub(model='jev-other-version')))
    assert result['runs'][0]['status'] == 'failed'
    assert all(r['status'] == 'unstarted' for r in result['runs'][1:])
    assert sum(len(s.requests) for s in services.values()) == 3


def test_jev_study_does_not_even_construct_the_deepseek_evaluator(tmp_path, monkeypatch):
    from reasonlineage.pilot import study
    def forbidden(*args, **kwargs):
        raise AssertionError('DeepSeek must not be constructed in jev mode')
    monkeypatch.setattr(study, 'evaluator_member', forbidden)
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: UniqueBackend(m.name) for m in setup.panel}
    result = asyncio.run(study.run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                        jev=True, checker=JevStub()))
    assert all(r['status'] == 'completed' for r in result['runs'])
    assert result['independent_evaluations'] == []
    assert result['independent_status'] == 'disabled_by_config'
    assert all(r['diagnostics']['status'] == 'completed' for r in result['runs'])
    assert result['frozen_plan']['independent_model'] is None
    assert result['frozen_plan']['protocol_directory'] == 'protocol-three-initial-jev'


def test_cli_jev_mode_uses_validated_profile_and_disables_deepseek_without_calls(tmp_path):
    path = tmp_path / 'not-started'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_co_scientist_pilot.py'),
                             '--jev', '--out', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['protocol_directory'] == 'protocol-three-initial-jev'
    assert plan['independent_model'] is None
    assert plan['limits']['max_checker_calls'] == 50
    assert not path.exists()


def test_checker_outage_is_reported_as_unchecked_instead_of_a_pass(tmp_path):
    class Outage(JevStub):
        async def ask(self, state, questions):
            raise CheckerError('test-private-outage-content')
    result, _, _, _ = execute(tmp_path, Outage())
    assert result['status'] == 'completed'
    assert result['j1']['status'] == 'partial' and result['j1']['failed_checks'] == 9
    assert result['diagnostics']['status'] == 'partial'
    assert 'test-private-outage-content' not in ''.join(p.read_text() for p in (tmp_path / 'run').rglob('*.json*'))
