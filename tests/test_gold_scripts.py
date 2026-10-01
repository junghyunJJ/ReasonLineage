"""The two gold-set scripts: building task files from a curation record, and the level-1 run script."""

import json
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
