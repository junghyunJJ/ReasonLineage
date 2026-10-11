"""The command line with fake models, fake servers, and fake PubMed (no network)."""

import json
import shutil
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fakes import Clock, FakeChecker, FakeModel
from reasonlineage.backends.base import BackendError
from reasonlineage.cli import Services, build_checker, main
from reasonlineage.engine.config import setup_from_dict, task_from_dict
from reasonlineage.engine.events import read_events
from reasonlineage.protocol import load_protocol
from diagnose_data import EFETCH_XML

NAMES = ("opus", "gpt", "grok", "qwen")
FAMILY = {"opus": "anthropic", "gpt": "openai", "grok": "xai", "qwen": "alibaba"}


def write_files(tmp_path, *, local_checker=False):
    checkers = {"jev": {"version": "jev-1.13.0"}}
    if local_checker:
        checkers["deepseek"] = {"backend": "http", "model": "model-deepseek", "effort": "max", "base_url": "http://fake-checker/v1",
                                "family": "deepseek"}
    setup = {
        "panel": [{"name": n, "backend": "http", "model": f"model-{n}", "effort": "xhigh",
                   "base_url": "http://fake/v1", "family": FAMILY[n]} for n in NAMES],
        "checkers": checkers,
        "checker_for": {"public": "deepseek" if local_checker else "jev"},
    }
    task = {"id": "ipf", "question": "Which drug for IPF?", "candidates": ["metformin", "imatinib", "sildenafil"],
            "category": "biomedical", "data_sensitivity": "public"}
    (tmp_path / "setup.json").write_text(json.dumps(setup))
    (tmp_path / "task.json").write_text(json.dumps(task))
    return str(tmp_path / "task.json"), str(tmp_path / "setup.json")


class World:
    """Fake outside world: models, servers, checker, and PubMed."""

    def __init__(self, *, judge_fails=False, server_down=False, checker=None, down=()):
        self.models = {n: FakeModel(n, Clock(), fail_roles={"judge"} if (judge_fails and n == "grok") else ())
                       for n in NAMES}
        self.checker = checker

        def list_models(member):
            if server_down or member.name in down:
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


@pytest.mark.parametrize("mode, generations", [("experiment", "-1"), ("exploration", "11")])
def test_bad_generations_stop_before_any_call(tmp_path, capsys, mode, generations):
    task, setup = write_files(tmp_path)
    world = World()
    args = ["run", task, "--config", setup, "--mode", mode, "--generations", generations, "--out", str(tmp_path / "runs")]
    assert main(args, world.services) == 1
    assert "generation_limit" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()
    assert all(m.seen == [] for m in world.models.values())


def test_a_down_checker_server_stops_the_run_before_any_call(tmp_path, capsys):
    task, setup = write_files(tmp_path, local_checker=True)
    world = World(checker=FakeChecker(), down={"deepseek"})
    assert main(["run", task, "--config", setup, "--out", str(tmp_path / "runs")], world.services) == 1
    assert "deepseek" in capsys.readouterr().err
    assert all(m.seen == [] for m in world.models.values())


def test_resume_checks_the_checker_server_too(tmp_path, capsys):
    task, setup = write_files(tmp_path, local_checker=True)
    args = ["run", task, "--config", setup, "--seed", "7", "--generations", "1", "--out", str(tmp_path / "runs")]
    assert main(args, World(judge_fails=True, checker=FakeChecker()).services) == 2
    (run_dir,) = run_dirs(tmp_path)
    capsys.readouterr()
    world = World(checker=FakeChecker(), down={"deepseek"})
    assert main(["resume", str(run_dir)], world.services) == 1
    assert "deepseek" in capsys.readouterr().err
    assert all(m.seen == [] for m in world.models.values())


