"""repoDB (Brown & Patel, Scientific Data 2017) as the source of the dev gold set (gold design 4.1-4.3).

repoDB marks a drug-indication pair as failed when a trial stopped, whatever the reason. Only
trials that stopped for efficacy or safety count here; the rest stopped for funding, accrual,
or administration and say nothing about the drug. repoDB has too few such failures on its own, so
a ClinicalTrials.gov search of each indication adds more (gold design 4.3).
"""

import csv
import hashlib
import io
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

COMMIT = "c921b2610f596a40cee2a538de37f9f29d3dfd06"
URL = f"https://raw.githubusercontent.com/zietzm/repoDB/{COMMIT}/data/repoDB.csv"
SHA256 = "c5424d26b190ea207f6d343620eea748f845b0f28cad811eaf3a158797e0ef23"
CACHE = Path.home() / ".cache" / "reasonlineage" / "repodb"
FAILED = frozenset({"Terminated", "Withdrawn", "Suspended"})
EFFICACY = re.compile(
    r"efficac|futil|no (significant )?(benefit|effect|difference)|not effective|ineffective"
    r"|lack of (clinical )?(benefit|response|activity)|did not (meet|show|demonstrate)|primary (end ?point|outcome)"
    r"|interim analysis|unlikely to (meet|succeed|show)|insufficient (activity|response|benefit)",
    re.IGNORECASE,
)
SAFETY = re.compile(r"safety|adverse|toxicit|side effect|serious", re.IGNORECASE)
PLACEBO = re.compile(r"placebo|saline|vehicle|sham|standard (of )?care|usual care|best supportive care", re.IGNORECASE)
TESTED = frozenset({"DRUG", "BIOLOGICAL"})


class SourceError(RuntimeError):
    """The repoDB file could not be fetched, or it is not the pinned file."""


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def load_rows(cache: str | Path = CACHE, download: Callable[[str], bytes] = _download) -> list[dict[str, str]]:
    """The rows of the pinned repoDB file, fetched once into `cache`."""
    path = Path(cache) / "repoDB.csv"
    if not path.exists():
        try:
            data = download(URL)
        except OSError as exc:
            raise SourceError(f"could not fetch {URL}: {exc}") from None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise SourceError(f"{path} has sha256 {digest}, not the pinned {SHA256}; delete it to fetch again")
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def stop_reason(text: str | None) -> str | None:
    """'efficacy' or 'safety' when a trial's stop reason names one of them, else None."""
    if EFFICACY.search(text or ""):
        return "efficacy"
    if SAFETY.search(text or ""):
        return "safety"
    return None


def candidates(rows: Sequence[dict[str, str]], min_failed: int = 2,
               extra: dict[str, list[dict[str, str]]] | None = None) -> list[dict[str, Any]]:
    """Indications with at least one approved drug and `min_failed` other drugs whose trials for it
    stopped for efficacy or safety.

    `extra` adds failures found by a ClinicalTrials.gov search (`searched_failures`), by indication id;
    a drug and trial that repoDB already has is not added twice.
    """
    approved: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for row in rows:
        names.setdefault(row["ind_id"], row["ind_name"])
        if row["status"] == "Approved":
            approved[row["ind_id"]].add(row["drug_name"])
    failures: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        reason = stop_reason(row["DetailedStatus"])
        if row["status"] in FAILED and reason and row["drug_name"] not in approved[row["ind_id"]]:
            failures[row["ind_id"]].append({"drug": row["drug_name"], "nct": row["NCT"], "status": row["status"],
                                            "phase": row["phase"], "reason": reason, "detail": row["DetailedStatus"],
                                            "source": "repodb"})
    for ind_id, found in (extra or {}).items():
        known = {(f["drug"], f["nct"]) for f in failures[ind_id]}
        failures[ind_id] += [f for f in found if (f["drug"], f["nct"]) not in known]
    pool = []
    for ind_id in sorted(failures):
        if approved[ind_id] and len({f["drug"] for f in failures[ind_id]}) >= min_failed:
            pool.append({"ind_id": ind_id, "indication": names[ind_id], "approved": sorted(approved[ind_id]),
                         "failed": sorted(failures[ind_id], key=lambda f: (f["drug"], f["nct"]))})
    return pool


def _drug_pattern(names: Iterable[str]) -> re.Pattern[str]:
    """Drug names as whole words, the longest first, so 'insulin glargine' is found before 'insulin'."""
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=lambda n: (-len(n), n)))
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


def drug_namer(rows: Sequence[dict[str, str]]) -> Callable[[str], set[str]]:
    """A function giving the repoDB drugs, approved for some indication, that a text names as whole words."""
    names = {row["drug_name"].lower(): row["drug_name"] for row in rows if row["status"] == "Approved"}
    pattern = _drug_pattern(names)
    return lambda text: {names[m] for m in pattern.findall((text or "").lower())}


def tested_drug(interventions: Iterable[dict[str, Any]], name_drugs: Callable[[str], set[str]]) -> str | None:
    """The one repoDB drug that every tested intervention names, or None.

    Tested interventions are drugs or biologicals that are not a placebo; one that names no repoDB drug,
    or a second drug, gives None.
    """
    tested = [i.get("name") or "" for i in interventions
              if i.get("type") in TESTED and not PLACEBO.search(i.get("name") or "")]
    drugs = [name_drugs(name) for name in tested]
    named = set().union(*drugs)
    return named.pop() if drugs and all(drugs) and len(named) == 1 else None


def searched_failures(rows: Sequence[dict[str, str]], ind_id: str, records: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Failed drugs from searched trials of one indication (gold design 4.3): the trial stopped for efficacy
    or safety, and its tested drugs are all one repoDB drug that is approved for something, but not for this.
    """
    name_drugs = drug_namer(rows)
    approved = {row["drug_name"] for row in rows if row["ind_id"] == ind_id and row["status"] == "Approved"}
    found = []
    for record in records:
        reason = stop_reason(record["why_stopped"])
        drug = tested_drug(record["interventions"], name_drugs)
        if reason and drug and drug not in approved:
            found.append({"drug": drug, "nct": record["nct"], "status": record["status"].title(),
                          "phase": "/".join(record["phases"]), "reason": reason, "detail": record["why_stopped"],
                          "source": "ctgov"})
    return found
