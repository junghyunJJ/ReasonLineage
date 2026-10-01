"""CT Open as the source of gold v0 (gold v0 design 4): safe loading, trial selection, review, grouping, files."""

import copy
import hashlib
import json
import pickle

import pytest

from reasonlineage.diagnose.gold import correctness
from reasonlineage.diagnose.j2 import load_gold_items
from reasonlineage.engine.config import load_task
from reasonlineage.gold import ctopen, repodb

FIRED = []


def fire():
    FIRED.append("ran")


class Carrier:
    """Loading a pickled Carrier would call fire(): a stand-in for a file that carries code."""

    def __reduce__(self):
        return (fire, ())


PLAIN = pickle.dumps({("NCT00000001", "{}"): {"arms": [], "n": 1.5, "pair": (1, 2)}})


def pin(monkeypatch, sha256):
    monkeypatch.setitem(ctopen.SETS, "test-2025", {"file": "Test.pickle", "commit": "abc123", "sha256": sha256, "after": "2025-01-01"})


def test_plain_data_loads():
    assert ctopen.safe_load(PLAIN) == {("NCT00000001", "{}"): {"arms": [], "n": 1.5, "pair": (1, 2)}}


def test_a_file_that_carries_code_is_refused_without_running_it():
    with pytest.raises(ctopen.SourceError, match="more than plain data"):
        ctopen.safe_load(pickle.dumps({"x": Carrier()}))
    assert FIRED == []


def test_a_pinned_set_is_fetched_once_and_its_checksum_checked(tmp_path, monkeypatch):
    pin(monkeypatch, hashlib.sha256(PLAIN).hexdigest())
    fetched = []

    def download(url):
        fetched.append(url)
        return PLAIN

    assert ctopen.load_set("test-2025", cache=tmp_path, download=download) == ctopen.safe_load(PLAIN)
    assert ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: pytest.fail("fetched twice"))
    assert fetched == ["https://raw.githubusercontent.com/ClinicalTrial-OpenChallenge/CT_Open/abc123/datasets/Test.pickle"]


def test_a_file_that_is_not_the_pinned_one_is_refused(tmp_path, monkeypatch):
    pin(monkeypatch, "0" * 64)
    with pytest.raises(ctopen.SourceError, match="not the pinned"):
        ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: PLAIN)


def test_a_file_that_is_not_a_dict_of_entries_is_refused(tmp_path, monkeypatch):
    listed = pickle.dumps([1, 2])
    pin(monkeypatch, hashlib.sha256(listed).hexdigest())
    with pytest.raises(ctopen.SourceError, match="dict of entries"):
        ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: listed)


def test_an_unknown_set_and_a_failed_download_are_source_errors(tmp_path):
    with pytest.raises(ctopen.SourceError, match="unknown CT Open set"):
        ctopen.load_set("spring-2031", cache=tmp_path)

    def down(url):
        raise OSError("no route to host")

    with pytest.raises(ctopen.SourceError, match="could not fetch"):
        ctopen.load_set("summer-2025", cache=tmp_path, download=down)


def test_the_2025_sets_are_pinned():
    assert ctopen.SETS["winter-2025"]["after"] == "2025-02-01" and ctopen.SETS["summer-2025"]["after"] == "2025-09-01"
    assert all(len(p["sha256"]) == 64 and len(p["commit"]) == 40 for p in ctopen.SETS.values())


APPROVED = [{"drug_name": name, "status": "Approved"} for name in ("Edrug", "Adrug", "Fdrug", "Gdrug")]
NAME_DRUGS = repodb.drug_namer(APPROVED)
AFTER = "2026-07-01"


def entry(*, arm="Edrug 10 mg", label="MET", comparator="Placebo", outcome_type="primaryOutcomes",
          dates=("2026-07-02",), tested=(("DRUG", "Edrug 10 mg"),), tuples=None, measure="Change in score"):
    endpoint = str({"measure": measure, "description": "", "timeFrame": "12 weeks", "outcome_type": outcome_type})
    return {"brief_title": "A trial", "endpoint": endpoint,
            "arms": [{"label": arm, "type": "EXPERIMENTAL", "interventions": [{"type": t, "name": n} for t, n in tested]},
                     {"label": comparator, "type": "PLACEBO_COMPARATOR", "interventions": [{"type": "DRUG", "name": "Placebo"}]}],
            "list_of_tuples": [[arm, label, comparator]] if tuples is None else tuples,
            "reported_results": {f"https://example.org/{i}": {"date": d, "results": ["reported"]} for i, d in enumerate(dates)}}