def test_gen0_from_a_missing_run_stops_before_any_call(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    world = World()
    args = ["run", task, "--config", setup, "--gen0-from", str(tmp_path / "no-such-run"), "--out", str(tmp_path / "runs")]
    assert main(args, world.services) == 1
    assert "no-such-run" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()
    assert all(m.seen == [] for m in world.models.values())


def test_gen0_from_a_run_of_another_task_is_refused(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")], World().services)
    (source,) = run_dirs(tmp_path)
    other = json.loads((tmp_path / "task.json").read_text()) | {"question": "Which drug for a different disease?"}
    (tmp_path / "other.json").write_text(json.dumps(other))
    world = World()
    args = ["run", str(tmp_path / "other.json"), "--config", setup, "--gen0-from", str(source), "--out", str(tmp_path / "runs")]
    assert main(args, world.services) == 1
    assert "different task" in capsys.readouterr().err
    assert run_dirs(tmp_path) == [source]
    assert all(m.seen == [] for m in world.models.values())


def test_gen0_from_shares_generation_0_through_the_command_line(tmp_path):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")], World().services)
    (source,) = run_dirs(tmp_path)
    args = ["run", task, "--config", setup, "--judges", "all", "--generations", "1", "--gen0-from", str(source),
            "--out", str(tmp_path / "runs")]
    assert main(args, World().services) == 0
    (second,) = [p for p in run_dirs(tmp_path) if p != source]
    writes = [r for r in read_events(second / "events.jsonl") if r["event"] == "call.completed" and r["name"].startswith("g0/write/")]
    assert len(writes) == 4 and all(r["replayed"] for r in writes)


PUBLIC = task_from_dict({"id": "t", "question": "Q?", "candidates": ["a", "b"], "category": "biomedical",
                         "data_sensitivity": "public"})


def jev_setup(key_file):
    return setup_from_dict({
        "panel": [{"name": "opus", "backend": "claude", "model": "m"}],
        "checkers": {"jev": {"version": "jev-1.13.0", "api_key_file": str(key_file)}},
        "checker_for": {"public": "jev"},
    })


def test_the_jev_key_is_read_from_the_key_file(tmp_path):
    key_file = tmp_path / "jev.key"
    key_file.write_text("key-from-file\n")
    checker, why = build_checker(jev_setup(key_file), PUBLIC, load_protocol(), env={})
    assert why is None and checker.api_key == "key-from-file"


def test_the_key_file_path_may_start_with_a_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "jev.key").write_text("key-from-home")
    checker, _ = build_checker(jev_setup("~/jev.key"), PUBLIC, load_protocol(), env={})
    assert checker.api_key == "key-from-home"


def test_an_environment_key_wins_over_the_key_file(tmp_path):
    key_file = tmp_path / "jev.key"
    key_file.write_text("key-from-file")
    checker, _ = build_checker(jev_setup(key_file), PUBLIC, load_protocol(), env={"JEV_API_KEY": "key-from-env"})
    assert checker.api_key == "key-from-env"


def test_a_missing_key_file_skips_j1_and_names_the_file(tmp_path):
    checker, why = build_checker(jev_setup(tmp_path / "missing.key"), PUBLIC, load_protocol(), env={})
    assert checker is None and "missing.key" in why


def test_replay_can_add_generations_to_a_generation_zero_run(tmp_path):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--seed", "5", "--generations", "0", "--out", str(tmp_path / "runs")], World().services)
    (first,) = run_dirs(tmp_path)
    world = World()
    args = ["run", task, "--config", setup, "--replay", str(first), "--generations", "2", "--out", str(tmp_path / "runs")]
    assert main(args, world.services) == 0
    (second,) = [p for p in run_dirs(tmp_path) if p != first]
    options = json.loads((second / "header.json").read_text())["options"]
    assert options["generations"] == 2 and options["seed"] == 5 and options["replay_from"] == str(first)
    calls = [r for r in read_events(second / "events.jsonl") if r["event"] == "call.completed"]
    assert {r["name"].split("/")[0] for r in calls} == {"g0", "g1", "g2"}
    assert all(r["replayed"] == r["name"].startswith("g0/") for r in calls)
    assert sum(len(m.seen) for m in world.models.values()) == sum(not r["replayed"] for r in calls)


def test_replay_refuses_a_run_of_another_task(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--generations", "0", "--out", str(tmp_path / "runs")], World().services)
    (source,) = run_dirs(tmp_path)
    other = json.loads((tmp_path / "task.json").read_text()) | {"question": "Which drug for a different disease?"}
    (tmp_path / "other.json").write_text(json.dumps(other))
    world = World()
    args = ["run", str(tmp_path / "other.json"), "--config", setup, "--replay", str(source), "--out", str(tmp_path / "runs")]
    assert main(args, world.services) == 1
    assert "different task" in capsys.readouterr().err
    assert run_dirs(tmp_path) == [source]
    assert all(m.seen == [] for m in world.models.values())


def test_python_dash_m_runs_the_command_line():
    src = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run([sys.executable, "-m", "reasonlineage", "--help"], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(src)})
    assert result.returncode == 0 and "run" in result.stdout and "resume" in result.stdout


def test_gold_scores_runs_and_writes_the_report(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    for seed in ("1", "2"):
        main(["run", task, "--config", setup, "--seed", seed, "--generations", "0", "--out", str(tmp_path / "runs")], World().services)
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"tasks": {"ipf": {"approved": ["metformin"], "failed": ["imatinib", "sildenafil"]}}}))
    (tmp_path / "runs" / "notes.txt").write_text("not a run")
    report = tmp_path / "report.json"
    paths = [str(p) for p in sorted((tmp_path / "runs").iterdir())]
    capsys.readouterr()
    assert main(["gold", "--gold", str(gold), *paths, "--out", str(report)], World().services) == 0
    out = capsys.readouterr()
    assert "Level 1 (generation 0): 4 answers" in out.out and "more than one run" in out.out and "set aside" in out.out
    assert "notes.txt: not a run folder" in out.err
    saved = json.loads(report.read_text())
    assert saved["runs"] == {"scored": 2, "not_a_run": 1} and saved["level1"]["answers"] == 4
    assert all((d / "diagnostics" / "gold.jsonl").exists() for d in run_dirs(tmp_path))


