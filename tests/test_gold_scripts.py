"""The gold-set scripts: building repoDB task files from a curation record, the level-1 run script, and the
level-2 script that replays generation 0 and evolves further."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POOL = [{"ind_id": "C1", "indication": "Disease X", "approved": ["Adrug"],
         "failed": [{"drug": "Bdrug", "nct": "NCT00000001", "status": "Terminated", "phase": "Phase 3", "reason": "efficacy", "detail": "Futility"},
                    {"drug": "Cdrug", "nct": "NCT00000002", "status": "Withdrawn", "phase": "Phase 2", "reason": "safety", "detail": "Toxicity"}]}]
TASK = {"id": "repodb-disease-x", "ind_id": "C1", "indication": "Disease X", "display_name": "disease X",
        "approved": {"drug": "Adrug", "why": "approved"},
        "failed": [{"drug": "Bdrug", "ncts": ["NCT00000001"], "why": "futility"}, {"drug": "Cdrug", "ncts": ["NCT00000002"], "why": "toxicity"}]}


def build(tmp_path, curation):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / "candidates.json").write_text(json.dumps(POOL))
    (gold_dir / "curation.json").write_text(json.dumps(curation))
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "build_repodb_dev.py"), "build", "--gold-dir", str(gold_dir),
                           "--tasks-dir", str(tmp_path / "tasks")], capture_output=True, text=True)


def test_build_step_writes_tasks_and_gold(tmp_path):
    result = build(tmp_path, {"tasks": [TASK], "dropped": []})
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "tasks" / "repodb-disease-x.json").exists() and (tmp_path / "gold" / "gold.json").exists()


def test_build_step_refuses_a_broken_curation(tmp_path):
    result = build(tmp_path, {"tasks": [{**TASK, "approved": {"drug": "Bdrug", "why": "x"}}], "dropped": []})
    assert result.returncode == 1 and "breaks the rules" in result.stderr and "not approved" in result.stderr
    assert not (tmp_path / "gold" / "gold.json").exists()


def test_run_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "run_gold.sh")]).returncode == 0


def script_copy(tmp_path):
    """The run script in a fresh checkout with two tasks, and a fake `python` that only logs its calls."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "run_gold.sh", root / "scripts")
    tasks = root / "tasks" / "repodb-dev"
    tasks.mkdir(parents=True)
    for name in ("repodb-a", "repodb-b"):
        (tasks / f"{name}.json").write_text("{}")
    bin_dir, log = tmp_path / "bin", tmp_path / "python.log"
    bin_dir.mkdir()
    (bin_dir / "python").write_text(f'#!/usr/bin/env bash\necho "$PYTHONPATH|$*" >> "{log}"\n')
    (bin_dir / "python").chmod(0o755)
    return root, log, {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def run_script(root, env, *args):
    return subprocess.run(["bash", str(root / "scripts" / "run_gold.sh"), *map(str, args)], capture_output=True, text=True, env=env)


def test_run_script_skips_finished_tasks_and_runs_this_checkouts_code(tmp_path):
    root, log, env = script_copy(tmp_path)
    done = tmp_path / "out" / "20260930-120000-repodb-a"
    done.mkdir(parents=True)
    (done / "header.json").write_text("{}")
    (done / "result.json").write_text("{}")
    result = run_script(root, env, "repodb-dev", tmp_path / "out")
    assert result.returncode == 0, result.stderr
    assert "skip repodb-a" in result.stdout
    calls = [line.split("|") for line in log.read_text().splitlines()]
    assert [args.split()[:3] for _, args in calls] == [["-m", "reasonlineage", "run"], ["-m", "reasonlineage", "gold"]]
    assert "repodb-b.json" in calls[0][1] and {path for path, _ in calls} == {str(root / "src")}
    assert f"--gold {root}/gold/repodb-dev/gold.json" in calls[1][1]
    assert f"--analysis {tmp_path}/out/analysis.md" in calls[1][1]


def test_run_script_stops_at_a_run_that_did_not_finish(tmp_path):
    root, log, env = script_copy(tmp_path)
    stopped = tmp_path / "out" / "20260930-120000-repodb-a"
    stopped.mkdir(parents=True)
    (stopped / "header.json").write_text("{}")
    result = run_script(root, env, "repodb-dev", tmp_path / "out")
    assert result.returncode == 1 and "resume" in result.stderr and "repodb-a" in result.stderr
    assert not log.exists()


def test_run_script_writes_to_runs_gold_set_by_default(tmp_path):
    root, log, env = script_copy(tmp_path)
    result = run_script(root, env, "repodb-dev")
    assert result.returncode == 0, result.stderr
    run_call = log.read_text().splitlines()[0]
    assert f"--out {root}/runs/gold-repodb-dev" in run_call


def test_run_script_stops_on_a_set_without_task_files(tmp_path):
    root, log, env = script_copy(tmp_path)
    result = run_script(root, env, "ctopen-nope")
    assert result.returncode == 1 and "no task files in tasks/ctopen-nope" in result.stderr
    assert not log.exists()


# --- the level-2 script (weather level-2 design 6.2) ---

def test_evolve_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "run_gold_evolve.sh")]).returncode == 0


