import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest

from reasonlineage.backends.base import BackendError, ModelRequest, ModelResponse, ProviderRefusal
from reasonlineage.engine.answer import normalize_answer
from reasonlineage.engine.calls import CallRecorder, call_file
from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import EventLog, read_events
from reasonlineage.pilot.budget import Budget, MeteredBackend, public_data
from reasonlineage.pilot.run import run_case
from reasonlineage.protocol import load_protocol

ROOT = Path(__file__).resolve().parents[1]
NAME = 'g0/write/c001/glm'


class PublicService:
    name = 'glm'

    def __init__(self, *, malformed=0, failure=None):
        self.requests = []
        self.malformed = malformed
        self.failure = failure

    async def complete(self, request):
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        if 'answer' in (request.json_schema or {}).get('properties', {'answer': {}}):
            title = 'Testable transport hypothesis'
            data = {'answer': title + '. Supported premise [S1].' + ' A matched control tests the premise.' * 70,
                    'ranking': [{'item': title, 'promisingness': .7, 'confidence': .6, 'pmids': []}]}
            if len(self.requests) <= self.malformed:
                data['answer'] = ['malformed public answer', 'Bearer abcdefghijklmnopqrstuvwxyz']
        else:
            data = {key: .72 for key in request.json_schema['properties'] if key != 'critique'}
            data['critique'] = ['Separate premise from assumption.']
        return ModelResponse(self.name, request.model, '<think>PRIVATE_CANARY</think>' + json.dumps(data), data, .01, None,
                             request.prompt_sha256, {'usage': {'input_tokens': 10, 'output_tokens': 15},
                                                     'reasoning': 'PRIVATE_CANARY', 'Authorization': 'SECRET_CANARY'})


def usable(response):
    normalize_answer(response.data, None)


def format_recorder(tmp_path, **overrides):
    events = EventLog(tmp_path / 'events.jsonl')
    options = {'attempts': 2, 'retry_backend_errors': False, 'unusable_sanitizer': public_data, **overrides}
    return CallRecorder(tmp_path, events, 7, **options)


def test_malformed_public_response_is_audited_then_one_usable_answer_is_saved(tmp_path):
    service = PublicService(malformed=1)
    local = Budget(seconds=100)
    backend = MeteredBackend(service, local, Budget(seconds=100))
    recorder = format_recorder(tmp_path)
    request = ModelRequest('public system', 'public question Bearer abcdefghijklmnopqrstuvwxyz', 'fake-glm')

    response = asyncio.run(recorder.call(NAME, 'glm', backend, request, check=usable))

    assert isinstance(response.data['answer'], str)
    assert local.snapshot()['backend_calls'] == 2
    assert len(service.requests) == 2
    first, second = service.requests
    assert (first.system, first.prompt, first.model, first.json_schema) == (
        second.system, second.prompt, second.model, second.json_schema)
    assert first.seed != second.seed
    records = read_events(tmp_path / 'events.jsonl')
    assert [entry['event'] for entry in records] == ['call.failed', 'call.completed']
    saved = json.loads(call_file(tmp_path, NAME).read_text())
    assert isinstance(saved['response']['data']['answer'], str)
    audits = list((tmp_path / 'unusable').rglob('*.json'))
    assert len(audits) == 1
    audit = json.loads(audits[0].read_text())
    assert audit['attempt'] == 0
    assert audit['request']['seed'] == first.seed
    assert audit['response']['data']['answer'] == ['malformed public answer', '[REDACTED_CREDENTIAL]']
    assert audit['request']['prompt'] == 'public question [REDACTED_CREDENTIAL]'
    assert 'PRIVATE_CANARY' not in audits[0].read_text()
    assert 'SECRET_CANARY' not in audits[0].read_text()
    assert records[0]['file'] == audits[0].relative_to(tmp_path).as_posix()


@pytest.mark.parametrize('error', [
    BackendError('timeout'),
    BackendError('HTTP 401 authentication failed'),
    BackendError('provider capacity or rate limit'),
    ProviderRefusal('provider biology safeguard blocked request [bio]'),
])
def test_format_recovery_never_retries_backend_failures(tmp_path, error):
    service = PublicService(failure=error)
    local = Budget(seconds=100)
    backend = MeteredBackend(service, local, Budget(seconds=100))
    recorder = format_recorder(tmp_path)

    with pytest.raises(BackendError):
        asyncio.run(recorder.call(NAME, 'glm', backend, ModelRequest('s', 'p', 'fake'), check=usable))

    assert len(service.requests) == local.snapshot()['backend_calls'] == 1
    assert local.snapshot()['unknown_usage_calls'] == 1
    assert [entry['event'] for entry in read_events(tmp_path / 'events.jsonl')] == ['call.failed', 'call.gave_up']
    assert not (tmp_path / 'unusable').exists()
    assert not call_file(tmp_path, NAME).exists()


def test_default_recorder_stops_provider_refusal_without_retry(tmp_path):
    service = PublicService(failure=ProviderRefusal('provider safeguard refused request'))
    recorder = CallRecorder(tmp_path, EventLog(tmp_path / 'events.jsonl'), 7)

    with pytest.raises(ProviderRefusal):
        asyncio.run(recorder.call(NAME, 'glm', service, ModelRequest('s', 'p', 'fake'), check=usable))

    assert len(service.requests) == 1
    assert [entry['event'] for entry in read_events(tmp_path / 'events.jsonl')] == ['call.failed', 'call.gave_up']


