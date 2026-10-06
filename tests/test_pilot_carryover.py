import asyncio
import importlib.util
import json
import sys

import pytest

from reasonlineage.engine.config import load_setup
from reasonlineage.pilot import study
from test_pilot_run import FakeBackend, ROOT
from test_pilot_study import Independent


def prior_attempt(tmp_path, *, calls=22, started=900):
    prior = tmp_path / 'prior'
    prior.mkdir()
    usage = {'backend_calls': calls, 'reported_input_tokens': 39656,
             'reported_output_tokens': 114130, 'reported_tokens': 153786,
             'unknown_usage_calls': 9, 'elapsed_seconds': 100,
             'remaining_seconds': 11900, 'token_limit': None,
             'call_limit': 248, 'seconds_limit': 12000}
    (prior / 'study.json').write_text(json.dumps({'usage': usage, 'cancelled': True}))
    clock = {'monotonic': started, 'utc': 'original-start',
             'first_model_dispatch': 'preflight diagnostic'}
    (prior / 'clock.json').write_text(json.dumps(clock))
    preflight = prior / 'preflight'
    preflight.mkdir()
    for index in range(4):
        (preflight / f'{index}-receipt.json').write_text(json.dumps({'reported_usage': [1, 2, 3]}))
    calls_dir = prior / 'runs/als-glm/calls/g0/write'
    calls_dir.mkdir(parents=True)
    (calls_dir / 'c001.json').write_text(json.dumps({'response': {'cost_usd': .75}}))
    (prior / 'provenance.txt').write_text('Keep all interrupted-attempt records.')
    return prior


@pytest.fixture
def fixed_clock(monkeypatch):
    original = study.StudyBudget

    class FixedClockBudget(original):
        def __init__(self, destination, **kwargs):
            super().__init__(destination, clock=lambda: 1000.0, **kwargs)

    monkeypatch.setattr(study, 'StudyBudget', FixedClockBudget)


def fake_study(out, **kwargs):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    return asyncio.run(study.run_study(out, ROOT, setup=setup,
                       services={m.name: FakeBackend(m.name) for m in setup.panel},
                       evaluator=Independent(), relaxed=True, **kwargs))


def test_fresh_relaxed_plan_distinguishes_nominal_calls_from_retry_capacity():
    plan = study.dry_plan(ROOT, relaxed=True)
    assert len(plan['schedule']) == 8
    assert plan['limits']['run_calls'] == 30
    assert plan['limits']['max_run_calls'] == 40
    assert plan['limits']['total_calls'] == 328
    assert plan['limits']['total_seconds'] == 14400
    assert plan['limits']['generation_seconds'] == 12000
    assert study.dry_plan(ROOT)['limits']['total_calls'] == 404


def test_prior_usage_replaces_diagnostic_allowance_in_relaxed_ceiling(tmp_path):
    prior = prior_attempt(tmp_path)
    plan = study.dry_plan(ROOT, relaxed=True, prior_run_directory=prior)
    assert plan['limits']['total_calls'] == 346
    assert plan['prior_attempt']['usage']['backend_calls'] == 22
    assert plan['prior_attempt']['directory'] == str(prior.resolve())


def test_carryover_seeds_aggregate_usage_once_and_keeps_prior_immutable(tmp_path, fixed_clock):
    prior = prior_attempt(tmp_path)
    original = {p.relative_to(prior): p.read_bytes() for p in prior.rglob('*') if p.is_file()}
    out = tmp_path / 'study'
    result = fake_study(out, prior_run_directory=prior)
    assert [run['status'] for run in result['runs']] == ['completed'] * 8
    assert result['usage']['backend_calls'] == 266
    assert result['usage']['reported_input_tokens'] == 42096
    assert result['usage']['reported_output_tokens'] == 117790
    assert result['usage']['reported_tokens'] == 159886
    assert result['usage']['unknown_usage_calls'] == 9
    assert result['usage']['elapsed_seconds'] == 100
    assert result['usage']['remaining_seconds'] == 14300
    assert result['usage']['call_limit'] == 346
    assert result['cost']['provider_reported_cost_usd'] == .75
    assert result['cost']['completed_responses'] == 245
    assert json.loads((out / 'clock.json').read_text()) == json.loads((prior / 'clock.json').read_text())
    copied = {p.relative_to(out / 'prior-attempt'): p.read_bytes()
              for p in (out / 'prior-attempt').rglob('*') if p.is_file()}
    assert copied == original
    assert {p.relative_to(prior): p.read_bytes() for p in prior.rglob('*') if p.is_file()} == original


@pytest.mark.parametrize(('started', 'elapsed', 'remaining'), [
    (-11001, 12001, 2399), (-13401, 14401, 0),
])
def test_prior_clock_keeps_original_generation_and_total_deadlines(tmp_path, fixed_clock,
                                                                 started, elapsed, remaining):
    prior = prior_attempt(tmp_path, started=started)
    result = fake_study(tmp_path / 'study', prior_run_directory=prior)
    assert [run['status'] for run in result['runs']] == ['unstarted'] * 8
    assert [review['status'] for review in result['independent_evaluations']] == ['unstarted'] * 4
    assert result['usage']['backend_calls'] == 22
    assert result['usage']['reported_tokens'] == 153786
    assert result['usage']['unknown_usage_calls'] == 9
    assert result['usage']['elapsed_seconds'] == elapsed
    assert result['usage']['remaining_seconds'] == remaining
    assert result['usage']['seconds_limit'] == 14400


