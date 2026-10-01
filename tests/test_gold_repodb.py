"""The pinned repoDB file, the candidate indications drawn from it (gold design 4.1, 4.2), and the failed
drugs picked from a ClinicalTrials.gov search (gold design 4.3)."""

import csv
import hashlib
import io

import pytest

from reasonlineage.gold import repodb

HEADER = '"drug_name","drug_id","ind_name","ind_id","NCT","status","phase","DetailedStatus"\n'


def csv_text(*rows):
    return HEADER + "".join(",".join(f'"{value}"' for value in row) + "\n" for row in rows)


ROWS = csv_text(
    ("Adrug", "DB1", "Disease X", "C1", "NA", "Approved", "NA", "NA"),
    ("Bdrug", "DB2", "Disease X", "C1", "NCT01", "Terminated", "Phase 3", "Lack of efficacy at interim analysis"),
    ("Cdrug", "DB3", "Disease X", "C1", "NCT02", "Withdrawn", "Phase 2", "Serious adverse events"),
    ("Ddrug", "DB4", "Disease X", "C1", "NCT03", "Terminated", "Phase 2", "Funding unavailable"),
    ("Adrug", "DB1", "Disease X", "C1", "NCT04", "Terminated", "Phase 4", "Futility"),
    ("Bdrug", "DB2", "Disease Y", "C2", "NCT05", "Suspended", "Phase 2", "No benefit"),
    ("Edrug", "DB5", "Disease Y", "C2", "NA", "Approved", "NA", "NA"),
)


def rows():
    return list(csv.DictReader(io.StringIO(ROWS)))


@pytest.mark.parametrize("text, reason", [
    ("Lack of efficacy", "efficacy"), ("Futility analysis", "efficacy"), ("Did not meet primary endpoint", "efficacy"),
    ("Serious adverse events", "safety"), ("Toxicity", "safety"),
    ("Funding unavailable", None), ("Low accrual", None), ("", None), (None, None),
])
def test_stop_reasons(text, reason):
    assert repodb.stop_reason(text) == reason


def test_candidates_need_an_approved_drug_and_two_efficacy_or_safety_failures():
    (only,) = repodb.candidates(rows())
    assert only["ind_id"] == "C1" and only["indication"] == "Disease X" and only["approved"] == ["Adrug"]
    assert [(f["drug"], f["nct"], f["reason"]) for f in only["failed"]] == [("Bdrug", "NCT01", "efficacy"), ("Cdrug", "NCT02", "safety")]


def test_repodb_failures_are_marked_with_their_source():
    (only,) = repodb.candidates(rows())
    assert {f["source"] for f in only["failed"]} == {"repodb"}


def searched(drug, nct):
    return {"drug": drug, "nct": nct, "status": "Terminated", "phase": "PHASE2", "reason": "efficacy", "detail": "Futility",
            "source": "ctgov"}


def test_searched_failures_join_the_pool_once_and_count_toward_the_minimum():
    pool = repodb.candidates(rows(), extra={"C2": [searched("Adrug", "NCT20"), searched("Bdrug", "NCT05")]})
    (c2,) = [c for c in pool if c["ind_id"] == "C2"]
    assert [(f["drug"], f["nct"], f["source"]) for f in c2["failed"]] == [("Adrug", "NCT20", "ctgov"), ("Bdrug", "NCT05", "repodb")]


def record(why, *interventions):
    return {"nct": "NCT10", "title": "A trial", "status": "TERMINATED", "why_stopped": why, "phases": ["PHASE2"],
            "conditions": ["Disease X"], "interventions": [{"type": kind, "name": name} for kind, name in interventions]}


def approved(name):
    return {"drug_name": name, "drug_id": "DB9", "ind_name": "Disease Z", "ind_id": "C9", "NCT": "NA", "status": "Approved",
            "phase": "NA", "DetailedStatus": "NA"}


