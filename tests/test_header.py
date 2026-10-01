import subprocess
from dataclasses import replace
from pathlib import Path

from reasonlineage.engine.config import JevSettings, Member, RunOptions, Task, load_setup
from reasonlineage.engine.header import build_header, cli_versions, experiment_problems, resume_problems
from reasonlineage.protocol import load_protocol

REPO = Path(__file__).resolve().parents[1]
SETUP = load_setup(REPO / "configs" / "main.json")
PROTOCOL = load_protocol()


def problems(setup=SETUP, options=RunOptions(), protocol=PROTOCOL, checker=True, fixed=True):
    return experiment_problems(setup=setup, options=options, protocol=protocol, checker_available=checker, policies_fixed=fixed)


def test_the_main_setup_can_start_an_experiment():
    assert problems() == []


def test_experiment_refuses_aliases_open_generations_and_impossible_axes():
    aliased = replace(SETUP, panel=(Member("gpt", "codex", "gpt-latest"),), jev=JevSettings("jev-latest"))
    found = problems(setup=aliased, options=RunOptions(generations=-1, judges="same_family"), fixed=False)
    assert any("fixed policies" in p for p in found)
    assert any("generations" in p for p in found)
    assert any("gpt-latest" in p for p in found) and any("jev-latest" in p for p in found)
    assert any("same_family" in p for p in found)


def test_an_experiment_may_score_generation_zero_only():
    assert problems(options=RunOptions(generations=0)) == []


def test_an_enforced_gate_needs_a_checker():
    enforced = replace(PROTOCOL, data={**PROTOCOL.data, "j1": {**PROTOCOL.j1, "enforce": True}})
    assert any("J1" in p for p in problems(protocol=enforced, checker=False))


def test_header_records_what_resume_needs():
    task = Task("t1", "Q?", ("a", "b"), "biomedical", "public")
    header = build_header(run_id="r1", task=task, setup=SETUP, options=RunOptions(seed=7), protocol=PROTOCOL,
                          versions={"claude": "2.1.285"}, commit="abc", checker="jev", checker_note=None)
    assert header["protocol"] == {"version": "1.0.2", "hash": PROTOCOL.hash}
    assert header["options"]["seed"] == 7 and header["task"]["candidates"] == ["a", "b"]
    assert header["setup"]["panel"][3]["base_url"] == "https://ollama.com/v1"
    assert header["j1_enforce"] is False and header["checker"] == "jev"


def test_resume_stops_on_a_changed_protocol_and_warns_on_cli_versions():
    header = {"protocol": {"hash": "old"}, "cli_versions": {"codex": "0.159.2"}, "options": {"mode": "experiment"}}
    stop, warn = resume_problems(header, PROTOCOL, {"codex": "0.160.0"}, [])
    assert "protocol files changed" in stop[0]
    assert warn == ["CLI versions changed: codex: 0.159.2 -> 0.160.0"]


def test_a_wrong_local_model_stops_experiments_but_only_warns_in_exploration():
    base = {"protocol": {"hash": PROTOCOL.hash}, "cli_versions": {}}
    stop, _ = resume_problems({**base, "options": {"mode": "experiment"}}, PROTOCOL, {}, ["qwen: serves ['x']"])
    assert stop == ["qwen: serves ['x']"]
    stop, warn = resume_problems({**base, "options": {"mode": "exploration"}}, PROTOCOL, {}, ["qwen: serves ['x']"])
    assert stop == [] and warn == ["qwen: serves ['x']"]


def test_cli_versions_are_read_and_failures_are_marked():
    members = [Member("opus", "claude", "m"), Member("gpt", "codex", "m"), Member("qwen", "http", "m", None, "u", "alibaba")]

    def fake(argv):
        if argv[0] == "codex":
            raise subprocess.CalledProcessError(1, argv)
        return "2.1.285 (Claude Code)\n"

    assert cli_versions(members, run=fake) == {"claude": "2.1.285 (Claude Code)", "codex": "unknown (CalledProcessError)"}
