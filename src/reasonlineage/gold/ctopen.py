"""CT Open (arXiv 2604.16742) as the source of gold v0 (gold v0 design).

Every quarter CT Open publishes clinical trial outcome questions whose answers were not public before the
window's cutoff, with the dated reports each answer came from. Gold v0 keeps the primary-endpoint results of
trials that test an already approved drug and were first reported after every panel model's training cutoff.
"""

import ast
import hashlib
import io
import pickle
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from . import repodb

REPO = "ClinicalTrial-OpenChallenge/CT_Open"
COMMIT_2025 = "cc78ff33e90cc8da01f9db4e3b3d35dcc9ce4539"
# Each set's file, pinned by commit and sha256, and the earliest first-report date it accepts (gold v0 design 4.1).
SETS: dict[str, dict[str, str]] = {
    "winter-2025": {"file": "Winter_2025.pickle", "commit": COMMIT_2025,
                    "sha256": "849c36f258a84787a5360500ca246c800880418e5cb1996f73f8cb4927736141", "after": "2025-02-01"},
    "summer-2025": {"file": "Summer_2025.pickle", "commit": COMMIT_2025,
                    "sha256": "1b01f622d68c42d522916734cf4b04fb5a437901b6cea2f7e39df91085ca9567", "after": "2025-09-01"},
}
CACHE = Path.home() / ".cache" / "reasonlineage" / "ctopen"
FIELDS = ("endpoint", "list_of_tuples", "arms", "reported_results")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class SourceError(RuntimeError):
    """A CT Open file could not be fetched, is not the pinned file, or does not hold the expected plain data."""


class _PlainOnly(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"{module}.{name}")


def safe_load(data: bytes) -> Any:
    """The pickled object, if it is plain data (dicts, lists, tuples, strings, numbers).

    A pickle can run code while it loads, so every class and function it asks for is refused.
    """
    try:
        return _PlainOnly(io.BytesIO(data)).load()
    except pickle.UnpicklingError as exc:
        raise SourceError(f"the file holds more than plain data ({exc}); refusing to load it") from None


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def load_set(name: str, cache: str | Path = CACHE, download: Callable[[str], bytes] = _download) -> dict:
    """The entries of a pinned CT Open set, fetched once into `cache`."""
    if name not in SETS:
        raise SourceError(f"unknown CT Open set {name!r}; add it to ctopen.SETS with its commit, file, sha256 "
                          f"and date (gold v0 design 4.1)")
    pin = SETS[name]
    url = f"https://raw.githubusercontent.com/{REPO}/{pin['commit']}/datasets/{pin['file']}"
    path = Path(cache) / pin["file"]
    if not path.exists():
        try:
            data = download(url)
        except OSError as exc:
            raise SourceError(f"could not fetch {url}: {exc}") from None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != pin["sha256"]:
        raise SourceError(f"{path} has sha256 {digest}, not the pinned {pin['sha256']}; delete it to fetch again")
    entries = safe_load(data)
    if not isinstance(entries, dict):
        raise SourceError(f"{path} does not hold a dict of entries (gold v0 design 4.2)")
    return entries


def first_report(entry: dict[str, Any]) -> str | None:
    """The earliest YYYY-MM-DD date among an entry's reported results, or None."""
    dates = [report.get("date") for report in (entry.get("reported_results") or {}).values() if isinstance(report, dict)]
    dates = [d for d in dates if isinstance(d, str) and DATE.fullmatch(d)]
    return min(dates) if dates else None


def _endpoint(text: Any) -> dict[str, Any] | None:
    """The outcome measure that CT Open stores as dict text, or None when it does not parse."""
    try:
        value = ast.literal_eval(text) if isinstance(text, str) else text
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, dict) else None


def _comparison(entry: dict[str, Any]) -> tuple[str, str, str] | None:
    """The one (tested arm, MET or NOT MET, comparator) of an entry, or None."""
    tuples = entry["list_of_tuples"] or []
    if len(tuples) != 1 or len(tuples[0]) != 3 or tuples[0][1] not in ("MET", "NOT MET"):
        return None
    return tuple(tuples[0])


def candidates(entries: dict, after: str, name_drugs: Callable[[str], set[str]]) -> list[dict[str, Any]]:
    """Trials whose primary-endpoint result gold v0 can use (gold v0 design 4.2), in NCT order.

    A trial counts when every primary-endpoint entry holds one comparison and they all agree, its first report
    (the earliest over all its entries, any outcome) is on or after `after`, and its tested arm tests one repoDB
    drug approved for some indication.
    """
    first: dict[str, str] = {}
    primary: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for (nct, _), entry in entries.items():
        missing = [field for field in FIELDS if field not in entry]
        if missing:
            raise SourceError(f"CT Open entry {nct} has no {', '.join(missing)}; "
                              f"the file's format differs from gold v0 design 4.2")
        date = first_report(entry)
        if date and (nct not in first or date < first[nct]):
            first[nct] = date
        endpoint = _endpoint(entry["endpoint"])
        if endpoint and endpoint.get("outcome_type") == "primaryOutcomes":
            primary[nct].append((endpoint, entry))
    found = []
    for nct in sorted(primary):
        if nct not in first or first[nct] < after:
            continue
        comparisons = [_comparison(entry) for _, entry in primary[nct]]
        if None in comparisons or len({c[1] for c in comparisons}) != 1:
            continue
        endpoint, entry = min(primary[nct], key=lambda pair: str(sorted(pair[0].items())))
        arm_label, label, comparator = _comparison(entry)
        arm = next((a for a in entry["arms"] if a.get("label") == arm_label), None)
        drug = repodb.tested_drug(arm.get("interventions") or [], name_drugs) if arm else None
        if drug is None:
            continue
        found.append({"nct": nct, "title": entry.get("brief_title"), "drug": drug, "arm": arm_label,
                      "comparator": comparator, "endpoint": {"measure": endpoint.get("measure"),
                                                            "timeFrame": endpoint.get("timeFrame")},
                      "label": label, "first_report": first[nct]})
    return found


def attach(found: list[dict[str, Any]], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The candidates with each trial's conditions and phases from its ClinicalTrials.gov record.

    A record that could not be fetched leaves both empty and is marked, so the review can judge it.
    """
    out = []
    for candidate in found:
        record = records.get(candidate["nct"], {})
        out.append({**candidate, "conditions": record.get("conditions") or [], "phases": record.get("phases") or [],
                    **({"fetch_error": record["error"]} if "error" in record else {})})
    return out
