"""One initial hypothesis per generator, then two survivors and two offspring."""
import asyncio
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case
from test_pilot_run import FakeBackend
from test_pilot_study import Independent

ROOT = Path(__file__).resolve().parents[1]


def inputs(tmp_path, **overrides):
    root = tmp_path / 'inputs'
    destination = root / 'research/co-scientist-pilot'
    destination.mkdir(parents=True)
    for case in ('als', 'aml'):
        shutil.copyfile(ROOT / f'research/co-scientist-pilot/{case}-evidence.md', destination / f'{case}-evidence.md')
    shutil.copytree(ROOT / 'research/co-scientist-pilot/protocol-relaxed', destination / 'protocol-three-initial')
    path = destination / 'protocol-three-initial/protocol.json'
    data = json.loads(path.read_text())
    data['version'] = 'co-scientist-three-initial-0.5'
    data['pilot'].update(initial_population=3, population_limit=4, survivor_count=2, nominal_call_count=27)
    data['pilot'].update(overrides)
    path.write_text(json.dumps(data))
    return root


def execute(tmp_path, case, method, **overrides):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: FakeBackend(m.name) for m in setup.panel}
    root = inputs(tmp_path, **overrides)
    directory = tmp_path / f'{case}-{method}'
    result = asyncio.run(run_case(directory, case, method, setup, services, Budget(seconds=100),
                                  root=root, protocol_directory='protocol-three-initial'))
    return result, read_events(directory / 'events.jsonl'), services, directory


@pytest.mark.parametrize('case', ['als', 'aml'])
def test_three_models_seed_once_then_keep_two_and_create_mutation_and_crossover(tmp_path, case):
    result, events, _, directory = execute(tmp_path, case, 'reasonlineage')
    assert result['status'] == 'completed'
    created = [e for e in events if e['event'] == 'candidate.created']
    seeds = [e for e in created if e['generation'] == 0]
    assert Counter(e['author'] for e in seeds) == {'gpt': 1, 'grok': 1, 'glm': 1}
    assert Counter(e['operator'] for e in created) == {'seed': 3, 'mutation': 3, 'crossover': 3}
    by_id = {e['id']: e for e in created}
    for selection in (e for e in events if e['event'] == 'selection'):
        assert len(selection['survivors']) == 2
        children = [e for e in created if e['generation'] == selection['generation'] + 1]
        assert len(children) == 2
        mutation = next(e for e in children if e['operator'] == 'mutation')
        cross = next(e for e in children if e['operator'] == 'crossover')
        assert mutation['parents'] == selection['survivors'][:1]
        assert mutation['author'] == by_id[mutation['parents'][0]]['author']
        assert cross['parents'] == selection['survivors']
        assert cross['author'] not in {by_id[p]['author'] for p in cross['parents']}
    judged = [e for e in events if e['event'] == 'judge.scored']
    assert len(judged) == 18
    assert set(Counter(e['candidate'] for e in judged).values()) == {2}
    assert all(e['judge'] != e['author'] for e in judged)
    assert result['usage']['backend_calls'] == 27
    assert len(json.loads((directory / 'result.json').read_text())['population']) == 4
    assert result['header']['evolution'] == {'initial_candidates': 3, 'population_limit': 4,
                                           'survivor_count': 2, 'generations': 3}


@pytest.mark.parametrize('method', ['gpt', 'grok', 'glm'])
def test_single_model_control_uses_same_three_initial_candidates(tmp_path, method):
    result, events, services, _ = execute(tmp_path, 'aml', method)
    assert result['status'] == 'completed'
    created = [e for e in events if e['event'] == 'candidate.created']
    assert Counter(e['operator'] for e in created) == {'seed': 3, 'mutation': 6}
    assert all(e['author'] == method for e in created)
    assert all(len(e['survivors']) == 2 for e in events if e['event'] == 'selection')
    assert result['usage']['backend_calls'] == len(services[method].requests) == 27
    assert result['header']['evolution']['initial_candidates'] == 3


@pytest.mark.parametrize('settings', [
    {'initial_population': 5}, {'initial_population': 2}, {'initial_population': True},
    {'population_limit': 2}, {'survivor_count': True},
])
def test_invalid_population_settings_stop_before_any_provider_call(tmp_path, settings):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: FakeBackend(m.name) for m in setup.panel}
    root = inputs(tmp_path, **settings)
    with pytest.raises(ValueError):
        asyncio.run(run_case(tmp_path / 'invalid', 'als', 'reasonlineage', setup, services,
                             Budget(seconds=100), root=root, protocol_directory='protocol-three-initial'))
    assert all(not s.requests for s in services.values())


def test_command_selects_three_initial_profile_without_dispatch(tmp_path):
    destination = tmp_path / 'never-created'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_co_scientist_pilot.py'),
                             '--three-initial', '--out', str(destination)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['protocol_directory'] == 'protocol-three-initial'
    assert {m['name'] for m in plan['models']} == {'gpt', 'grok', 'glm'}
    assert plan['limits']['run_calls'] == 27
    assert len(plan['schedule']) == 8
    assert not destination.exists()


def test_full_study_uses_new_profile_for_multi_and_solo_slots(tmp_path):
    from reasonlineage.pilot.study import run_study
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    services = {m.name: FakeBackend(m.name) for m in setup.panel}
    judge = Independent()
    result = asyncio.run(run_study(tmp_path / 'study', ROOT, setup=setup, services=services,
                                   evaluator=judge, three_initial=True))
    assert len(result['runs']) == 8
    assert all(r['status'] == 'completed' and r['usage']['backend_calls'] == 27 for r in result['runs'])
    assert all(r['header']['evolution']['initial_candidates'] == 3 for r in result['runs'])
    assert all(r['header']['evolution']['survivor_count'] == 2 for r in result['runs'])
    assert result['usage']['backend_calls'] == 8 * 27 + 4
    assert len(judge.requests) == 4
    assert result['frozen_plan']['protocol_directory'] == 'protocol-three-initial'
