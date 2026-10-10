"""Meter checker requests separately; credentials never enter the recorder."""
import asyncio
import json
import time
from pathlib import Path

from ..checks.base import CheckerError
from ..checks.calibration import VERSION
from ..checks.credentials import read_dotenv_key, shared_dotenv
from ..checks.jev import JevChecker
from ..engine.errors import RunStopped
from .budget import BudgetExceeded, usage_counts, public_data


class CheckerVersionMismatch(RunStopped):
    """A checker model change stops all remaining study slots."""


def live_checker(root):
    return JevChecker(read_dotenv_key(shared_dotenv(root)), VERSION, data_sensitivity='public')


class MeteredChecker:
    def __init__(self, service, local, shared, model_budget, run_dir):
        self.service, self.local, self.shared, self.model_budget = service, local, shared, model_budget
        self.name, self.pinned_version = service.name, VERSION
        self.admission = asyncio.Semaphore(2)
        self.path = Path(run_dir) / 'checker-calls.jsonl'

    def _append(self, record):
        with self.path.open('a', encoding='utf-8') as file:
            file.write(json.dumps(public_data(record), ensure_ascii=False, allow_nan=False) + '\n')

    async def ask(self, state, questions):
        async with self.admission:
            if self.local.started is None and self.model_budget.started is not None:
                self.local.started = self.model_budget.started
            try:
                self.local.check()
                self.shared.check()
                if self.model_budget.remaining <= 0:
                    raise BudgetExceeded('case timeout')
            except BudgetExceeded:
                raise RunStopped('jev checker budget exhausted') from None
            for budget in (self.local, self.shared):
                budget.start()
                budget.calls_used += 1
            call, started = self.local.calls_used, time.monotonic()
            self._append({'event': 'checker.started', 'call': call, 'state': state,
                          'questions': [q.to_dict() for q in questions]})
            timeout = min(120, self.local.remaining, self.shared.remaining, self.model_budget.remaining)
            try:
                result = await asyncio.wait_for(self.service.ask(state, questions), timeout)
            except BaseException as error:
                for budget in (self.local, self.shared):
                    budget.record(None)
                self._append({'event': 'checker.failed', 'call': call, 'usage': None,
                              'error': 'checker request failed; external details suppressed'})
                if isinstance(error, asyncio.CancelledError):
                    raise
                if not isinstance(error, Exception):
                    raise
                raise CheckerError('jev checker request failed; external details suppressed') from None
            counts = usage_counts(result.usage or {})
            for budget in (self.local, self.shared):
                budget.record(counts)
            self._append({'event': 'checker.completed', 'call': call, 'model': result.model,
                          'answers': {name: a.to_dict() for name, a in result.answers.items()},
                          'usage': result.usage, 'elapsed_seconds': round(time.monotonic()-started, 3)})
            if result.model != self.pinned_version:
                raise CheckerVersionMismatch('jev answered with a different pinned version')
            return result
