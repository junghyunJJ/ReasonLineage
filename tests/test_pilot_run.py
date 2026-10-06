import asyncio
import json
from pathlib import Path

import pytest

from reasonlineage.backends.base import BackendError, ModelResponse
from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case

ROOT = Path(__file__).resolve().parents[1]


class FakeBackend:
    def __init__(self, name, fail_at=None, malformed=False):
        self.name, self.fail_at, self.malformed = name, fail_at, malformed
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if len(self.requests) == self.fail_at:
            raise BackendError('refused')
        if 'answer' in request.json_schema['properties']:
            title = f'Testable pore hypothesis {len(self.requests)}'
            data = {'answer': title + '. Supported premise [S1]. Speculative bridge; falsifier stated.',
                    'ranking': [{'item': title, 'promisingness': .7, 'confidence': .6, 'pmids': []}]}
            if self.malformed:
                data['ranking'].append(dict(data['ranking'][0], item='second hypothesis'))
        else:
            data = {key: .72 for key in request.json_schema['properties'] if key != 'critique'}
            data['critique'] = ['Separate premise from assumption.']
        return ModelResponse(self.name, request.model, json.dumps(data), data, .01, None,
                             request.prompt_sha256, {'usage': {'input_tokens': 10, 'output_tokens': 15},
                                                     'reasoning': 'PRIVATE_CANARY'})


def execute(tmp_path, method, services=None, case='als'):
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    services = services or {m.name: FakeBackend(m.name) for m in setup.panel}
    outcome = asyncio.run(run_case(tmp_path / f'{case}-{method}', case, method, setup,
                                   services, Budget(seconds=100), root=ROOT))
    return outcome, services


@pytest.mark.parametrize('method', ['reasonlineage', 'gpt'])
def test_full_run_has_matched_candidates_and_fresh_critics(tmp_path, method):
    result, services = execute(tmp_path, method)
    assert result['status'] == 'completed'
    assert result['usage']['backend_calls'] == 40
    assert result['usage']['reported_tokens'] == 1000
    events = read_events(tmp_path / f'als-{method}' / 'events.jsonl')
    candidates = [e for e in events if e['event'] == 'candidate.created']
    assert len(candidates) == 10
    assert len([e for e in events if e['event'] == 'judge.scored']) == 30
    calls = [e['name'] for e in events if e['event'] == 'call.completed']
    assert len(calls) == len(set(calls)) == 40
    assert not any('realign' in c or 'rewrite' in c for c in calls)
    assert result['initial']['id'] in ['c001', 'c002', 'c003', 'c004']
    if method == 'gpt':
        assert {e['operator'] for e in candidates} == {'seed', 'mutation'}
        assert len(services['gpt'].requests) == 40
        seeds = services['gpt'].requests[:4]
        assert len({s.prompt for s in seeds}) == 1
        assert len({s.seed for s in seeds}) == 4
    else:
        assert len([e for e in candidates if e['operator'] == 'crossover']) == 3
    records = ''.join(p.read_text() for p in (tmp_path / f'als-{method}').rglob('*.json'))
    assert 'PRIVATE_CANARY' not in records
    assert len(result['header']['evidence_sha256']) == 64
    assert '[S1]' in services['gpt'].requests[0].prompt or '## S1' in services['gpt'].requests[0].prompt


def test_invalid_output_fails_without_format_repair_or_retry(tmp_path):
    result, services = execute(tmp_path, 'gpt', {'gpt': FakeBackend('gpt', malformed=True)})
    assert result['status'] == 'failed'
    assert 'final' not in result
    assert len(services['gpt'].requests) == 4
    assert not (tmp_path / 'als-gpt' / 'result.json').exists()


def test_judge_failure_preserves_initial_but_never_a_final(tmp_path):
    result, _ = execute(tmp_path, 'gpt', {'gpt': FakeBackend('gpt', fail_at=20)})
    assert result['status'] == 'failed'
    assert result['initial']
    assert 'final' not in result
    assert result['usage']['unknown_usage_calls'] == 1


def test_run_folder_reuse_is_refused_before_any_dispatch(tmp_path):
    _, services = execute(tmp_path, 'gpt')
    count = len(services['gpt'].requests)
    with pytest.raises(FileExistsError):
        execute(tmp_path, 'gpt', services)
    assert len(services['gpt'].requests) == count
