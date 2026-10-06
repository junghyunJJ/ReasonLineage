"""ClaudeCLIBackend against a fake `claude` executable, so no network or login is needed."""

import asyncio
import json
import sys

import pytest

from reasonlineage.backends import BackendError, ClaudeCLIBackend, ModelRequest

FAKE_CLAUDE = """#!{python}
import json, os, sys, time
mode = os.environ.get("FAKE_MODE", "ok")
prompt = sys.stdin.read()
args = sys.argv[1:]
if mode == "sleep":
    time.sleep(5)
if mode == "fail":
    sys.stderr.write("boom")
    sys.exit(2)
if mode == "flaky":
    marker = os.environ["FAKE_MARKER"]
    if not os.path.exists(marker):
        open(marker, "w").close()
        sys.exit(1)
payload = {{"type": "result", "subtype": "success", "is_error": False,
           "result": json.dumps({{"echo": prompt}}), "total_cost_usd": 0.001}}
if "--json-schema" in args:
    payload["structured_output"] = {{"echo": prompt, "argv": args}}
print(json.dumps(payload))
"""

SCHEMA = {"type": "object", "properties": {"score": {"type": "number"}}, "required": ["score"]}


@pytest.fixture
def fake_claude(tmp_path):
    path = tmp_path / "claude"
    path.write_text(FAKE_CLAUDE.format(python=sys.executable))
    path.chmod(0o755)
    return str(path)


def request(**overrides):
    base = {"system": "You are a strict evaluator.", "prompt": "hello", "model": "claude-haiku-4-5-20251001"}
    return ModelRequest(**{**base, **overrides})


def test_argv_isolates_the_call():
    argv = ClaudeCLIBackend().build_argv(request(effort="high", json_schema=SCHEMA))
    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == "You are a strict evaluator."
    assert json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    for flag in ["--safe-mode", "--no-session-persistence"]:
        assert flag in argv
    assert "hello" not in argv  # the prompt goes through stdin


def test_prompt_with_shell_metacharacters_reaches_the_model_intact(fake_claude):
    tricky = 'He said "stop" `rm -rf /` $(whoami) \'quoted\'\n```code```'
    backend = ClaudeCLIBackend(binary=fake_claude)
    response = asyncio.run(backend.complete(request(prompt=tricky, json_schema=SCHEMA)))
    assert response.data["echo"] == tricky
    assert response.cost_usd == 0.001
    assert response.prompt_sha256 == request(prompt=tricky).prompt_sha256


def test_structured_output_falls_back_to_result_text():
    payload = {"type": "result", "subtype": "success", "is_error": False, "result": '{"score": 0.4}'}
    response = ClaudeCLIBackend().parse(json.dumps(payload), request(json_schema=SCHEMA), 1.0)
    assert response.data == {"score": 0.4}


def test_error_payload_raises():
    payload = {"type": "result", "subtype": "error_max_turns", "is_error": True, "result": "nope"}
    with pytest.raises(BackendError, match="error payload"):
        ClaudeCLIBackend().parse(json.dumps(payload), request(), 1.0)


def test_missing_structured_output_raises():
    payload = {"type": "result", "subtype": "success", "is_error": False, "result": "not json"}
    with pytest.raises(BackendError, match="structured output"):
        ClaudeCLIBackend().parse(json.dumps(payload), request(json_schema=SCHEMA), 1.0)


def test_nonzero_exit_fails_after_retry(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "fail")
    backend = ClaudeCLIBackend(binary=fake_claude, retries=1)
    with pytest.raises(BackendError, match=r"2 attempt\(s\).*boom"):
        asyncio.run(backend.complete(request()))


def test_one_retry_recovers_a_flaky_call(fake_claude, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "flaky")
    monkeypatch.setenv("FAKE_MARKER", str(tmp_path / "marker"))
    response = asyncio.run(ClaudeCLIBackend(binary=fake_claude, retries=1).complete(request()))
    assert json.loads(response.text) == {"echo": "hello"}


def test_timeout_kills_the_process(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "sleep")
    backend = ClaudeCLIBackend(binary=fake_claude, retries=0)
    with pytest.raises(BackendError, match="timed out"):
        asyncio.run(backend.complete(request(timeout_s=0.5)))


def test_biology_safeguard_is_identified_before_exit_payload_truncation(tmp_path):
    path = tmp_path / 'bio-error-cli'
    payload = {'subtype': 'success', 'is_error': True,
               'result': "API Error: Opus 5.5's safeguards flagged this session. Details: [bio]",
               'padding': 'x' * 1500}
    path.write_text('#!' + sys.executable + '\nimport sys\nprint(' + repr(json.dumps(payload)) + ')\nsys.exit(1)\n')
    path.chmod(0o755)
    with pytest.raises(BackendError, match='biology safeguard'):
        asyncio.run(ClaudeCLIBackend(binary=str(path), retries=0).complete(request()))
