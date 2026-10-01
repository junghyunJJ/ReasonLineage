"""ClinicalTrials.gov: the search for stopped trials (gold design 4.3) and the trial records kept for
curation (gold design 4.4)."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from reasonlineage.gold.trials import API, SearchError, fetch_trials, search

STUDY = {"protocolSection": {
    "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Bdrug for Disease X"},
    "statusModule": {"overallStatus": "TERMINATED", "whyStopped": "Lack of efficacy"},
    "conditionsModule": {"conditions": ["Disease X"]},
    "designModule": {"phases": ["PHASE3"]},
    "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Bdrug"}, {"type": "DRUG", "name": "Placebo"}]},
}}
OTHER = {"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}, "statusModule": {"overallStatus": "WITHDRAWN"}}}


def test_records_are_fetched_summarized_and_saved(tmp_path):
    asked = []

    def get(url):
        asked.append(url)
        return STUDY

    records = fetch_trials(["NCT00000001"], tmp_path / "trials.json", get=get)
    record = records["NCT00000001"]
    assert (record["title"], record["status"], record["why_stopped"]) == ("Bdrug for Disease X", "TERMINATED", "Lack of efficacy")
    assert record["nct"] == "NCT00000001" and record["phases"] == ["PHASE3"] and record["conditions"] == ["Disease X"]
    assert record["interventions"] == [{"name": "Bdrug", "type": "DRUG"}, {"name": "Placebo", "type": "DRUG"}]
    assert asked == [API.format(nct="NCT00000001")]
    assert json.loads((tmp_path / "trials.json").read_text())["NCT00000001"]["title"] == "Bdrug for Disease X"


def test_saved_records_are_not_fetched_again(tmp_path):
    path = tmp_path / "trials.json"
    fetch_trials(["NCT00000001"], path, get=lambda url: STUDY)
    records = fetch_trials(["NCT00000001"], path, get=lambda url: pytest.fail("fetched again"))
    assert records["NCT00000001"]["status"] == "TERMINATED"


def test_a_failing_fetch_is_retried_once_then_recorded_and_retried_later(tmp_path):
    path, calls = tmp_path / "trials.json", []

    def down(url):
        calls.append(url)
        raise OSError("HTTP Error 404: Not Found")

    records = fetch_trials(["NCT00000009"], path, get=down)
    assert len(calls) == 2 and records["NCT00000009"] == {"error": "HTTP Error 404: Not Found"}
    assert fetch_trials(["NCT00000009"], path, get=lambda url: STUDY)["NCT00000009"]["status"] == "TERMINATED"


def test_ids_that_are_not_nct_numbers_are_skipped(tmp_path):
    records = fetch_trials(["NA", "", "NCT00000001"], tmp_path / "trials.json", get=lambda url: STUDY)
    assert list(records) == ["NCT00000001"]


def test_search_reads_every_page_of_stopped_interventional_trials():
    pages = {None: {"studies": [STUDY], "nextPageToken": "t2"}, "t2": {"studies": [OTHER]}}
    asked = []

    def get(url):
        query = parse_qs(urlsplit(url).query)
        asked.append(query)
        return pages[query.get("pageToken", [None])[0]]

    found = search("Disease X", get=get)
    assert [(r["nct"], r["status"]) for r in found] == [("NCT00000001", "TERMINATED"), ("NCT00000002", "WITHDRAWN")]
    assert asked[0]["query.cond"] == ["Disease X"] and asked[0]["filter.overallStatus"] == ["TERMINATED,WITHDRAWN,SUSPENDED"]
    assert asked[0]["filter.advanced"] == ["AREA[StudyType]INTERVENTIONAL"] and asked[0]["pageSize"] == ["1000"]
    assert "InterventionType" in asked[0]["fields"][0] and asked[1]["pageToken"] == ["t2"]


def test_search_sends_the_condition_name_intact():
    asked = []

    def get(url):
        asked.append(parse_qs(urlsplit(url).query)["query.cond"])
        return {"studies": []}

    assert search("Lupus Erythematosus, Systemic", get=get) == []
    assert asked == [["Lupus Erythematosus, Systemic"]]


def test_a_search_page_that_fails_once_is_asked_again():
    answers = [OSError("connection reset"), {"studies": [STUDY]}]

    def flaky(url):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    assert [r["nct"] for r in search("Disease X", get=flaky)] == ["NCT00000001"]


def test_a_search_that_fails_twice_stops_with_the_condition_named():
    calls = []

    def down(url):
        calls.append(url)
        raise OSError("HTTP Error 503: Service Unavailable")

    with pytest.raises(SearchError, match="Disease X"):
        search("Disease X", get=down)
    assert len(calls) == 2
