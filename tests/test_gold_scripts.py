"""The two gold-set scripts: building task files from a curation record, and the level-1 run script."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "run_gold_dev.sh")]).returncode == 0


def script_copy(tmp_path):
    """The run script in a fresh checkout with two tasks, and a fake `python` that only logs its calls."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "run_gold_dev.sh", root / "scripts")
    tasks = root / "tasks" / "repodb-dev"
    tasks.mkdir(parents=True)
    for name in ("repodb-a", "repodb-b"):
        (tasks / f"{name}.json").write_text("{}")
    bin_dir, log = tmp_path / "bin", tmp_path / "python.log"
    bin_dir.mkdir()
    (bin_dir / "python").write_text(f'#!/usr/bin/env bash\necho "$PYTHONPATH|$*" >> "{log}"\n')
    (bin_dir / "python").chmod(0o755)
    return root, log, {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def run_script(root, out, env):
    return subprocess.run(["bash", str(root / "scripts" / "run_gold_dev.sh"), str(out)], capture_output=True, text=True, env=env)


def test_run_script_skips_finished_tasks_and_runs_this_checkouts_code(tmp_path):
    root, log, env = script_copy(tmp_path)
    done = tmp_path / "out" / "20260930-120000-repodb-a"
    done.mkdir(parents=True)
    (done / "header.json").write_text("{}")
    (done / "result.json").write_text("{}")
    result = run_script(root, tmp_path / "out", env)
    assert result.returncode == 0, result.stderr
    assert "skip repodb-a" in result.stdout
    calls = [line.split("|") for line in log.read_text().splitlines()]
    assert [args.split()[:3] for _, args in calls] == [["-m", "reasonlineage", "run"], ["-m", "reasonlineage", "gold"]]
    assert "repodb-b.json" in calls[0][1] and {path for path, _ in calls} == {str(root / "src")}


def test_run_script_stops_at_a_run_that_did_not_finish(tmp_path):
    root, log, env = script_copy(tmp_path)
    stopped = tmp_path / "out" / "20260930-120000-repodb-a"
    stopped.mkdir(parents=True)
    (stopped / "header.json").write_text("{}")
    result = run_script(root, tmp_path / "out", env)
    assert result.returncode == 1 and "resume" in result.stderr and "repodb-a" in result.stderr
    assert not log.exists()
