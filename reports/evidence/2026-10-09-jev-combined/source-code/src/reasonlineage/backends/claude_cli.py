"""Claude through the headless Claude Code CLI (`claude -p`), using the local subscription login.

Each call is a fresh process with every customization and tool disabled and the
default system prompt replaced, so the model sees only `request.system` and
`request.prompt`. The prompt goes through stdin, never through a shell.
"""

import json

from ._subprocess import SubprocessBackend, response, structured_data
from .base import BackendError, ModelRequest, ModelResponse, ProviderRefusal


class ClaudeCLIBackend(SubprocessBackend):
    def __init__(self, name: str = "claude", binary: str = "claude", max_concurrency: int = 3, retries: int = 1) -> None:
        super().__init__(name, binary, max_concurrency, retries)

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

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        code, stdout, stderr, duration = await self._exec(
            self.build_argv(request), stdin=request.prompt.encode(), timeout_s=request.timeout_s, check=False
        )
        if code:
            try:
                payload = json.loads(stdout)
            except (ValueError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, dict) and payload.get('is_error'):
                # Read the typed result before generic subprocess truncation.
                return self.parse(stdout.decode(), request, duration)
            detail = (stderr or stdout).decode(errors='replace').strip()[-500:]
            raise BackendError(f'exit {code}: {detail}')
        return self.parse(stdout.decode(), request, duration)

    def parse(self, stdout: str, request: ModelRequest, duration_s: float) -> ModelResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            raise BackendError(f"output is not JSON: {stdout[:200]!r}") from None
        if payload.get("is_error") or payload.get("subtype") != "success":
            if '[bio]' in str(payload.get('result', '')).lower():
                raise ProviderRefusal('provider biology safeguard blocked request [bio]')
            raise BackendError(f"error payload: subtype={payload.get('subtype')!r} result={str(payload.get('result'))[:300]!r}")
        text = payload.get("result") or ""
        data = structured_data(request, payload.get("structured_output"), text)
        return response(self.name, request, text, data, duration_s, payload.get("total_cost_usd"), payload)