def select(*entries):
    """CT Open keys an entry by (NCT, endpoint text)."""
    return ctopen.candidates({(nct, e["endpoint"]): e for nct, e in entries}, AFTER, NAME_DRUGS)


def test_a_primary_result_first_reported_after_the_date_is_kept():
    (found,) = select(("NCT00000001", entry()))
    assert found == {"nct": "NCT00000001", "title": "A trial", "drug": "Edrug", "arm": "Edrug 10 mg", "comparator": "Placebo",
                     "endpoint": {"measure": "Change in score", "timeFrame": "12 weeks"}, "label": "MET",
                     "first_report": "2026-07-02"}


def test_the_date_itself_counts():
    assert [f["first_report"] for f in select(("NCT00000001", entry(dates=("2026-07-01",))))] == ["2026-07-01"]


@pytest.mark.parametrize("changed", [
    {"outcome_type": "secondaryOutcomes"},                                   # not the primary endpoint
    {"tuples": [["Edrug 10 mg", "MET", "Placebo"], ["Edrug 10 mg", "MET", "Other"]]},  # two comparisons
    {"label": "NOT REPORTED"},                                               # neither MET nor NOT MET
    {"dates": ("2026-06-30",)},                                              # reported before the date
    {"dates": ()},                                                           # no dated report
    {"dates": ("June 2026",)},                                               # no date in YYYY-MM-DD form
    {"tested": (("DRUG", "Zdrug"),)},                                        # not an approved drug
    {"tested": (("DRUG", "Edrug"), ("DRUG", "Adrug"))},                      # two drugs tested together
    {"tuples": [["Another arm", "MET", "Placebo"]]},                         # the tested arm is not among the arms
])
def test_trials_that_are_left_out(changed):
    assert select(("NCT00000001", entry(**changed))) == []


def test_an_endpoint_that_does_not_parse_is_left_out():
    broken = entry() | {"endpoint": "{'measure': 'unterminated"}
    assert ctopen.candidates({("NCT00000001", "x"): broken}, AFTER, NAME_DRUGS) == []


def test_a_result_reported_earlier_for_another_outcome_keeps_the_trial_out():
    primary = entry(dates=("2026-07-10",))
    secondary = entry(outcome_type="secondaryOutcomes", measure="Other outcome", dates=("2026-06-20",))
    assert select(("NCT00000001", primary), ("NCT00000001", secondary)) == []


def test_several_primary_endpoints_count_only_when_they_agree():
    agree = select(("NCT00000001", entry(measure="First")), ("NCT00000001", entry(measure="Second")))
    assert [(f["nct"], f["label"]) for f in agree] == [("NCT00000001", "MET")]
    mixed = select(("NCT00000001", entry(measure="First")), ("NCT00000001", entry(measure="Second", label="NOT MET")))
    assert mixed == []


def test_trials_come_back_in_nct_order():
    found = select(("NCT00000009", entry()), ("NCT00000002", entry(label="NOT MET")))
    assert [f["nct"] for f in found] == ["NCT00000002", "NCT00000009"]


def test_a_missing_field_stops_with_its_name():
    broken = entry()
    del broken["arms"]
    with pytest.raises(ctopen.SourceError, match="no arms"):
        ctopen.candidates({("NCT00000001", broken["endpoint"]): broken}, AFTER, NAME_DRUGS)


def test_attach_adds_conditions_and_phases_and_marks_fetch_errors():
    found = select(("NCT00000001", entry()), ("NCT00000002", entry(label="NOT MET")))
    records = {"NCT00000001": {"conditions": ["Disease X"], "phases": ["PHASE2"]}, "NCT00000002": {"error": "HTTP Error 404"}}
    first, second = ctopen.attach(found, records)
    assert (first["conditions"], first["phases"], "fetch_error" in first) == (["Disease X"], ["PHASE2"], False)
    assert (second["conditions"], second["phases"], second["fetch_error"]) == ([], [], "HTTP Error 404")


def cand(nct, label, drug, phases=("PHASE2",)):
    return {"nct": nct, "title": "A trial", "drug": drug, "arm": f"{drug} 10 mg", "comparator": "Placebo",
            "endpoint": {"measure": "Change in score", "timeFrame": "12 weeks"}, "label": label,
            "first_report": "2026-07-02", "conditions": ["Disease"], "phases": list(phases)}


CANDS = [cand("NCT00000001", "MET", "Edrug"), cand("NCT00000002", "NOT MET", "Adrug"), cand("NCT00000003", "NOT MET", "Fdrug")]
REVIEW = {"keep": [{"nct": "NCT00000001", "display_name": "disease a", "why": "new indication"},
                   {"nct": "NCT00000002", "display_name": "disease b", "why": "new indication"},
                   {"nct": "NCT00000003", "display_name": "disease c", "why": "new indication"}],
          "drop": []}