@pytest.mark.parametrize('marker', ['refusal', 'content_filter'])
@pytest.mark.parametrize('format_only', [False, True])
def test_explicit_returned_refusal_stops_without_retry_or_candidate(tmp_path, marker, format_only):
    class ExplicitRefusal(PublicService):
        async def complete(self, request):
            response = await super().complete(request)
            if marker == 'refusal':
                return replace(response, data={'refusal': 'Cannot assist with this request'})
            return replace(response, raw={**response.raw, 'finish_reason': 'content_filter'})

    service = ExplicitRefusal()
    local = Budget(seconds=100)
    backend = MeteredBackend(service, local, Budget(seconds=100))
    recorder = format_recorder(tmp_path) if format_only else CallRecorder(tmp_path, EventLog(tmp_path / 'events.jsonl'), 7)

    with pytest.raises(ProviderRefusal):
        asyncio.run(recorder.call(NAME, 'glm', backend, ModelRequest('s', 'p', 'fake'), check=usable))

    assert len(service.requests) == local.snapshot()['backend_calls'] == 1
    assert not call_file(tmp_path, NAME).exists()
    assert [entry['event'] for entry in read_events(tmp_path / 'events.jsonl')] == ['call.failed', 'call.gave_up']


def test_two_malformed_responses_exhaust_the_only_format_retry(tmp_path):
    service = PublicService(malformed=3)
    backend = MeteredBackend(service, Budget(seconds=100), Budget(seconds=100))

    with pytest.raises(BackendError, match='2 attempt'):
        asyncio.run(format_recorder(tmp_path).call(NAME, 'glm', backend, ModelRequest('s', 'p', 'fake'), check=usable))

    assert len(service.requests) == 2
    assert not call_file(tmp_path, NAME).exists()
    assert len(list((tmp_path / 'unusable').rglob('*.json'))) == 2


def test_call_cap_blocks_retry_before_an_extra_service_invocation(tmp_path):
    service = PublicService(malformed=1)
    local = Budget(seconds=100, calls=1)
    backend = MeteredBackend(service, local, Budget(seconds=100))

    with pytest.raises(BackendError, match='call limit'):
        asyncio.run(format_recorder(tmp_path).call(NAME, 'glm', backend, ModelRequest('s', 'p', 'fake'), check=usable))

    assert len(service.requests) == local.snapshot()['backend_calls'] == 1
    assert not call_file(tmp_path, NAME).exists()
    assert len(list((tmp_path / 'unusable').rglob('*.json'))) == 1


def test_relaxed_actual_invocations_stop_at_forty_including_format_retries(tmp_path):
    class OneMalformedPerQuestion(PublicService):
        def __init__(self):
            super().__init__()
            self.questions = set()

        async def complete(self, request):
            self.malformed = len(self.requests) + 1 if request.prompt not in self.questions else 0
            self.questions.add(request.prompt)
            return await super().complete(request)

    policy = load_protocol(ROOT / 'research/co-scientist-pilot/protocol-relaxed').data['pilot']
    local = Budget(seconds=100, calls=policy['call_limit'])
    service = OneMalformedPerQuestion()
    backend = MeteredBackend(service, local, Budget(seconds=100, calls=100))
    recorder = format_recorder(tmp_path)

    async def invoke():
        for index in range(20):
            response = await recorder.call(f'g0/write/c{index:03d}/glm', 'glm', backend,
                                           ModelRequest('s', f'question {index}', 'fake'), check=usable)
            assert isinstance(response.data['answer'], str)
        with pytest.raises(BackendError, match='call limit'):
            await recorder.call('g0/write/c020/glm', 'glm', backend, ModelRequest('s', 'question 20', 'fake'), check=usable)

    asyncio.run(invoke())

    assert len(service.requests) == local.snapshot()['backend_calls'] == 40
    assert len(list((tmp_path / 'calls').rglob('*.json'))) == 20
    assert len(list((tmp_path / 'unusable').rglob('*.json'))) == 20


@pytest.mark.parametrize('protocol_directory,want_status,want_calls,want_limit', [
    ('protocol-relaxed', 'completed', 31, 40),
    ('protocol', 'failed', 4, 40),
])
def test_only_relaxed_pilot_recovers_a_malformed_seed(tmp_path, protocol_directory, want_status, want_calls, want_limit):
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    service = PublicService(malformed=1)
    run_dir = tmp_path / 'run'

    result = asyncio.run(run_case(run_dir, 'als', 'glm', setup, {'glm': service}, Budget(seconds=100),
                                 root=ROOT, protocol_directory=protocol_directory))

    assert result['status'] == want_status
    assert len(service.requests) == result['usage']['backend_calls'] == want_calls
    assert result['header']['budgets']['call_limit'] == want_limit
    events = read_events(run_dir / 'events.jsonl')
    candidates = [entry for entry in events if entry['event'] == 'candidate.created']
    if protocol_directory == 'protocol-relaxed':
        assert len(candidates) == 10
        assert len([entry for entry in events if entry['event'] == 'judge.scored']) == 20
        assert len([entry for entry in events if entry['event'] == 'call.completed']) == 30
        assert len(list((run_dir / 'unusable').rglob('*.json'))) == 1
        assert not any('realign' in entry.get('name', '') or 'rewrite' in entry.get('name', '') for entry in events)
    else:
        assert not candidates
        assert not (run_dir / 'unusable').exists()