def test_gold_writes_the_level1_analysis(tmp_path):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--seed", "1", "--generations", "0", "--out", str(tmp_path / "runs")], World().services)
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"tasks": {"ipf": {"approved": ["metformin"], "failed": ["imatinib", "sildenafil"]}}}))
    analysis = tmp_path / "analysis.md"
    paths = [str(p) for p in sorted((tmp_path / "runs").iterdir())]
    assert main(["gold", "--gold", str(gold), *paths, "--analysis", str(analysis)], World().services) == 0
    text = analysis.read_text()
    assert text.startswith("# Level 1 analysis") and "**Verdict:" in text and "## Mean judge score by author" in text


def test_gold_needs_a_readable_gold_file(tmp_path, capsys):
    assert main(["gold", "--gold", str(tmp_path / "missing.json"), str(tmp_path)], World().services) == 1
    assert "gold file" in capsys.readouterr().err


def custom_protocol(tmp_path):
    """A copy of the packaged protocol with a different hash and the same behaviour."""
    root = load_protocol().root
    folder = tmp_path / "custom-protocol"
    shutil.copytree(root / "prompts", folder / "prompts")
    shutil.copy(root / "protocol.json", folder / "protocol.json")
    seed = folder / "prompts" / "seed.md"
    seed.write_text(seed.read_text(encoding="utf-8") + "\n", encoding="utf-8")   # rendered prompts are stripped
    return folder


def test_run_records_the_default_protocol_source(tmp_path):
    task, setup = write_files(tmp_path)
    assert main(["run", task, "--config", setup, "--generations", "1", "--out", str(tmp_path / "runs")],
                World().services) == 0
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    assert header["protocol"]["source"] == {"profile": "default"}
    assert header["protocol"]["hash"] == load_protocol().hash


