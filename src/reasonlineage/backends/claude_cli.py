"""Claude through the headless Claude Code CLI (`claude -p`), using the local subscription login.

Each call is a fresh process with every customization and tool disabled and the
default system prompt replaced, so the model sees only `request.system` and
`request.prompt`. The prompt goes through stdin, never through a shell.
"""

import asyncio
import json
import time

from .base import BackendError, ModelRequest, ModelResponse


class ClaudeCLIBackend:
    def __init__(
        self,
        name: str = "claude",
        binary: str = "claude",
        max_concurrency: int = 3,
        retries: int = 1,
    ) -> None:
        self.name = name
        self.binary = binary
        self.retries = retries
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def build_argv(self, request: ModelRequest) -> list[str]:
        argv = [
            self.binary, "-p",
            "--model", request.model,
            "--output-format", "json",
            "--safe-mode",
            "--tools", "",
            "--no-session-persistence",
            "--system-prompt", request.system,
        ]
        if request.effort:
            argv += ["--effort", request.effort]
        if request.json_schema is not None:
            argv += ["--json-schema", json.dumps(request.json_schema)]
        return argv

    async def complete(self, request: ModelRequest) -> ModelResponse:
        errors = []
        for _ in range(self.retries + 1):
            try:
                async with self._semaphore:
                    return await self._run_once(request)
            except BackendError as exc:
                errors.append(str(exc))
        raise BackendError(f"{self.name}/{request.model} failed after {len(errors)} attempt(s): {errors}")

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *self.build_argv(request),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(request.prompt.encode()), request.timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise BackendError(f"timed out after {request.timeout_s:.0f}s") from None
        if proc.returncode != 0:
            detail = (stderr or stdout).decode(errors="replace").strip()[-500:]
            raise BackendError(f"exit {proc.returncode}: {detail}")
        return self.parse(stdout.decode(), request, time.monotonic() - started)

    def parse(self, stdout: str, request: ModelRequest, duration_s: float) -> ModelResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            raise BackendError(f"output is not JSON: {stdout[:200]!r}") from None
        if payload.get("is_error") or payload.get("subtype") != "success":
            raise BackendError(f"error payload: subtype={payload.get('subtype')!r} result={str(payload.get('result'))[:300]!r}")

        text = payload.get("result") or ""
        data = None
        if request.json_schema is not None:
            data = payload.get("structured_output")
            if data is None:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    raise BackendError("json_schema was requested but no structured output came back") from None
            if not isinstance(data, dict):
                raise BackendError(f"structured output is not an object: {type(data).__name__}")

        return ModelResponse(
            backend=self.name,
            model=request.model,
            text=text,
            data=data,
            duration_s=duration_s,
            cost_usd=payload.get("total_cost_usd"),
            prompt_sha256=request.prompt_sha256,
            raw=payload,
        )
