"""OpenAI models through `codex exec`, using the local ChatGPT login.

Codex is an agent: by default it runs shell commands and web searches on its own
(a probe on 2026-09-27 did both for a one-line scoring prompt). Each call here
ignores the user config and rules, replaces the built-in instructions, disables
web search and every tool feature, runs read-only in an empty directory, and is
rejected if the event stream shows any item besides the reply or reasoning.
"""

import json
import tempfile
from pathlib import Path

from ._subprocess import SubprocessBackend, response, structured_data
from .base import BackendError, ModelRequest, ModelResponse

DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "multi_agent", "plugins", "apps", "browser_use",
    "browser_use_external", "computer_use", "image_generation", "hooks", "view_image",
    "sleep_tool", "tool_suggest", "skill_search", "goals", "personality",
)
ALLOWED_ITEMS = frozenset({"agent_message", "reasoning"})


class CodexCLIBackend(SubprocessBackend):
    def __init__(self, name: str = "codex", binary: str = "codex", max_concurrency: int = 3, retries: int = 1) -> None:
        super().__init__(name, binary, max_concurrency, retries)

    def build_argv(self, request: ModelRequest, workdir: Path, instructions: Path, schema: Path | None, last: Path) -> list[str]:
        argv = [
            self.binary, "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only",
            "-C", str(workdir),
            "-m", request.model,
            "-c", f"model_instructions_file={json.dumps(str(instructions))}",
            "-c", 'web_search="disabled"',
            "-c", "project_doc_max_bytes=0",
            "-o", str(last),
        ]
        if request.effort:
            argv += ["-c", f"model_reasoning_effort={json.dumps(request.effort)}"]
        for feature in DISABLED_FEATURES:
            argv += ["--disable", feature]
        if schema is not None:
            argv += ["--output-schema", str(schema)]
        return argv + ["-"]  # prompt from stdin

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        with tempfile.TemporaryDirectory(prefix="reasonlineage-codex-") as tmp:
            tmp = Path(tmp)
            workdir = tmp / "work"
            workdir.mkdir()
            instructions = tmp / "instructions.txt"
            instructions.write_text(request.system)
            schema = None
            if request.json_schema is not None:
                schema = tmp / "schema.json"
                schema.write_text(json.dumps(request.json_schema))
            last = tmp / "last_message.txt"
            argv = self.build_argv(request, workdir, instructions, schema, last)
            code, stdout, stderr, duration = await self._exec(
                argv, stdin=request.prompt.encode(), cwd=workdir, timeout_s=request.timeout_s, check=False
            )
            last_text = last.read_text() if last.exists() else None
        return self.parse(stdout.decode(errors="replace"), last_text, code, stderr.decode(errors="replace"), request, duration)

    def parse(self, stdout: str, last_text: str | None, code: int, stderr: str, request: ModelRequest, duration_s: float) -> ModelResponse:
        items, usage, failure, messages = {}, None, None, []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind in {"turn.failed", "error"}:
                failure = failure or str(event.get("error", {}).get("message") or event.get("message"))
            elif kind == "turn.completed":
                usage = event.get("usage")
            elif kind == "item.completed":
                item = event.get("item") or {}
                items[item.get("type")] = items.get(item.get("type"), 0) + 1
                if item.get("type") == "agent_message":
                    messages.append(item.get("text", ""))
        if failure:
            raise BackendError(f"turn failed: {failure[:400]}")
        if code != 0:
            raise BackendError(f"exit {code}: {stderr.strip()[-400:]}")
        tools = sorted(t for t in items if t not in ALLOWED_ITEMS)
        if tools:
            raise BackendError(f"isolation broken, model used tools: {tools}")
        text = last_text if last_text is not None else (messages[-1] if messages else "")
        data = structured_data(request, None, text)
        return response(self.name, request, text, data, duration_s, None, {"usage": usage or {}, "items": items})
