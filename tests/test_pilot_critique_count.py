import asyncio
from dataclasses import replace

import pytest

from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case
from test_pilot_run import FakeBackend, ROOT


POINTS = ['Check prior AML studies.', 'Measure free marrow exposure.',
          'Test physiological uridine salvage.', 'Clarify differentiation endpoints.']


class FourPoints(FakeBackend):
    async def complete(self, request):
        response = await super().complete(request)
        if 'critique' in request.json_schema['properties']:
            return replace(response, data={**response.data, 'critique': POINTS})
        return response


def test_relaxed_preserves_four_valid_points_without_extra_calls(tmp_path):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    result = asyncio.run(run_case(tmp_path / 'run', 'aml', 'glm', setup,
                                 {'glm': FourPoints('glm')}, Budget(seconds=100),
                                 root=ROOT, protocol_directory='protocol-relaxed'))
    assert result['status'] == 'completed'
    assert result['usage']['backend_calls'] == 30
    events = read_events(tmp_path / 'run/events.jsonl')
    judgments = [e for e in events if e['event'] == 'judge.scored']
    assert len(judgments) == 20
    assert all(e['critique'] == POINTS for e in judgments)
    assert len([e for e in events if e['event'] == 'anomaly' and e['kind'] == 'critique_count']) == 20
    assert not any(e['event'] == 'call.failed' for e in events)


def test_strict_critique_count_contract_is_preserved(tmp_path):
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    result = asyncio.run(run_case(tmp_path / 'run', 'aml', 'glm', setup,
                                 {'glm': FourPoints('glm')}, Budget(seconds=100), root=ROOT))
    assert result['status'] == 'failed'
    assert '1-3 critique strings' in result['reason']


@pytest.mark.parametrize('bad_kind', ['score', 'empty_point'])
def test_advisory_count_preserves_score_and_content_validation(tmp_path, bad_kind):
    class Invalid(FourPoints):
        async def complete(self, request):
            response = await super().complete(request)
            if 'critique' in request.json_schema['properties']:
                data = dict(response.data)
                if bad_kind == 'score':
                    data['evidenceCoverage'] = 1.1
                else:
                    data['critique'] = POINTS + [' ']
                return replace(response, data=data)
            return response
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    result = asyncio.run(run_case(tmp_path / 'run', 'aml', 'glm', setup,
                                 {'glm': Invalid('glm')}, Budget(seconds=100),
                                 root=ROOT, protocol_directory='protocol-relaxed'))
    assert result['status'] == 'failed'
