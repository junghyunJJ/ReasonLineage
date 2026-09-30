from pathlib import Path

import pytest

from reasonlineage.backends import BackendError, ClaudeCLIBackend, HttpBackend
from reasonlineage.engine.config import (
    ConfigError,
    Member,
    build_backend,
    load_setup,
    load_task,
    setup_from_dict,
    task_from_dict,
    verify_http_members,
)

REPO = Path(__file__).resolve().parents[1]


def task(**overrides):
    base = {"id": "t1", "question": "Q?", "candidates": ["a", "b"], "category": "biomedical", "data_sensitivity": "public"}
    return {**base, **overrides}


def test_main_config_holds_the_final_panel_and_checkers():
    setup = load_setup(REPO / "configs" / "main.json")
    assert [(m.name, m.model, m.effort) for m in setup.panel] == [
        ("opus", "claude-opus-5-5", "xhigh"), ("gpt", "gpt-6.1-sol", "xhigh"),
        ("grok", "grok-4.7", "xhigh"), ("qwen", "Qwen/Qwen3.8-Flash-Next-FP8", "xhigh"),
    ]
    assert [m.family_name for m in setup.panel] == ["anthropic", "openai", "xai", "alibaba"]
    assert setup.jev.version == "jev-1.13.0"
    assert setup.local_checkers["deepseek"].effort == "max"
    assert setup.checker_for == {"public": "jev", "private": "deepseek"}
    assert setup_from_dict(setup.to_dict()) == setup


def test_example_task_loads():
    loaded = load_task(REPO / "tasks" / "example-ipf.json")
    assert loaded.candidates == ("metformin", "imatinib", "sildenafil")
    assert task_from_dict(loaded.to_dict()) == loaded


@pytest.mark.parametrize("bad, message", [
    ({"candidates": ["a", " A "]}, "same item twice"),
    ({"candidates": ["a"]}, "at least 2"),
    ({"data_sensitivity": "secret"}, "public' or 'private"),
    ({"category": "astrology"}, "'category'"),
    ({"question": " "}, "'question'"),
])
def test_task_validation(bad, message):
    with pytest.raises(ConfigError, match=message):
        task_from_dict(task(**bad))


def test_http_member_needs_url_and_family():
    with pytest.raises(ConfigError, match="base_url.*family"):
        setup_from_dict({"panel": [{"name": "qwen", "backend": "http", "model": "m"}]})


def test_private_data_can_never_go_to_jev():
    raw = {"panel": [{"name": "opus", "backend": "claude", "model": "m"}],
           "checkers": {"jev": {"version": "jev-1.13.0"}}, "checker_for": {"private": "jev"}}
    with pytest.raises(ConfigError, match="private"):
        setup_from_dict(raw)


def test_verify_http_members_reports_down_or_wrong_servers():
    qwen = Member("qwen", "http", "Qwen/Qwen3.8-Flash-Next-FP8", "xhigh", "http://x/v1", "alibaba")
    opus = Member("opus", "claude", "claude-opus-5-5", "xhigh")

    def down(member):
        raise BackendError("request to http://x/v1 failed: connection refused")

    assert verify_http_members([opus, qwen], lambda m: [m.model]) == []
    assert verify_http_members([qwen], down) == ["qwen: request to http://x/v1 failed: connection refused"]
    assert "serves ['other']" in verify_http_members([qwen], lambda m: ["other"])[0]


def test_build_backend_turns_off_backend_retries():
    claude = build_backend(Member("opus", "claude", "claude-opus-5-5"), 2)
    http = build_backend(Member("qwen", "http", "m", None, "http://x/v1", "alibaba"), 3)
    assert isinstance(claude, ClaudeCLIBackend) and claude.retries == 0
    assert isinstance(http, HttpBackend) and http.retries == 0 and http.base_url == "http://x/v1"
