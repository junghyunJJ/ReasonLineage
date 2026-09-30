"""The command line with fake models, fake servers, and fake PubMed (no network)."""

import json

import pytest

from fakes import Clock, FakeChecker, FakeModel
from reasonlineage.backends.base import BackendError
from reasonlineage.cli import Services, main
from reasonlineage.engine.events import read_events
from diagnose_data import EFETCH_XML

NAMES = ("opus", "gpt", "grok", "qwen")
FAMILY = {"opus": "anthropic", "gpt": "openai", "grok": "xai", "qwen": "alibaba"}


def write_files(tmp_path):
    setup = {
        "panel": [{"name": n, "backend": "http", "model": f"model-{n}", "effort": "xhigh",
                   "base_url": "http://fake/v1", "family": FAMILY[n]} for n in NAMES],
        "checkers": {"jev": {"version": "jev-1.13.0"}},
        "checker_for": {"public": "jev"},
    }
    task = {"id": "ipf", "question": "Which drug for IPF?", "candidates": ["metformin", "imatinib", "sildenafil"],
            "category": "biomedical", "data_sensitivity": "public"}
    (tmp_path / "setup.json").write_text(json.dumps(setup))
    (tmp_path / "task.json").write_text(json.dumps(task))
    return str(tmp_path / "task.json"), str(tmp_path / "setup.json")


class World:
    """Fake outside world: models, servers, checker, and PubMed."""

    def __init__(self, *, judge_fails=False, server_down=False, checker=None):
        self.models = {n: FakeModel(n, Clock(), fail_roles={"judge"} if (judge_fails and n == "grok") else ())
                       for n in NAMES}
        self.checker = checker

        def list_models(member):
            if server_down:
                raise BackendError(f"request to {member.base_url} failed: connection refused")
            return [member.model]

        def checker_factory(setup, task, protocol, env):
            return (self.checker, None) if self.checker else (None, "jev needs an API key in $JEV_API_KEY")

        self.services = Services(backend=lambda member, n: self.models[member.name], list_models=list_models,
                                 checker=checker_factory, versions=lambda members: {}, pubmed=lambda ids: EFETCH_XML, env={})


def run_dirs(tmp_path):
    return sorted(p for p in (tmp_path / "runs").iterdir() if p.is_dir())


def test_run_writes_a_complete_run_folder(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    code = main(["run", task, "--config", setup, "--seed", "7", "--generations", "1", "--out", str(tmp_path / "runs")],
                World().services)
    assert code == 0
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    assert header["options"]["seed"] == 7 and header["options"]["generations"] == 1
    assert header["checker"] is None and "API key" in header["checker_note"]
    assert (run_dir / "result.json").exists()
    assert "J1 is skipped" in capsys.readouterr().out


def test_a_down_local_server_stops_the_run_before_any_call(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    world = World(server_down=True)
    assert main(["run", task, "--config", setup, "--out", str(tmp_path / "runs")], world.services) == 1
    assert "connection refused" in capsys.readouterr().err
    assert all(m.seen == [] for m in world.models.values())


def test_replay_and_gen0_from_cannot_be_combined(tmp_path):
    task, setup = write_files(tmp_path)
    with pytest.raises(SystemExit):
        main(["run", task, "--config", setup, "--replay", "a", "--gen0-from", "b"], World().services)


def test_a_stopped_run_resumes_after_the_cause_is_fixed(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    args = ["run", task, "--config", setup, "--seed", "7", "--generations", "1", "--out", str(tmp_path / "runs")]
    assert main(args, World(judge_fails=True).services) == 2
    assert "reasonlineage resume" in capsys.readouterr().err
    (run_dir,) = run_dirs(tmp_path)
    assert main(["resume", str(run_dir)], World().services) == 0
    events = [r["event"] for r in read_events(run_dir / "events.jsonl")]
    assert "run.stopped" in events and "run.resumed" in events and events[-1] == "run.completed"


def test_resume_refuses_a_changed_protocol(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")], World().services)
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    header["protocol"]["hash"] = "something else"
    (run_dir / "header.json").write_text(json.dumps(header))
    assert main(["resume", str(run_dir)], World().services) == 1
    assert "protocol files changed" in capsys.readouterr().err


def test_replay_reuses_seed_and_conditions(tmp_path):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--seed", "11", "--judges", "all", "--generations", "1",
          "--out", str(tmp_path / "runs")], World().services)
    (first,) = run_dirs(tmp_path)
    dead = World()
    dead.models = {n: FakeModel(n, fail_roles={"author", "judge"}) for n in NAMES}
    assert main(["run", task, "--config", setup, "--replay", str(first), "--out", str(tmp_path / "runs")], dead.services) == 0
    second = [p for p in run_dirs(tmp_path) if p != first][0]
    options = json.loads((second / "header.json").read_text())["options"]
    assert options["seed"] == 11 and options["judges"] == "all" and options["replay_from"] == str(first)
    assert json.loads((second / "result.json").read_text())["best"] == json.loads((first / "result.json").read_text())["best"]


def test_the_gate_writes_checks_when_a_checker_is_available(tmp_path):
    task, setup = write_files(tmp_path)
    world = World(checker=FakeChecker())
    assert main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")], world.services) == 0
    (run_dir,) = run_dirs(tmp_path)
    assert len(read_events(run_dir / "checks.jsonl")) == 6  # 4 seeds + 2 offspring


def test_diagnose_runs_j2_and_the_pmid_check(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    world = World(checker=FakeChecker())
    main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")], world.services)
    (run_dir,) = run_dirs(tmp_path)
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"items": [{"item": "metformin", "outcome_date": "2026-03-01"}]}))
    assert main(["diagnose", str(run_dir), "--gold-items", str(gold)], world.services) == 0
    assert (run_dir / "diagnostics" / "j2.jsonl").exists()
    summary = json.loads((run_dir / "diagnostics" / "pmid_summary.json").read_text())
    assert summary["citations"] > 0
