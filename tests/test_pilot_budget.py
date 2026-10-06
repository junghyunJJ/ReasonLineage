import asyncio
import threading
from dataclasses import replace

import pytest

from reasonlineage.backends.base import BackendError, ModelRequest, ModelResponse
from reasonlineage.pilot.budget import Budget, MeteredBackend, usage_counts


@pytest.mark.parametrize('usage,want', [
    ({'input_tokens': 2, 'cache_creation_input_tokens': 1644, 'cache_read_input_tokens': 0, 'output_tokens': 2432}, (1646, 2432, 4078)),
    ({'input_tokens': 1219, 'cache_read_input_tokens': 1152, 'output_tokens': 6342, 'total_tokens': 8713, 'reasoning_tokens': 5526}, (2371, 6342, 8713)),
    ({'input_tokens': 5598, 'cached_input_tokens': 1000, 'output_tokens': 2725, 'reasoning_output_tokens': 2002}, (5598, 2725, 8323)),
    ({'prompt_tokens': 576, 'completion_tokens': 11123, 'total_tokens': 11699}, (576, 11123, 11699)),
])
def test_usage_accounts_for_cache_without_counting_reasoning_twice(usage, want):
    assert usage_counts(usage) == want


def test_missing_or_invalid_usage_is_not_claimed_as_zero_consumption():
    assert usage_counts({}) is None
    assert usage_counts({'input_tokens': True, 'output_tokens': 3}) is None
    assert usage_counts({'input_tokens': 10, 'output_tokens': -2}) is None


def test_budget_prevents_dispatch_after_call_token_or_time_limit():
    now = [0.0]
    budget = Budget(seconds=10, tokens=20, calls=2, clock=lambda: now[0])
    budget.reserve()
    budget.record((5, 6, 11))
    budget.reserve()
    budget.record((4, 5, 9))
    with pytest.raises(BackendError):
        budget.reserve()
    timed = Budget(seconds=10, clock=lambda: now[0])
    now[0] = 11
    with pytest.raises(BackendError):
        timed.reserve()


class Service:
    name = 'fake'

    def __init__(self, fail=False):
        self.requests = []
        self.fail = fail

    async def complete(self, request):
        self.requests.append(request)
        if self.fail:
            raise BackendError('refused: unsafe')
        return ModelResponse('fake', 'fake-model', 'public answer', {'answer': 'public answer'}, 0.1, None,
                             request.prompt_sha256, {'usage': {'input_tokens': 2, 'output_tokens': 3},
                                                     'reasoning': 'private chain', 'Authorization': 'secret'})


def test_metering_removes_private_provider_fields_and_counts_every_call():
    service = Service()
    local, shared = Budget(seconds=20), Budget(seconds=40)
    backend = MeteredBackend(service, local, shared)
    request = ModelRequest('s', 'p', 'fake-model', timeout_s=100)
    result = asyncio.run(backend.complete(request))
    assert result.text == 'public answer'
    assert 'reasoning' not in result.raw and 'Authorization' not in result.raw
    assert local.snapshot()['reported_tokens'] == 5
    assert shared.snapshot()['reported_tokens'] == 5
    assert service.requests[0].timeout_s <= 20


def test_persistable_usage_includes_cache_and_preserves_provider_counters():
    class Cached(Service):
        async def complete(self, request):
            response = await super().complete(request)
            return replace(response, raw={'usage': {'input_tokens': 2, 'cache_creation_input_tokens': 1644,
                                                   'cache_read_input_tokens': 0, 'output_tokens': 2432}})
    response = asyncio.run(MeteredBackend(Cached(), Budget(), Budget()).complete(ModelRequest('s', 'p', 'fake')))
    assert response.raw['usage']['input_tokens'] == 1646
    assert response.raw['usage']['total_tokens'] == 4078
    assert response.raw['provider_usage']['input_tokens'] == 2


