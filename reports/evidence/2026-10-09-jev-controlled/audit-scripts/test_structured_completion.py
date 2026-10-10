import asyncio
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAIR = ROOT / 'runs/jev-controlled-2026-10-09'


def module():
    spec = importlib.util.spec_from_file_location('planned_step_completion', HERE / 'planned_step_completion.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_invalid_json_is_metered_and_retried_without_rewriting_previous_candidates(tmp_path, monkeypatch):
    from reasonlineage.backends.http import HttpBackend
    from reasonlineage.engine.calls import derive_seed
    mod = module()
    dest = tmp_path / 'pair'
    source = dest / 'jev-off/runs/als-glm'
    shutil.copytree(PAIR / 'jev-off/runs/als-glm', source)
    shutil.copytree(PAIR / 'jev-off/frozen-inputs', dest / 'jev-off/frozen-inputs')
    shutil.copytree(PAIR / 'planned-step-completions/jev-off-als-glm', dest / 'planned-step-completions/jev-off-als-glm')
    shutil.copyfile(PAIR / 'pair-plan.json', dest / 'pair-plan.json')
    (dest / 'pair-status.json').write_text(json.dumps({'status': 'partial', 'started_utc': datetime.now(timezone.utc).isoformat()}))
    monkeypatch.setattr(mod, 'DEST', dest)
    requests = []

    class Service(HttpBackend):
        def __init__(self):
            super().__init__('glm', 'http://unused')

        async def _run_once(self, request):
            requests.append(request)
            if len(requests) == 1:
                text = 'Invalid JSON response'
            elif 'answer' in request.json_schema['properties']:
                text = json.dumps({'answer': 'Supported premise, explicitly speculative mechanism, controlled test, falsifying observation. ' * 40,
                                   'ranking': [{'item': 'Completed scheduled hypothesis', 'promisingness': .7, 'confidence': .6, 'pmids': []}]})
            else:
                text = json.dumps({**{k: .9 for k in request.json_schema['properties'] if k != 'critique'},
                                   'critique': ['A public critique ' + str(request.seed)]})
            return self.parse({'model': request.model, 'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
                               'choices': [{'finish_reason': 'stop', 'message': {'content': text, 'reasoning': 'PRIVATE_SENTINEL'}}]}, request, .01)

    monkeypatch.setattr(mod, 'build_backend', lambda *a: Service())
    out = dest / 'structured-completions/jev-off-als-glm'
    result = asyncio.run(mod.execute(source, out, repair=True))
    assert result['status'] == 'planned_steps_complete'
    assert len(requests) == 6  # malformed writer + writer format retry + four original critics
    assert requests[0].seed == derive_seed(20261006, 'g3/mutate/c009/glm', 2)
    assert requests[1].seed == derive_seed(20261006, 'g3/mutate/c009/glm', 3)
    assert result['new_model_usage']['reported_tokens'] == 120
    assert result['new_model_usage']['unknown_usage_calls'] == 0
    assert result['cumulative_unknown_model_usage_calls'] == 2
    assert not result['cumulative_token_cap_verified']
    assert result['completed_planned_hypotheses'] == 1 and result['new_generations'] == 0
    assert json.loads((source / 'status.json').read_text())['status'] == 'failed'
    assert json.loads((dest / 'planned-step-completions/jev-off-als-glm/status.json').read_text())['status'] == 'partial'
    rows = [json.loads(s) for s in (out / 'events.jsonl').read_text().splitlines()]
    assert len([r for r in rows if r['event'] == 'candidate.created']) == 9
    assert len([r for r in rows if r['event'] == 'judge.scored']) == 18
    diagnostics = [json.loads(s) for s in (out / 'response-diagnostics.jsonl').read_text().splitlines()]
    assert diagnostics[0]['error_category'] == 'missing_structured_object'
    assert diagnostics[0]['usage']['total_tokens'] == 20
    assert 'PRIVATE_SENTINEL' not in ''.join(p.read_text() for p in out.rglob('*.json*'))


def test_truncated_http_reply_cannot_be_accepted_as_a_candidate(tmp_path):
    from reasonlineage.backends.base import ModelRequest
    from reasonlineage.backends.http import HttpBackend
    mod = module()
    backend = HttpBackend('glm', 'http://unused')
    mod.observe_structured_responses(backend, tmp_path)
    request = ModelRequest('system', 'prompt', 'glm', json_schema={'type': 'object'}, max_tokens=32768)
    reply = backend.parse({'usage': {'prompt_tokens': 10, 'completion_tokens': 32768, 'total_tokens': 32778},
                           'choices': [{'finish_reason': 'length', 'message': {'content': '{"answer":"truncated'}}]}, request, 1)
    assert reply.data is None and reply.text == ''
    assert reply.raw['usage']['total_tokens'] == 32778
    diagnostics = json.loads((tmp_path / 'response-diagnostics.jsonl').read_text())
    assert diagnostics['error_category'] == 'output_limit'