def test_a_searched_trial_counts_when_its_one_tested_drug_is_approved_for_something_else():
    found = repodb.searched_failures(rows(), "C1", [record("Futility at interim", ("DRUG", "Edrug 10 mg"), ("DRUG", "Placebo"))])
    assert found == [{"drug": "Edrug", "nct": "NCT10", "status": "Terminated", "phase": "PHASE2", "reason": "efficacy",
                      "detail": "Futility at interim", "source": "ctgov"}]


def test_dose_arms_of_one_drug_are_one_tested_drug():
    found = repodb.searched_failures(rows(), "C1", [record("Serious adverse events", ("DRUG", "Edrug 5 mg"), ("DRUG", "Edrug 10 mg"))])
    assert [(f["drug"], f["reason"]) for f in found] == [("Edrug", "safety")]


@pytest.mark.parametrize("why, interventions", [
    ("Funding ended", [("DRUG", "Edrug")]),                          # not stopped for efficacy or safety
    ("Futility", [("DRUG", "Adrug")]),                               # approved for this indication
    ("Futility", [("DRUG", "Zdrug")]),                               # not a repoDB drug
    ("Futility", [("DRUG", "Edrug"), ("DRUG", "Zdrug")]),            # a second tested drug that is not in repoDB
    ("Futility", [("DRUG", "Edrug"), ("BIOLOGICAL", "Adrug")]),      # two repoDB drugs
    ("Futility", [("DRUG", "Edrug plus Adrug")]),                    # two drugs in one name
    ("Futility", [("PROCEDURE", "Edrug infusion")]),                 # no tested drug
    ("Futility", [("DRUG", None)]),                                  # a tested drug with no name
])
def test_searched_trials_that_do_not_count(why, interventions):
    assert repodb.searched_failures(rows(), "C1", [record(why, *interventions)]) == []


def test_drug_names_match_whole_words_and_the_longest_name_first():
    more = rows() + [approved("Iron"), approved("Insulin"), approved("Insulin Glargine")]
    assert repodb.searched_failures(more, "C1", [record("Futility", ("DRUG", "Ironwood extract"))]) == []
    (found,) = repodb.searched_failures(more, "C1", [record("Futility", ("DRUG", "insulin glargine injection"))])
    assert found["drug"] == "Insulin Glargine"


def test_the_pinned_file_is_fetched_once_and_its_checksum_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(repodb, "SHA256", hashlib.sha256(ROWS.encode()).hexdigest())
    fetched = []

    def download(url):
        fetched.append(url)
        return ROWS.encode()

    assert len(repodb.load_rows(cache=tmp_path, download=download)) == 7
    assert repodb.load_rows(cache=tmp_path, download=lambda url: pytest.fail("fetched twice")) == repodb.load_rows(cache=tmp_path)
    assert fetched == [repodb.URL] and repodb.COMMIT in repodb.URL


def test_a_file_that_is_not_the_pinned_one_is_refused(tmp_path):
    with pytest.raises(repodb.SourceError, match="not the pinned"):
        repodb.load_rows(cache=tmp_path, download=lambda url: ROWS.encode())


def test_a_failed_download_is_a_source_error(tmp_path):
    def down(url):
        raise OSError("no route to host")

    with pytest.raises(repodb.SourceError, match="could not fetch"):
        repodb.load_rows(cache=tmp_path, download=down)


def test_tested_drug_is_the_one_repodb_drug_every_tested_intervention_names():
    name_drugs = repodb.drug_namer(rows())
    assert name_drugs("Edrug 10 mg plus Adrug") == {"Edrug", "Adrug"}
    assert repodb.tested_drug([{"type": "DRUG", "name": "Edrug 5 mg"}, {"type": "DRUG", "name": "Placebo"}], name_drugs) == "Edrug"
    assert repodb.tested_drug([{"type": "DRUG", "name": "Edrug"}, {"type": "BIOLOGICAL", "name": "Adrug"}], name_drugs) is None
    assert repodb.tested_drug([{"type": "DRUG", "name": "Zdrug"}], name_drugs) is None
    assert repodb.tested_drug([{"type": "PROCEDURE", "name": "Edrug infusion"}], name_drugs) is None