def test_carryover_rejects_preflight_conflict_before_creating_output(tmp_path):
    prior = prior_attempt(tmp_path)
    out = tmp_path / 'study'
    with pytest.raises(ValueError, match='mutually exclusive'):
        fake_study(out, prior_run_directory=prior, preflight_directory=prior / 'preflight')
    assert not out.exists()


@pytest.mark.parametrize(('calls', 'accepted'), [(80, True), (81, False)])
def test_carryover_cannot_expand_original_404_call_authorization(tmp_path, calls, accepted):
    prior = prior_attempt(tmp_path, calls=calls)
    out = tmp_path / 'study'
    if accepted:
        assert study.dry_plan(ROOT, relaxed=True, prior_run_directory=prior)['limits']['total_calls'] == 404
    else:
        with pytest.raises(ValueError, match='404'):
            fake_study(out, prior_run_directory=prior)
        assert not out.exists()


def test_strict_profile_cannot_add_carried_calls_to_its_original_ceiling(tmp_path):
    prior = prior_attempt(tmp_path)
    with pytest.raises(ValueError, match='404'):
        study.dry_plan(ROOT, prior_run_directory=prior)


def test_carryover_cannot_extend_original_time_allowance(tmp_path, fixed_clock):
    prior = prior_attempt(tmp_path, started=-11001)
    result = fake_study(tmp_path / 'study', prior_run_directory=prior,
                        generation_seconds=20000, total_seconds=30000)
    assert [run['status'] for run in result['runs']] == ['unstarted'] * 8
    assert result['usage']['backend_calls'] == 22
    assert result['usage']['seconds_limit'] == 14400
    assert result['usage']['remaining_seconds'] == 2399


def test_carryover_refuses_existing_output_and_output_inside_prior(tmp_path):
    prior = prior_attempt(tmp_path)
    marker = prior / 'provenance.txt'
    with pytest.raises(FileExistsError):
        fake_study(prior, prior_run_directory=prior)
    with pytest.raises(ValueError, match='inside prior'):
        fake_study(prior / 'new-attempt', prior_run_directory=prior)
    assert marker.read_text() == 'Keep all interrupted-attempt records.'
    assert not (prior / 'new-attempt').exists()


@pytest.mark.parametrize('key', ['backend_calls', 'reported_input_tokens', 'reported_output_tokens',
                                 'reported_tokens', 'unknown_usage_calls'])
def test_carryover_rejects_invalid_aggregate_usage_without_dispatch(tmp_path, key):
    prior = prior_attempt(tmp_path)
    path = prior / 'study.json'
    prior_study = json.loads(path.read_text())
    prior_study['usage'][key] = -1
    path.write_text(json.dumps(prior_study))
    out = tmp_path / 'study'
    with pytest.raises(ValueError, match='prior.*usage'):
        fake_study(out, prior_run_directory=prior)
    assert not out.exists()


@pytest.mark.parametrize('value', [None, True, '900', float('nan'), float('inf')])
def test_carryover_requires_finite_original_monotonic_clock(tmp_path, value):
    prior = prior_attempt(tmp_path)
    path = prior / 'clock.json'
    clock = json.loads(path.read_text())
    clock['monotonic'] = value
    path.write_text(json.dumps(clock))
    out = tmp_path / 'study'
    with pytest.raises(ValueError, match='prior.*clock'):
        fake_study(out, prior_run_directory=prior)
    assert not out.exists()


@pytest.mark.parametrize(('key', 'value'), [('reported_tokens', 153785), ('unknown_usage_calls', 23)])
def test_carryover_requires_consistent_aggregate_usage(tmp_path, key, value):
    prior = prior_attempt(tmp_path)
    path = prior / 'study.json'
    prior_study = json.loads(path.read_text())
    prior_study['usage'][key] = value
    path.write_text(json.dumps(prior_study))
    out = tmp_path / 'study'
    with pytest.raises(ValueError, match='prior.*usage'):
        fake_study(out, prior_run_directory=prior)
    assert not out.exists()


def load_script():
    spec = importlib.util.spec_from_file_location('carryover_pilot_script', ROOT / 'scripts/run_co_scientist_pilot.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_cli_dry_plan_reports_carried_ceiling_without_dispatch(tmp_path, monkeypatch, capsys):
    prior = prior_attempt(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run_co_scientist_pilot.py', '--relaxed', '--prior-run-dir', str(prior)])
    assert load_script().main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['limits']['total_calls'] == 346
    assert not (tmp_path / 'study').exists()


def test_cli_rejects_prior_preflight_conflict(tmp_path, monkeypatch, capsys):
    prior = prior_attempt(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run_co_scientist_pilot.py', '--relaxed', '--prior-run-dir', str(prior),
                                   '--preflight-dir', str(prior / 'preflight')])
    with pytest.raises(SystemExit) as error:
        load_script().main()
    assert error.value.code == 2
    assert 'not allowed with argument' in capsys.readouterr().err


def test_cli_supervisor_uses_prior_original_clock(tmp_path, monkeypatch):
    prior = prior_attempt(tmp_path)
    out = tmp_path / 'study'
    script = load_script()
    seen = {}

    def fake_supervisor(command, clock_file):
        seen['command'], seen['clock_file'] = command, clock_file
        return 17

    monkeypatch.setattr(script, 'supervise', fake_supervisor)
    monkeypatch.setattr(sys, 'argv', ['run_co_scientist_pilot.py', '--run', '--relaxed',
                                   '--out', str(out), '--prior-run-dir', str(prior)])
    assert script.main() == 17
    assert seen['clock_file'] == prior / 'clock.json'
    assert seen['command'][-2:] == ['--prior-run-dir', str(prior.resolve())]
    assert not out.exists()
