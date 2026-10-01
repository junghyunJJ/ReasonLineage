"""The CT Open build script (gold v0 design 3, 4.4): the build step from saved candidates and a review record."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_ctopen.py"


def cand(nct, label, drug):
    return {"nct": nct, "title": "A trial", "drug": drug, "arm": f"{drug} 10 mg", "comparator": "Placebo",
            "endpoint": {"measure": "Change in score", "timeFrame": "12 weeks"}, "label": label,
            "first_report": "2025-09-02", "conditions": ["Disease"], "phases": ["PHASE2"]}


CANDS = [cand("NCT00000001", "MET", "Edrug"), cand("NCT00000002", "NOT MET", "Adrug"), cand("NCT00000003", "NOT MET", "Fdrug")]
KEEP = [{"nct": c["nct"], "display_name": f"disease {i}", "why": "new indication"} for i, c in enumerate(CANDS)]


def build(tmp_path, review):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(exist_ok=True)
    (gold_dir / "candidates.json").write_text(json.dumps(CANDS))
    (gold_dir / "review.json").write_text(json.dumps(review))
    return subprocess.run([sys.executable, str(SCRIPT), "build", "summer-2025", "--gold-dir", str(gold_dir),
                           "--tasks-dir", str(tmp_path / "tasks")], capture_output=True, text=True)


def test_build_step_writes_tasks_gold_and_items(tmp_path):
    result = build(tmp_path, {"keep": KEEP, "drop": []})
    assert result.returncode == 0, result.stderr
    assert "1 task files" in result.stdout
    assert (tmp_path / "tasks" / "ctopen-summer-2025-01.json").exists() and (tmp_path / "gold" / "gold.json").exists()
    assert (tmp_path / "gold" / "items" / "ctopen-summer-2025-01.json").exists()


def test_build_step_refuses_a_broken_review(tmp_path):
    result = build(tmp_path, {"keep": KEEP[:2], "drop": []})
    assert result.returncode == 1 and "review.json breaks the rules" in result.stderr
    assert "NCT00000003: not reviewed" in result.stderr and not (tmp_path / "gold" / "gold.json").exists()


def test_an_unknown_set_is_refused_before_anything_runs(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), "build", "spring-2031", "--gold-dir", str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 2 and "invalid choice" in result.stderr


ENDPOINT = str({"measure": "Change in score", "timeFrame": "12 weeks", "outcome_type": "primaryOutcomes"})
ENTRY = {"brief_title": "A trial", "meta_label": "single_arm", "endpoint": ENDPOINT,
         "arms": [{"label": "Edrug arm", "type": "EXPERIMENTAL", "description": "Edrug daily",
                   "interventions": [{"type": "DRUG", "name": "Edrug"}]},
                  {"label": "Placebo arm", "type": "PLACEBO_COMPARATOR", "description": "Placebo daily",
                   "interventions": [{"type": "DRUG", "name": "Placebo"}]}],
         "list_of_tuples": [["Edrug arm", "MET", "Placebo arm"]],
         "reported_results": {"https://example.org/1": {"date": "2025-09-02", "results": ["reported"]}}}


def test_candidates_step_writes_the_candidates_and_a_review_sheet_without_answers(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_ctopen

    monkeypatch.setattr(build_ctopen.ctopen, "load_set", lambda name, cache: {("NCT00000001", ENDPOINT): ENTRY})
    monkeypatch.setattr(build_ctopen.repodb, "load_rows", lambda cache: [{"drug_name": "Edrug", "status": "Approved"}])
    monkeypatch.setattr(build_ctopen.trials, "fetch_trials",
                        lambda ncts, path: {nct: {"conditions": ["Disease"], "phases": ["PHASE2"]} for nct in ncts})
    assert build_ctopen.main(["candidates", "summer-2025", "--gold-dir", str(tmp_path)]) == 0
    assert [c["label"] for c in json.loads((tmp_path / "candidates.json").read_text())] == ["MET"]
    sheet = (tmp_path / "review_sheet.md").read_text()
    assert "NCT00000001" in sheet and "Placebo daily" in sheet and re.search(r"\bMET\b", sheet) is None