def test_run_with_an_unknown_protocol_stops_before_any_call(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    world = World()
    assert main(["run", task, "--config", setup, "--protocol", "no-such-profile", "--out", str(tmp_path / "runs")],
                world.services) == 1
    assert "jev-combined" in capsys.readouterr().err
    assert all(m.seen == [] for m in world.models.values())
    assert not (tmp_path / "runs").exists()


def test_run_with_the_jev_combined_profile_turns_the_gate_on(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    assert main(["run", task, "--config", setup, "--protocol", "jev-combined", "--out", str(tmp_path / "runs")],
                World().services) == 1
    assert "turns the J1 gate on" in capsys.readouterr().err


def test_resume_reloads_the_protocol_recorded_in_the_header(tmp_path):
    task, setup = write_files(tmp_path)
    folder = custom_protocol(tmp_path)
    args = ["run", task, "--config", setup, "--protocol", str(folder), "--seed", "7", "--generations", "1",
            "--out", str(tmp_path / "runs")]
    assert main(args, World(judge_fails=True).services) == 2
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    assert header["protocol"]["source"] == {"path": str(folder.resolve())}
    assert header["protocol"]["hash"] == load_protocol(folder).hash != load_protocol().hash
    assert main(["resume", str(run_dir)], World().services) == 0


def test_resume_of_a_header_without_a_protocol_source_uses_the_default(tmp_path):
    task, setup = write_files(tmp_path)
    args = ["run", task, "--config", setup, "--seed", "7", "--generations", "1", "--out", str(tmp_path / "runs")]
    assert main(args, World(judge_fails=True).services) == 2
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    header["protocol"].pop("source", None)
    (run_dir / "header.json").write_text(json.dumps(header))
    assert main(["resume", str(run_dir)], World().services) == 0


def test_diagnose_needs_the_protocol_recorded_in_the_header(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    folder = custom_protocol(tmp_path)
    assert main(["run", task, "--config", setup, "--protocol", str(folder), "--generations", "1",
                 "--out", str(tmp_path / "runs")], World().services) == 0
    (run_dir,) = run_dirs(tmp_path)
    shutil.rmtree(folder)
    assert main(["diagnose", str(run_dir)], World().services) == 1
    assert "protocol recorded in header.json is missing" in capsys.readouterr().err


def test_gen0_from_a_run_of_another_protocol_is_refused(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    folder = custom_protocol(tmp_path)
    assert main(["run", task, "--config", setup, "--protocol", str(folder), "--generations", "0",
                 "--out", str(tmp_path / "first")], World().services) == 0
    (source,) = sorted(p for p in (tmp_path / "first").iterdir() if p.is_dir())
    assert main(["run", task, "--config", setup, "--gen0-from", str(source), "--generations", "1",
                 "--out", str(tmp_path / "runs")], World().services) == 1
    assert "hash differs" in capsys.readouterr().err


def changed_protocol(tmp_path):
    """A copy of the packaged protocol whose mutation prompt really differs after rendering."""
    folder = custom_protocol(tmp_path)
    mutate = folder / "prompts" / "mutate.md"
    mutate.write_text(mutate.read_text(encoding="utf-8").rstrip() + "\nKeep the revision short.\n", encoding="utf-8")
    return folder


def test_replay_inherits_the_protocol_of_the_replayed_run(tmp_path):
    task, setup = write_files(tmp_path)
    folder = changed_protocol(tmp_path)
    assert main(["run", task, "--config", setup, "--protocol", str(folder), "--seed", "11", "--generations", "1",
                 "--out", str(tmp_path / "runs")], World().services) == 0
    (first,) = run_dirs(tmp_path)
    dead = World()
    dead.models = {n: FakeModel(n, fail_roles={"author", "judge"}) for n in NAMES}
    assert main(["run", task, "--config", setup, "--replay", str(first), "--out", str(tmp_path / "runs")], dead.services) == 0
    second = [p for p in run_dirs(tmp_path) if p != first][0]
    header = json.loads((second / "header.json").read_text())
    assert header["protocol"]["source"] == {"path": str(folder.resolve())}
    assert header["protocol"]["hash"] == load_protocol(folder).hash


def test_replay_with_other_protocol_files_is_refused(tmp_path, capsys):
    task, setup = write_files(tmp_path)
    folder = changed_protocol(tmp_path)
    assert main(["run", task, "--config", setup, "--protocol", str(folder), "--generations", "1",
                 "--out", str(tmp_path / "runs")], World().services) == 0
    (first,) = run_dirs(tmp_path)
    world = World()
    assert main(["run", task, "--config", setup, "--replay", str(first), "--protocol", "default",
                 "--out", str(tmp_path / "runs")], world.services) == 1
    err = capsys.readouterr().err
    assert "--replay" in err and "hash differs" in err
    assert all(m.seen == [] for m in world.models.values())


def test_the_jev_combined_profile_runs_resumes_and_diagnoses(tmp_path):
    task, setup = write_files(tmp_path)
    data = json.loads(open(task).read())
    data.pop("candidates")                                   # the profile checks open questions
    open(task, "w").write(json.dumps(data))
    assert main(["run", task, "--config", setup, "--protocol", "jev-combined", "--generations", "1",
                 "--out", str(tmp_path / "runs")], World(checker=FakeChecker()).services) == 0
    (run_dir,) = run_dirs(tmp_path)
    header = json.loads((run_dir / "header.json").read_text())
    assert header["protocol"]["source"] == {"profile": "jev-combined"} and header["j1_enforce"] is True
    assert read_events(run_dir / "checks.jsonl")
    assert main(["resume", str(run_dir)], World(checker=FakeChecker()).services) == 0
    assert main(["diagnose", str(run_dir)], World(checker=FakeChecker()).services) == 0
