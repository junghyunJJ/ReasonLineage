"""xAI models through the `grok` CLI, using the local grok.com login.

Grok reads the user's global ~/.claude/CLAUDE.md and ~/.claude/skills even with
its system prompt overridden (`grok inspect`, 2026-09-27). Each call therefore
runs with HOME pointed at a clean directory that holds only a link to the real
auth.json, so no instructions, skills, plugins, MCP servers, or hooks load.
`--tools ""` does not empty the toolset, and with `--tools read_file` the model
still gets search_tool and use_tool and did call them when writing a long
answer. Allowing one tool and then disallowing it and both meta tools leaves
no tools at all (about 4k input tokens). Output is streamed as NDJSON: a
non-empty `available_commands` tool list or any `tool_call` event rejects the
call. A long xhigh answer can take two model calls without tools, so the turn
count is not treated as a tool signal.
"""

import atexit
import json
import os
import shutil
import tempfile
from pathlib import Path

from ._subprocess import SubprocessBackend, response, structured_data
from .base import BackendError, ModelRequest, ModelResponse

CLEAN_CONFIG = '[telemetry]\nenabled = false\n'


class GrokCLIBackend(SubprocessBackend):
    def __init__(
        self,
        name: str = "grok",
        binary: str = "grok",
        max_concurrency: int = 3,
        retries: int = 1,
        grok_home: Path | None = None,
    ) -> None:
        super().__init__(name, binary, max_concurrency, retries)
        self.clean_home = self._make_clean_home(grok_home or Path.home() / ".grok")

    @staticmethod
    def _make_clean_home(real_grok: Path) -> Path:
        auth = real_grok / "auth.json"
        if not auth.exists():
            raise BackendError(f"no grok login found at {auth}; run `grok login` first")
        home = Path(tempfile.mkdtemp(prefix="reasonlineage-grok-home-"))
        atexit.register(shutil.rmtree, home, ignore_errors=True)  # removes the link, not the real auth.json
        (home / ".grok").mkdir()
        (home / ".grok" / "auth.json").symlink_to(auth)
        if (real_grok / "agent_id").exists():
            (home / ".grok" / "agent_id").write_text((real_grok / "agent_id").read_text())
        (home / ".grok" / "config.toml").write_text(CLEAN_CONFIG)
        return home

    def build_argv(self, request: ModelRequest, prompt_file: Path) -> list[str]:
        argv = [
            self.binary,
            "--prompt-file", str(prompt_file),
            "-m", request.model,
            "--system-prompt-override", request.system,
            "--tools", "read_file",
            "--disallowed-tools", "read_file,search_tool,use_tool",
            "--disable-web-search", "--no-subagents", "--no-plan",
            "--output-format", "streaming-json",
        ]
        if request.effort:
            argv += ["--reasoning-effort", request.effort]
        if request.json_schema is not None:
            argv += ["--json-schema", json.dumps(request.json_schema)]
        return argv

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        with tempfile.TemporaryDirectory(prefix="reasonlineage-grok-") as tmp:
            workdir = Path(tmp) / "work"
            workdir.mkdir()
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text(request.prompt)
            env = {**os.environ, "HOME": str(self.clean_home)}
            _, stdout, _, duration = await self._exec(
                self.build_argv(request, prompt_file), cwd=workdir, env=env, timeout_s=request.timeout_s
            )
        return self.parse(stdout.decode(), request, duration)

    def parse(self, stdout: str, request: ModelRequest, duration_s: float) -> ModelResponse:
        text, end, tools, available, kinds = [], None, [], [], {}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            kinds[kind] = kinds.get(kind, 0) + 1
            if kind == "text":
                text.append(event.get("data", ""))
            elif kind == "available_commands":
                available += event.get("tools") or []
            elif kind == "tool_call":
                tools.append(event.get("toolName") or event.get("title"))
            elif kind == "end":
                end = event
        if tools or available:
            raise BackendError(f"isolation broken, tools available={sorted(set(available))} used={tools}")
        if end is None:
            raise BackendError(f"no end event in output: {stdout[-200:]!r}")
        if end.get("stopReason") not in (None, "end_turn"):
            raise BackendError(f"stopped early: {end.get('stopReason')!r}")
        reply = "".join(text)
        data = structured_data(request, end.get("structuredOutput"), reply)
        return response(self.name, request, reply, data, duration_s, end.get("total_cost_usd"), {**end, "event_counts": kinds})
