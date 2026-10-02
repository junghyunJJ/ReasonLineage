"""CodexCLIBackend and GrokCLIBackend against fake executables (no network, no login)."""

import asyncio
import json
import sys

import pytest

from reasonlineage.backends import BackendError, CodexCLIBackend, GrokCLIBackend, ModelRequest

SCHEMA = {"type": "object", "properties": {"score": {"type": "number"}}, "required": ["score"]}

FAKE_CODEX = """#!{python}
import json, os, sys
args = sys.argv[1:]
prompt = sys.stdin.read()
mode = os.environ.get("FAKE_MODE", "ok")
last = args[args.index("-o") + 1]
def emit(event): print(json.dumps(event))
emit({{"type": "thread.started"}})
emit({{"type": "turn.started"}})
if mode == "fail":
    emit({{"type": "turn.failed", "error": {{"message": "model not supported"}}}})
    sys.exit(1)
if mode == "tool":
    emit({{"type": "item.completed", "item": {{"type": "web_search", "query": "x"}}}})
reply = json.dumps({{"echo": prompt, "cwd_empty": os.listdir(".") == []}})
emit({{"type": "item.completed", "item": {{"type": "agent_message", "text": reply}}}})
emit({{"type": "turn.completed", "usage": {{"input_tokens": 5000, "output_tokens": 10}}}})
open(last, "w").write(reply)
"""

FAKE_GROK = """#!{python}
import json, os, sys
args = sys.argv[1:]
prompt = open(args[args.index("--prompt-file") + 1]).read()
home = os.environ["HOME"]
mode = os.environ.get("FAKE_MODE", "ok")
reply = json.dumps({{"echo": prompt, "claude_visible": os.path.exists(os.path.join(home, ".claude")),
                    "auth_linked": os.path.islink(os.path.join(home, ".grok", "auth.json"))}})
def emit(event): print(json.dumps(event))
emit({{"type": "available_commands", "tools": ["read_file"] if mode == "tool" else []}})
if mode == "tool":
    emit({{"type": "tool_call", "toolName": "read_file", "rawInput": {{"target_file": "/etc/hosts"}}}})
for i in range(0, len(reply), 7):
    emit({{"type": "text", "data": reply[i:i + 7]}})
turns = 2 if mode == "continuation" else 1
emit({{"type": "end", "stopReason": "end_turn", "num_turns": turns, "structuredOutput": json.loads(reply),
      "usage": {{"input_tokens": 6000}}, "total_cost_usd": 0.02}})
"""


def fake(tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source.format(python=sys.executable))
    path.chmod(0o755)
    return str(path)


def request(**overrides):
    base = {"system": "You are a strict evaluator.", "prompt": 'say "hi" $(whoami)', "model": "m", "json_schema": SCHEMA}
    return ModelRequest(**{**base, **overrides})


@pytest.fixture
def grok_login(tmp_path):
    real = tmp_path / "real_grok"
    real.mkdir()
    (real / "auth.json").write_text("{}")
    return real


# --- Codex ---

def test_codex_argv_disables_config_tools_and_web(tmp_path):
    argv = CodexCLIBackend().build_argv(request(effort="xhigh"), tmp_path, tmp_path / "i.txt", tmp_path / "s.json", tmp_path / "o.txt")
    for flag in ["--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"]:
        assert flag in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert 'web_search="disabled"' in argv
    assert 'model_reasoning_effort="xhigh"' in argv
    assert "shell_tool" in argv and "multi_agent" in argv
    assert argv[-1] == "-"


def test_codex_waits_on_a_silent_stream_as_long_as_the_call_may_run(tmp_path):
    # Codex dropped GPT's long silent reasoning at its default stream idle limit ("idle timeout waiting for
    # websocket", 2026-10-01). The built-in provider cannot be changed, so calls use a copy of it whose idle
    # limit is the call's own timeout.
    argv = CodexCLIBackend().build_argv(request(timeout_s=3600), tmp_path, tmp_path / "i.txt", None, tmp_path / "o.txt")
    assert 'model_provider="openai-long-idle"' in argv
    (provider,) = [a for a in argv if a.startswith("model_providers.openai-long-idle=")]
    assert 'base_url="https://chatgpt.com/backend-api/codex"' in provider and "requires_openai_auth=true" in provider
    assert 'wire_api="responses"' in provider and "stream_idle_timeout_ms=3600000" in provider


def test_codex_reply_comes_back_through_an_empty_workdir(tmp_path):
    backend = CodexCLIBackend(binary=fake(tmp_path, "codex", FAKE_CODEX))
    response = asyncio.run(backend.complete(request()))
    assert response.data == {"echo": 'say "hi" $(whoami)', "cwd_empty": True}
    assert response.raw["usage"]["input_tokens"] == 5000


def test_codex_tool_use_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "tool")
    backend = CodexCLIBackend(binary=fake(tmp_path, "codex", FAKE_CODEX), retries=0)
    with pytest.raises(BackendError, match="web_search"):
        asyncio.run(backend.complete(request()))


def test_codex_turn_failure_reports_the_model_error(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "fail")
    backend = CodexCLIBackend(binary=fake(tmp_path, "codex", FAKE_CODEX), retries=0)
    with pytest.raises(BackendError, match="model not supported"):
        asyncio.run(backend.complete(request()))


# --- Grok ---

def test_grok_runs_in_a_clean_home_without_claude_config(tmp_path, grok_login):
    backend = GrokCLIBackend(binary=fake(tmp_path, "grok", FAKE_GROK), grok_home=grok_login)
    response = asyncio.run(backend.complete(request()))
    assert response.data == {"echo": 'say "hi" $(whoami)', "claude_visible": False, "auth_linked": True}
    assert (backend.clean_home / ".grok" / "auth.json").resolve() == (grok_login / "auth.json").resolve()


def test_grok_argv_overrides_system_prompt_and_limits_tools(tmp_path, grok_login):
    argv = GrokCLIBackend(grok_home=grok_login).build_argv(request(effort="xhigh"), tmp_path / "p.txt")
    assert argv[argv.index("--system-prompt-override") + 1] == "You are a strict evaluator."
    assert argv[argv.index("--tools") + 1] == "read_file"
    assert argv[argv.index("--disallowed-tools") + 1] == "read_file,search_tool,use_tool"
    assert argv[argv.index("--reasoning-effort") + 1] == "xhigh"
    for flag in ["--disable-web-search", "--no-subagents", "--no-plan"]:
        assert flag in argv


def test_grok_tool_call_is_rejected(tmp_path, grok_login, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "tool")
    backend = GrokCLIBackend(binary=fake(tmp_path, "grok", FAKE_GROK), grok_home=grok_login, retries=0)
    with pytest.raises(BackendError, match="read_file"):
        asyncio.run(backend.complete(request()))


def test_grok_long_answer_continuation_without_tools_is_accepted(tmp_path, grok_login, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "continuation")
    backend = GrokCLIBackend(binary=fake(tmp_path, "grok", FAKE_GROK), grok_home=grok_login, retries=0)
    response = asyncio.run(backend.complete(request()))
    assert response.raw["num_turns"] == 2
    assert json.loads(response.text)["claude_visible"] is False


def test_grok_requires_a_login(tmp_path):
    with pytest.raises(BackendError, match="grok login"):
        GrokCLIBackend(grok_home=tmp_path / "missing")