def test_elapsed_time_does_not_hide_shutdown_after_deadline():
    now = [0.0]
    budget = Budget(seconds=10, clock=lambda: now[0])
    now[0] = 11
    assert budget.snapshot()['elapsed_seconds'] == 11


def test_failed_call_is_not_retried_and_has_unknown_consumption():
    service = Service(fail=True)
    local, shared = Budget(seconds=20), Budget(seconds=40)
    with pytest.raises(BackendError, match='refused'):
        asyncio.run(MeteredBackend(service, local, shared).complete(ModelRequest('s', 'p', 'fake-model')))
    assert len(service.requests) == 1
    assert local.snapshot()['unknown_usage_calls'] == 1


def test_timeout_cancels_inflight_service_and_does_not_dispatch_again():
    class Slow(Service):
        async def complete(self, request):
            self.requests.append(request)
            await asyncio.sleep(2)
    service = Slow()
    local, shared = Budget(seconds=0.02), Budget(seconds=5)
    backend = MeteredBackend(service, local, shared)
    with pytest.raises(BackendError, match='timeout'):
        asyncio.run(backend.complete(ModelRequest('s', 'p', 'fake-model')))
    with pytest.raises(BackendError):
        asyncio.run(backend.complete(ModelRequest('s', 'p', 'fake-model')))
    assert len(service.requests) == 1


def test_queued_calls_recheck_tokens_at_actual_admission():
    class Serial(Service):
        def __init__(self):
            super().__init__()
            self.semaphore = asyncio.Semaphore(1)

        async def complete(self, request):
            async with self.semaphore:
                await asyncio.sleep(.001)
                return await super().complete(request)
    service = Serial()
    local = Budget(tokens=1, calls=10)
    backend = MeteredBackend(service, local, Budget(calls=10))
    async def invoke():
        return await asyncio.gather(*(backend.complete(ModelRequest('s', 'p', 'fake')) for _ in range(5)),
                                    return_exceptions=True)
    outcomes = asyncio.run(invoke())
    assert len(service.requests) == 1
    assert len([r for r in outcomes if isinstance(r, BackendError)]) == 4
    assert local.calls_used == 1


def test_unknown_successful_usage_stops_new_token_bounded_dispatch():
    class Unreported(Service):
        async def complete(self, request):
            return replace(await super().complete(request), raw={})
    service = Unreported()
    backend = MeteredBackend(service, Budget(), Budget(tokens=None))
    async def invoke():
        first = await backend.complete(ModelRequest('s', 'p', 'fake'))
        assert first.text == 'public answer'
        with pytest.raises(BackendError, match='usage'):
            await backend.complete(ModelRequest('s', 'p', 'fake'))
    asyncio.run(invoke())
    assert len(service.requests) == 1


def test_cancelled_http_thread_retains_capacity_before_next_case_admission():
    from reasonlineage.backends.http import HttpBackend
    started, release = threading.Event(), threading.Event()
    class BlockingHTTP(HttpBackend):
        def __init__(self):
            super().__init__('http', 'http://unused', max_concurrency=1)
            self.calls = self.active = self.peak = 0
        def _send(self, path, body, timeout_s):
            self.calls += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                if self.calls == 1:
                    started.set()
                    release.wait(2)
                return {'choices': [{'message': {'content': 'public'}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
            finally:
                self.active -= 1
    service = BlockingHTTP()
    shared, next_budget = Budget(tokens=None), Budget()
    async def exercise():
        first = asyncio.create_task(MeteredBackend(service, Budget(), shared).complete(ModelRequest('s', 'p', 'fake')))
        await asyncio.to_thread(started.wait, 1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(MeteredBackend(service, next_budget, shared).complete(ModelRequest('s', 'p', 'fake')))
        try:
            await asyncio.sleep(.03)
            assert service.calls == 1
            assert next_budget.calls_used == 0
        finally:
            release.set()
            await second
        assert service.peak == 1
    asyncio.run(exercise())
