"""Bounded model calls and a public-only recording boundary."""

import asyncio
import re
import time
from dataclasses import replace
from typing import Any, Callable, Mapping

from ..backends.base import BackendError, ModelRequest, ModelResponse


class BudgetExceeded(BackendError):
    pass


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def usage_counts(usage: Mapping[str, Any]) -> tuple[int, int, int] | None:
    """Prefer inclusive provider totals; separate cache counters otherwise.

    cached_input_tokens and reasoning counters are subsets, not additions.
    Claude/Grok's cache_read/creation_input_tokens are separate input counts.
    """
    incoming = usage.get('input_tokens', usage.get('prompt_tokens'))
    outgoing = usage.get('output_tokens', usage.get('completion_tokens'))
    if not _integer(outgoing):
        return None
    total = usage.get('total_tokens')
    if total is not None:
        if not _integer(total) or total < outgoing:
            return None
        if incoming is not None and not _integer(incoming):
            return None
        return total - outgoing, outgoing, total
    if not _integer(incoming):
        return None
    for key in ('cache_creation_input_tokens', 'cache_read_input_tokens'):
        value = usage.get(key, 0)
        if not _integer(value):
            return None
        incoming += value
    return incoming, outgoing, incoming + outgoing


_CREDENTIAL = re.compile(r'apikey_[A-Za-z0-9_]{16,}|\bsk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}')
_THINK = re.compile(r'<think>.*?</think>', re.S | re.I)
_PRIVATE_KEYS = {'reasoning', 'reasoning_content', 'chain_of_thought', 'analysis', 'authorization', 'api_key'}


def public_data(value: Any) -> Any:
    if isinstance(value, str):
        return _CREDENTIAL.sub('[REDACTED_CREDENTIAL]', _THINK.sub('', value))
    if isinstance(value, list):
        return [public_data(item) for item in value]
    if isinstance(value, Mapping):
        return {key: public_data(item) for key, item in value.items() if str(key).lower() not in _PRIVATE_KEYS}
    return value


def safe_error(error: BaseException) -> str:
    """Do not persist arbitrary provider payload/stdout excerpts."""
    message = str(error).lower()
    if isinstance(error, BudgetExceeded):
        return str(error)
    if '[bio]' in message or 'biology safeguard' in message:
        return 'provider biology safeguard blocked request [bio]'
    if any(word in message for word in ('refus', 'safety', 'cannot assist', 'declin')):
        return 'provider refused request'
    if 'timeout' in message or 'timed out' in message:
        return 'backend timeout'
    status = re.search(r'http\s+(\d{3})', message)
    if status:
        return 'backend HTTP ' + status.group(1)
    if any(word in message for word in ('json', 'structured', 'schema', 'unusable', 'length', 'cut off')):
        return 'invalid or truncated structured response'
    if 'capacity' in message or 'rate limit' in message:
        return 'provider capacity or rate limit'
    exit_code = re.search(r'exit\s+(-?\d+)', message)
    if exit_code:
        return 'backend exit ' + exit_code.group(1)
    return type(error).__name__ + ': backend failure'


class Budget:
    def __init__(self, *, seconds: float = 1200, tokens: int | None = 400000,
                 calls: int | None = 40, clock: Callable[[], float] = time.monotonic,
                 lazy: bool = False) -> None:
        if seconds <= 0 or (tokens is not None and tokens < 1) or (calls is not None and calls < 1):
            raise ValueError('budget limits must be positive')
        self.seconds, self.tokens, self.calls = seconds, tokens, calls
        self.clock = clock
        self.started = None if lazy else clock()
        self.calls_used = self.reported_input = self.reported_output = self.reported_tokens = self.unknown = 0

    def start(self) -> None:
        if self.started is None:
            self.started = self.clock()

    @property
    def remaining(self) -> float:
        return self.seconds if self.started is None else max(0.0, self.seconds - (self.clock() - self.started))

    def check(self) -> None:
        if self.remaining <= 0:
            raise BudgetExceeded('budget timeout limit')
        if self.calls is not None and self.calls_used >= self.calls:
            raise BudgetExceeded('budget call limit')
        if self.tokens is not None and self.reported_tokens >= self.tokens:
            raise BudgetExceeded('budget token limit')
        if self.tokens is not None and self.unknown:
            raise BudgetExceeded('budget usage unavailable; token cap cannot be verified')

    def reserve(self) -> None:
        self.check()
        self.start()
        self.calls_used += 1

    def record(self, counts: tuple[int, int, int] | None) -> None:
        if counts is None:
            self.unknown += 1
        else:
            self.reported_input += counts[0]
            self.reported_output += counts[1]
            self.reported_tokens += counts[2]

    def snapshot(self) -> dict[str, Any]:
        return {'backend_calls': self.calls_used, 'reported_input_tokens': self.reported_input,
                'reported_output_tokens': self.reported_output, 'reported_tokens': self.reported_tokens,
                'unknown_usage_calls': self.unknown, 'elapsed_seconds': round(0.0 if self.started is None else self.clock() - self.started, 3),
                'remaining_seconds': round(self.remaining, 3), 'token_limit': self.tokens,
                'call_limit': self.calls, 'seconds_limit': self.seconds}


def _numeric_tree(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: cleaned for key, item in value.items() if (cleaned := _numeric_tree(item)) is not None}
    return value if _integer(value) else None


class MeteredBackend:
    def __init__(self, service, local: Budget, shared: Budget, *, concurrency: int = 1) -> None:
        self.service, self.local, self.shared = service, local, shared
        self.name = service.name
        # Match the underlying service's capacity, so it has no hidden queue.
        self.admission = asyncio.Semaphore(concurrency)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        async with self.admission:
            return await self._complete_admitted(request)

    async def _complete_admitted(self, request: ModelRequest) -> ModelResponse:
        # Both checks occur before either counter changes; no await between them.
        self.local.check()
        self.shared.check()
        for budget in (self.local, self.shared):
            budget.start()
            budget.calls_used += 1
        timeout = min(request.timeout_s, self.local.remaining, self.shared.remaining)
        try:
            response = await asyncio.wait_for(self.service.complete(replace(request, timeout_s=timeout)), timeout)
        except asyncio.TimeoutError:
            self.local.record(None)
            self.shared.record(None)
            raise BudgetExceeded('model timeout at remaining budget') from None
        except asyncio.CancelledError:
            self.local.record(None)
            self.shared.record(None)
            raise
        except Exception as error:
            self.local.record(None)
            self.shared.record(None)
            raise BackendError(safe_error(error)) from None
        raw = response.raw or {}
        usage = raw.get('usage') or {}
        counts = usage_counts(usage) if isinstance(usage, Mapping) else None
        self.local.record(counts)
        self.shared.record(counts)
        kept = {'provider_usage': _numeric_tree(usage)} if usage else {}
        if counts is not None:
            kept['usage'] = dict(zip(('input_tokens', 'output_tokens', 'total_tokens'), counts))
        for key in ('finish_reason', 'served_model'):
            if key in raw:
                kept[key] = public_data(raw[key])
        return replace(response, text=public_data(response.text), data=public_data(response.data), raw=kept)
