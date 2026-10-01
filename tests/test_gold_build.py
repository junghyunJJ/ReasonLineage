"""Checking the curation record, then writing task files and the gold file (gold design 4.5, 4.6)."""

import copy
import json

import pytest

from reasonlineage.engine.config import load_task
from reasonlineage.gold import repodb
from reasonlineage.gold.build import QUESTION, CurationError, build, check_curation, shuffled, task_id

POOL = [{
    "ind_id": "C1", "indication": "Disease X", "approved": ["Adrug", "Zdrug"],
    "failed": [
        {"drug": "Bdrug", "nct": "NCT00000001", "status": "Terminated", "phase": "Phase 3", "reason": "efficacy", "detail": "Futility"},
        {"drug": "Cdrug", "nct": "NCT00000002", "status": "Withdrawn", "phase": "Phase 2", "reason": "safety", "detail": "Toxicity"},
    ],
}]
CURATION = {
    "tasks": [{
        "id": "repodb-disease-x", "ind_id": "C1", "indication": "Disease X", "display_name": "disease X",
        "approved": {"drug": "Adrug", "why": "approved for disease X; not the first-line drug"},
        "failed": [{"drug": "Bdrug", "ncts": ["NCT00000001"], "why": "monotherapy trial stopped for futility"},
                   {"drug": "Cdrug", "ncts": ["NCT00000002"], "why": "monotherapy trial stopped for toxicity"}],
    }],
    "dropped": [],
}


def test_build_writes_loadable_tasks_and_the_gold_file(tmp_path):
    (path,) = build(CURATION, POOL, tmp_path / "tasks", tmp_path / "gold.json")
    task = load_task(path)
    assert task.id == "repodb-disease-x" and sorted(task.candidates) == ["Adrug", "Bdrug", "Cdrug"]
    assert task.question == QUESTION.format(name="disease X")
    assert (task.category, task.data_sensitivity) == ("biomedical", "public")
    gold = json.loads((tmp_path / "gold.json").read_text())
    assert gold["tasks"] == {"repodb-disease-x": {"approved": ["Adrug"], "failed": ["Bdrug", "Cdrug"]}}
    assert gold["source"] == {"repo": "zietzm/repoDB", "commit": repodb.COMMIT, "path": "data/repoDB.csv", "sha256": repodb.SHA256}


def test_the_question_does_not_call_it_repurposing():
    assert "repurpos" not in QUESTION.lower()


def test_candidate_order_depends_only_on_the_task_id():
    drugs = ["Adrug", "Bdrug", "Cdrug"]
    assert shuffled(drugs, "repodb-x") == shuffled(drugs, "repodb-x")
    assert len({shuffled(drugs, f"repodb-{i}").index("Adrug") for i in range(20)}) == 3  # the approved drug moves around


def test_task_ids_come_from_the_display_name():
    assert task_id("rheumatoid arthritis") == "repodb-rheumatoid-arthritis"
    assert task_id("Non-Small Cell Lung Carcinoma") == "repodb-non-small-cell-lung-carcinoma"


def broken(change):
    curation = copy.deepcopy(CURATION)
    change(curation["tasks"][0])
    return curation


@pytest.mark.parametrize("change, message", [
    (lambda t: t["approved"].update(drug="Bdrug"), "not approved"),
    (lambda t: t["failed"][0].update(drug="Zdrug"), "no efficacy or safety failure"),
    (lambda t: t["failed"][1].update(ncts=["NCT09999999"]), "must be among"),
    (lambda t: t["failed"].pop(), "one approved and two different failed drugs"),
    (lambda t: t["failed"][0].update(why=""), "needs a reason"),
    (lambda t: t.update(id="repodb-other"), "id must be"),
    (lambda t: t.update(ind_id="C9"), "not in the candidate pool"),
])
def test_curation_rules_are_enforced(tmp_path, change, message):
    curation = broken(change)
    assert any(message in p for p in check_curation(curation, POOL))
    with pytest.raises(CurationError, match=message):
        build(curation, POOL, tmp_path / "tasks", tmp_path / "gold.json")
    assert not (tmp_path / "gold.json").exists()


def test_one_task_per_indication(tmp_path):
    curation = copy.deepcopy(CURATION)
    curation["tasks"].append(copy.deepcopy(curation["tasks"][0]))
    assert any("second task" in p for p in check_curation(curation, POOL))


def test_two_tasks_may_not_share_an_id(tmp_path):
    pool = POOL + [{**POOL[0], "ind_id": "C2", "indication": "Disease X, familial"}]
    twin = {**CURATION["tasks"][0], "ind_id": "C2", "indication": "Disease X, familial"}  # same display name, same id
    with pytest.raises(CurationError, match="same id"):
        build({"tasks": [CURATION["tasks"][0], twin], "dropped": []}, pool, tmp_path / "tasks", tmp_path / "gold.json")
    assert not (tmp_path / "gold.json").exists()
