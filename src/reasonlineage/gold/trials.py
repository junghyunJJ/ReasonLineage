"""ClinicalTrials.gov: a search for stopped trials of an indication (gold design 4.3), and trial records for
the failed pairs, kept in a JSON file (gold design 4.4).

Curation reads the records to check that a failed drug was the tested drug, for the indication itself,
and stopped for efficacy or safety.
"""

import json
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

FIELDS = "NCTId,BriefTitle,OverallStatus,WhyStopped,InterventionName,InterventionType,Phase,Condition"
API = f"https://clinicaltrials.gov/api/v2/studies/{{nct}}?fields={FIELDS}"
SEARCH = "https://clinicaltrials.gov/api/v2/studies"
NCT = re.compile(r"NCT\d{8}")


class SearchError(RuntimeError):
    """ClinicalTrials.gov could not be searched."""


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def summarize(study: dict[str, Any]) -> dict[str, Any]:
    """The fields curation needs, from one API v2 study record."""
    section = study.get("protocolSection", {})
    status = section.get("statusModule", {})
    ident = section.get("identificationModule", {})
    return {
        "nct": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "interventions": [{"name": i.get("name"), "type": i.get("type")}
                          for i in section.get("armsInterventionsModule", {}).get("interventions", [])],
        "phases": section.get("designModule", {}).get("phases", []),
        "conditions": section.get("conditionsModule", {}).get("conditions", []),
    }


def search(condition: str, get: Callable[[str], dict[str, Any]] = _get, attempts: int = 2) -> list[dict[str, Any]]:
    """Every stopped (terminated, withdrawn, suspended) interventional trial of a condition, page by page.

    A page that fails `attempts` times stops the search with a SearchError.
    """
    found: list[dict[str, Any]] = []
    token = None
    while True:
        params = {"query.cond": condition, "filter.overallStatus": "TERMINATED,WITHDRAWN,SUSPENDED",
                  "filter.advanced": "AREA[StudyType]INTERVENTIONAL", "fields": FIELDS, "pageSize": "1000"}
        if token:
            params["pageToken"] = token
        url = f"{SEARCH}?{urllib.parse.urlencode(params)}"
        for attempt in range(attempts):
            try:
                page = get(url)
                break
            except (OSError, ValueError) as exc:
                if attempt == attempts - 1:
                    raise SearchError(f"could not search ClinicalTrials.gov for {condition!r}: {exc}") from None
        found += [summarize(study) for study in page.get("studies", [])]
        token = page.get("nextPageToken")
        if not token:
            return found


def fetch_trials(ncts: Iterable[str], path: str | Path, get: Callable[[str], dict[str, Any]] = _get,
                 attempts: int = 2) -> dict[str, dict[str, Any]]:
    """A record for every NCT id, reusing the ones already saved in `path`.

    A fetch that fails `attempts` times is saved as {"error": ...} and tried again on the next call.
    Ids that are not NCT numbers (repoDB writes "NA") are skipped.
    """
    path = Path(path)
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for nct in sorted({n for n in ncts if NCT.fullmatch(n or "")}):
        if nct in records and "error" not in records[nct]:
            continue
        for _ in range(attempts):
            try:
                records[nct] = {**summarize(get(API.format(nct=nct))), "retrieved": date.today().isoformat()}
                break
            except (OSError, ValueError) as exc:
                records[nct] = {"error": str(exc)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return records