def evolve_copy(tmp_path, gold_ids=("wx-01", "wx-03")):
    """A checkout with one set of three finished generation-0 runs, a gold file naming two of them, and a fake
    `python` that only logs its calls."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "run_gold_evolve.sh", root / "scripts")
    (root / "tasks" / "wx").mkdir(parents=True)
    for task_id in ("wx-01", "wx-02", "wx-03"):
        (root / "tasks" / "wx" / f"{task_id}.json").write_text("{}")
        run = root / "runs" / "gold-wx" / f"20261003-120000-{task_id}"
        run.mkdir(parents=True)
        (run / "header.json").write_text("{}")
        (run / "result.json").write_text("{}")
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"source": {"left_out": ["wx-02"]}, "tasks": {i: {} for i in gold_ids}}, indent=2))
    bin_dir, log = tmp_path / "bin", tmp_path / "python.log"
    bin_dir.mkdir()
    (bin_dir / "python").write_text(f'#!/usr/bin/env bash\necho "$PYTHONPATH|$*" >> "{log}"\n')
    (bin_dir / "python").chmod(0o755)
    return root, gold, log, {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def run_evolve(root, env, *args):
    return subprocess.run(["bash", str(root / "scripts" / "run_gold_evolve.sh"), *map(str, args)],
                          capture_output=True, text=True, env=env)


def test_evolve_replays_each_gold_task_with_more_generations_then_scores(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    out = tmp_path / "out"
    result = run_evolve(root, env, out, gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    calls = [line.split("|") for line in log.read_text().splitlines()]
    assert {path for path, _ in calls} == {str(root / "src")}
    runs = [args for _, args in calls if args.startswith("-m reasonlineage run ")]
    assert runs == [f"-m reasonlineage run {root}/tasks/wx/{i}.json --replay {root}/runs/gold-wx/20261003-120000-{i} "
                    f"--generations 3 --out {out}" for i in ("wx-01", "wx-03")]  # wx-02 is not in the gold file
    assert calls[-1][1].startswith(f"-m reasonlineage gold --gold {gold} ")
    assert calls[-1][1].endswith(f"--out {out}/report.json --analysis {out}/analysis.md")


def test_evolve_skips_a_task_already_finished(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    done = tmp_path / "out" / "20261004-010000-wx-01"
    done.mkdir(parents=True)
    (done / "header.json").write_text("{}")
    (done / "result.json").write_text("{}")
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    assert "skip wx-01: already finished" in result.stdout
    runs = [line for line in log.read_text().splitlines() if "reasonlineage run " in line]
    assert len(runs) == 1 and "wx-03.json" in runs[0]


def test_evolve_skips_a_task_left_out_after_repeated_stops(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "left_out.txt").write_text("wx-01\n")
    result = run_evolve(root, env, out, gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    assert "skip wx-01: left out after repeated stops" in result.stdout
    runs = [line for line in log.read_text().splitlines() if "reasonlineage run " in line]
    assert len(runs) == 1 and "wx-03.json" in runs[0]


def test_evolve_stops_at_a_run_that_did_not_finish(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    stopped = tmp_path / "out" / "20261004-010000-wx-01"
    stopped.mkdir(parents=True)
    (stopped / "header.json").write_text("{}")
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 1 and "resume" in result.stderr and "wx-01" in result.stderr
    assert not log.exists()


def test_evolve_stops_when_a_gold_task_has_an_unfinished_generation_zero(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    (root / "runs" / "gold-wx" / "20261003-120000-wx-03" / "result.json").unlink()
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 1 and "generation-0 run of wx-03" in result.stderr
    assert "reasonlineage gold" not in (log.read_text() if log.exists() else "")


def test_evolve_stops_on_a_set_without_runs(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx", "nope")
    assert result.returncode == 1 and "no generation-0 runs in runs/gold-nope" in result.stderr
    assert "reasonlineage gold" not in log.read_text()


@pytest.mark.parametrize("args, message", [
    (("OUT", "GOLD", "3"), "usage: scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET"),
    (("OUT", "GOLD", "0", "wx"), "GENERATIONS must be a whole number of at least 1"),
    (("OUT", "GOLD", "three", "wx"), "GENERATIONS must be a whole number of at least 1"),
])
def test_evolve_refuses_wrong_arguments(tmp_path, args, message):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, *args)
    assert result.returncode == 2 and message in result.stderr
    assert not log.exists()


def test_evolve_stops_without_a_gold_file(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, tmp_path / "out", tmp_path / "missing.json", 3, "wx")
    assert result.returncode == 1 and "no gold file" in result.stderr
    assert not log.exists()
