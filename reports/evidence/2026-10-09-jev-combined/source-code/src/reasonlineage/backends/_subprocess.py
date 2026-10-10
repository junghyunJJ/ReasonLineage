"""Shared plumbing for CLI backends: concurrency limit, retry, timeout with kill, structured output."""

import asyncio
import contextlib
import json
import os
import signal
import time
from pathlib import Path
from typing import Any, Mapping

from .base import BackendError, ModelRequest, ModelResponse, ProviderRefusal


class SubprocessBackend:
    def __init__(self, name: str, binary: str, max_concurrency: int, retries: int) -> None:
        self.name = name
        self.binary = binary
        self.retries = retries
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        errors = []
        for _ in range(self.retries + 1):
            try:
                async with self._semaphore:
                    return await self._run_once(request)
            except ProviderRefusal:
                raise
            except BackendError as exc:
                errors.append(str(exc))
        raise BackendError(f"{self.name}/{request.model} failed after {len(errors)} attempt(s): {errors}")

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    async def _exec(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        stdin: bytes | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = True,
    ) -> tuple[int, bytes, bytes, float]:
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            start_new_session=True,  # its own process group, so a stop reaches the CLI's children too
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(stdin), timeout_s)
        except asyncio.TimeoutError:
            await _kill_group(proc)
            raise BackendError(f"timed out after {timeout_s:.0f}s") from None
        except asyncio.CancelledError:
            # Cancelled because another call failed, or Ctrl-C: do not leave the CLI running.
            await _kill_group(proc)
            raise
        if check and proc.returncode != 0:
            detail = (stderr or stdout).decode(errors="replace").strip()[-500:]
            raise BackendError(f"exit {proc.returncode}: {detail}")
        return proc.returncode, stdout, stderr, time.monotonic() - started


async def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """Kill the CLI and every process it started.

    Killing only the CLI is not enough: a child of it (codex runs a native binary under a node wrapper) keeps
    stdout open, and the wait below then lasts until that child finishes on its own.
    """
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    await proc.wait()


def structured_data(request: ModelRequest, structured: Any, text: str) -> Mapping[str, Any] | None:
    """The schema-constrained object, from the CLI's structured field or else the reply text."""
    if request.json_schema is None:
        return None
    data = structured
    if data is None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise BackendError("json_schema was requested but no structured output came back") from None
    if not isinstance(data, dict):
        raise BackendError(f"structured output is not an object: {type(data).__name__}")
    return data


def response(backend: str, request: ModelRequest, text: str, data, duration_s: float, cost, raw) -> ModelResponse:
    return ModelResponse(
        backend=backend,
        model=request.model,
        text=text,
        data=data,
        duration_s=duration_s,
        cost_usd=cost,
        prompt_sha256=request.prompt_sha256,
        raw=raw,
    )