def build(tmp_path, found=CANDS, review=REVIEW):
    return ctopen.build(found, review, "summer-2025", tmp_path / "tasks", tmp_path / "gold.json", tmp_path / "items")


def test_build_writes_tasks_the_gold_file_and_items(tmp_path):
    (path,) = build(tmp_path)
    task = load_task(path)
    assert task.id == "ctopen-summer-2025-01"
    assert sorted(task.candidates) == ["Adrug for disease b", "Edrug for disease a", "Fdrug for disease c"]
    assert task.question.startswith(ctopen.QUESTION) and (task.category, task.data_sensitivity) == ("biomedical", "public")
    assert "- Edrug for disease a: Edrug 10 mg vs Placebo, phase 2; primary endpoint: Change in score (12 weeks)" in task.question
    gold = json.loads((tmp_path / "gold.json").read_text())
    truth = gold["tasks"]["ctopen-summer-2025-01"]
    assert truth == {"approved": ["Edrug for disease a"], "failed": ["Adrug for disease b", "Fdrug for disease c"]}
    pin = ctopen.SETS["summer-2025"]
    assert gold["source"] == {"repo": ctopen.REPO, "commit": pin["commit"], "path": "datasets/Summer_2025.pickle",
                              "sha256": pin["sha256"], "after": "2025-09-01"}
    assert correctness(["Edrug for disease a", "Adrug for disease b", "Fdrug for disease c"], truth) == 1.0
    items = load_gold_items(tmp_path / "items" / "ctopen-summer-2025-01.json")
    assert sorted(i["item"] for i in items) == sorted(task.candidates) and {i["outcome_date"] for i in items} == {"2026-07-02"}


def test_a_trial_without_a_trial_record_still_builds(tmp_path):
    found = [CANDS[0] | {"phases": [], "conditions": [], "fetch_error": "HTTP Error 404"}, *CANDS[1:]]
    (path,) = build(tmp_path, found)
    assert "Edrug 10 mg vs Placebo, phase not reported;" in load_task(path).question


def reviewed(change):
    review = copy.deepcopy(REVIEW)
    change(review)
    return review


@pytest.mark.parametrize("change, message", [
    (lambda r: r["keep"].pop(), "NCT00000003: not reviewed"),
    (lambda r: r["drop"].append({"nct": "NCT00000099", "why": "x"}), "NCT00000099: not among the candidates"),
    (lambda r: r["drop"].append({"nct": "NCT00000001", "why": "x"}), "NCT00000001: reviewed twice"),
    (lambda r: r["keep"][0].update(why=""), "NCT00000001: needs a reason"),
    (lambda r: r["keep"][1].pop("display_name"), "NCT00000002: a kept trial needs a display_name"),
])
def test_review_rules_are_enforced(tmp_path, change, message):
    review = reviewed(change)
    assert any(message in p for p in ctopen.check_review(review, CANDS))
    with pytest.raises(ctopen.ReviewError, match=message):
        build(tmp_path, review=review)
    assert not (tmp_path / "gold.json").exists() and not (tmp_path / "tasks").exists()


def test_build_refuses_task_files_the_review_does_not_build(tmp_path):
    build(tmp_path)
    stale = tmp_path / "tasks" / "ctopen-summer-2025-02.json"
    stale.write_text("{}")
    with pytest.raises(ctopen.ReviewError, match="ctopen-summer-2025-02.json is not built by this review"):
        build(tmp_path)


def kept(nct, label, disease):
    return cand(nct, label, "Edrug") | {"display_name": disease}


def test_each_met_trial_gets_two_not_met_trials_of_other_diseases():
    trials = [kept("NCT00000001", "MET", "a"), kept("NCT00000002", "MET", "b"),
              *(kept(f"NCT0000001{i}", "NOT MET", d) for i, d in enumerate("cdef"))]
    groups = ctopen.group(trials, "summer-2025")
    assert groups == ctopen.group(list(reversed(trials)), "summer-2025")  # the order is fixed by the set, not the input
    assert len(groups) == 2 and all(len({t["display_name"] for t in g}) == 3 for g in groups)
    assert sorted(t["nct"] for g in groups for t in g[1:]) == [f"NCT0000001{i}" for i in range(4)]


def test_a_met_trial_without_two_other_diseases_is_left_out():
    trials = [kept("NCT00000001", "MET", "a"), kept("NCT00000002", "NOT MET", "a"), kept("NCT00000003", "NOT MET", "a"),
              kept("NCT00000004", "NOT MET", "b")]
    assert ctopen.group(trials, "summer-2025") == []
