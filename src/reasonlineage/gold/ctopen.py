"""CT Open (arXiv 2604.16742) as the source of gold v0 (gold v0 design).

Every quarter CT Open publishes clinical trial outcome questions whose answers were not public before the
window's cutoff, with the dated reports each answer came from. Gold v0 keeps the primary-endpoint results of
trials that test an already approved drug and were first reported after every panel model's training cutoff.
"""

import ast
import hashlib
import io
import json
import pickle
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from . import repodb
from .build import shuffled

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
QUESTION = ("Which of these three clinical trials is most likely to meet its primary endpoint? Rank the candidates, "
            "and give the mechanism, the key evidence, and a validation experiment for the top pick.")


class SourceError(RuntimeError):
    """A CT Open file could not be fetched, is not the pinned file, or does not hold the expected plain data."""


class ReviewError(ValueError):
    """The review record breaks a rule of gold v0 design 4.3, or the task folder holds files it does not build."""


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


def check_review(review: dict[str, Any], found: list[dict[str, Any]]) -> list[str]:
    """What breaks the rules of gold v0 design 4.3 in the review record; empty when usable."""
    known = {candidate["nct"] for candidate in found}
    problems: list[str] = []
    seen: set[str] = set()
    for kind in ("keep", "drop"):
        for item in review.get(kind, []):
            nct = item.get("nct")
            if nct not in known:
                problems.append(f"{nct}: not among the candidates")
            elif nct in seen:
                problems.append(f"{nct}: reviewed twice")
            seen.add(nct)
            if not item.get("why"):
                problems.append(f"{nct}: needs a reason ('why')")
            if kind == "keep" and not item.get("display_name"):
                problems.append(f"{nct}: a kept trial needs a display_name")
    problems += [f"{nct}: not reviewed; keep or drop it" for nct in sorted(known - seen)]
    return problems


def group(kept: list[dict[str, Any]], set_name: str) -> list[tuple[dict[str, Any], ...]]:
    """(MET, NOT MET, NOT MET) groups with three different diseases, in an order fixed by the set name.

    MET and NOT MET trials are each sorted by NCT and shuffled by a seed from the set name; each MET trial
    takes the first two unused NOT MET trials whose diseases differ from its own and from each other.
    """
    met = {t["nct"]: t for t in kept if t["label"] == "MET"}
    not_met = {t["nct"]: t for t in kept if t["label"] == "NOT MET"}
    pool = shuffled(sorted(not_met), f"ctopen-{set_name}-not-met")
    used: set[str] = set()
    groups = []
    for nct in shuffled(sorted(met), f"ctopen-{set_name}-met"):
        diseases = {met[nct]["display_name"]}
        picks = []
        for other in pool:
            if other not in used and not_met[other]["display_name"] not in diseases:
                picks.append(other)
                diseases.add(not_met[other]["display_name"])
                if len(picks) == 2:
                    break
        if len(picks) == 2:
            used.update(picks)
            groups.append((met[nct], not_met[picks[0]], not_met[picks[1]]))
    return groups


def _phase(phases: list[str]) -> str:
    names = [p.replace("EARLY_PHASE", "early phase ").replace("PHASE", "phase ") for p in phases if p != "NA"]
    return "/".join(names) or "phase not reported"


def build(found: list[dict[str, Any]], review: dict[str, Any], set_name: str, tasks_dir: str | Path,
          gold_path: str | Path, items_dir: str | Path) -> list[Path]:
    """Write one task file per group, the gold file, and one items file per task (gold v0 design 4.4).

    Nothing is written when the review breaks a rule or the task folder holds files this review does not build.
    """
    problems = check_review(review, found)
    if problems:
        raise ReviewError("; ".join(problems))
    by_nct = {candidate["nct"]: candidate for candidate in found}
    kept = [by_nct[item["nct"]] | {"display_name": item["display_name"]} for item in review.get("keep", [])]
    groups = group(kept, set_name)
    ids = [f"ctopen-{set_name}-{i:02d}" for i in range(1, len(groups) + 1)]
    tasks_dir, gold_path, items_dir = Path(tasks_dir), Path(gold_path), Path(items_dir)
    stale = [f"{path} is not built by this review; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise ReviewError("; ".join(stale))
    pin = SETS[set_name]
    gold = {"source": {"repo": REPO, "commit": pin["commit"], "path": f"datasets/{pin['file']}", "sha256": pin["sha256"],
                       "after": pin["after"]},
            "tasks": {}}
    tasks_dir.mkdir(parents=True, exist_ok=True)
    items_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task_id, trials in zip(ids, groups):
        names = {f"{t['drug']} for {t['display_name']}": t for t in trials}
        order = shuffled(list(names), task_id)
        lines = [f"- {name}: {names[name]['arm']} vs {names[name]['comparator']}, {_phase(names[name]['phases'])}; "
                 f"primary endpoint: {names[name]['endpoint']['measure']} ({names[name]['endpoint']['timeFrame']})"
                 for name in order]
        body = {"id": task_id, "question": QUESTION + "\n" + "\n".join(lines), "candidates": order,
                "category": "biomedical", "data_sensitivity": "public"}
        path = tasks_dir / f"{task_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        met, *failed = list(names)
        gold["tasks"][task_id] = {"approved": [met], "failed": sorted(failed)}
        items = {"items": [{"item": name, "outcome_date": t["first_report"]} for name, t in names.items()]}
        (items_dir / f"{task_id}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
