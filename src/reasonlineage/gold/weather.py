"""Climate-departure gold set (weather design 4).

Each task names three states and asks whose month departed furthest above its own 1901-2000 normal. The answer is
what the weather actually did in July or August 2026, first published after every panel model's training cutoff, so
it cannot be computed from the prompt or recalled — the failure that put three earlier sets at the ceiling.
"""

import hashlib
import itertools
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .build import shuffled


class SourceError(RuntimeError):
    """NCEI could not be read, the saved pool is not the recorded one, or a band ran out of triples."""


API = ("https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/statewide/time-series/"
       "{state}/{measure}/1/{month}/2026-2026.json?base_prd=true&begbaseyear=1901&endbaseyear=2000")
STATE_IDS = range(1, 49)  # NCEI's statewide numbers: 1 Alabama to 48 Wyoming, alphabetical.
# 49 is unused, and 50 (Alaska) and 51 (Hawaii) report a shorter base period than the 1901-2000 normal.
MONTHS = (7, 8)
MONTH_NAMES = {7: "July", 8: "August"}
MEASURES = ("tavg", "pcp")
CACHE = Path.home() / ".cache" / "reasonlineage" / "weather"
# Alaska is left out: it belongs to none of the nine contiguous climate regions (design 4.1).
REGIONS: dict[str, tuple[str, ...]] = {
    "Northeast": ("Connecticut", "Delaware", "Maine", "Maryland", "Massachusetts", "New Hampshire", "New Jersey",
                  "New York", "Pennsylvania", "Rhode Island", "Vermont"),
    "Upper Midwest": ("Iowa", "Michigan", "Minnesota", "Wisconsin"),
    "Ohio Valley": ("Illinois", "Indiana", "Kentucky", "Missouri", "Ohio", "Tennessee", "West Virginia"),
    "Southeast": ("Alabama", "Florida", "Georgia", "North Carolina", "South Carolina", "Virginia"),
    "Northern Rockies and Plains": ("Montana", "Nebraska", "North Dakota", "South Dakota", "Wyoming"),
    "South": ("Arkansas", "Kansas", "Louisiana", "Mississippi", "Oklahoma", "Texas"),
    "Southwest": ("Arizona", "Colorado", "New Mexico", "Utah"),
    "Northwest": ("Idaho", "Oregon", "Washington"),
    "West": ("California", "Nevada"),
}
REGION_OF = {state: region for region, states in REGIONS.items() for state in states}
# (low, high) departure between the first and second place, by measure and band (design 4.3).
BANDS: dict[str, dict[str, tuple[float, float]]] = {
    "tavg": {"easy": (2.0, 1e9), "medium": (1.0, 2.0), "hard": (0.4, 1.0)},
    "pcp": {"easy": (1.5, 1e9), "medium": (0.7, 1.5), "hard": (0.3, 0.7)},
}
BAND_NAMES = ("easy", "medium", "hard")
MAX_PER_STATE = 3  # how often one state may appear in a set
MEASURE_WORDS = {"tavg": "average temperature was furthest above",
                 "pcp": "precipitation was furthest above"}
UNITS = {"tavg": "degrees Fahrenheit", "pcp": "inches"}  # the departure's unit, stated in the question
QUESTION = (
    "In {month} 2026, how did each of these three states compare with its own long-term normal? The normal is "
    "that state's 1901-2000 average for the same month. Compare the departure from that normal in {unit} - the "
    "difference, not the percentage of normal. You have no tools and no web access: reason from what "
    "you know about regional climate and the patterns of that summer.\n\n"
    "Candidates: {candidates}\n\n"
    "Which state's {month} 2026 {measure} its 1901-2000 normal? Rank the three, and give the reasoning that "
    "decides the order, the key evidence, and one observation that would confirm your top pick.")


# --- 4.1 the pool ---

def _get(url: str, tries: int = 4, wait_s: float = 5.0) -> dict[str, Any]:
    """One API reply, tried again after a pause; nothing in the request identifies anyone."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                reply = json.load(response)
            time.sleep(0.2)
            return reply
        except (OSError, ValueError):
            if attempt == tries:
                raise
            time.sleep(wait_s * attempt)
    raise AssertionError("unreachable")


def reading(reply: Mapping[str, Any], month: int) -> tuple[str, float] | None:
    """The state's name and its departure from normal, or None when the month has no departure.

    The name comes from the reply, so no state is ever named by guesswork (design 4.1).
    """
    title = (reply.get("description") or {}).get("title") or ""
    state = title.split(f" {MONTH_NAMES[month]} ")[0].strip()
    record = (reply.get("data") or {}).get(f"2026{month:02d}") or {}
    departure = record.get("departure")
    if not state or departure is None:
        return None
    return state, float(departure)


def fetch_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get,
               state_ids: Sequence[int] = tuple(STATE_IDS)) -> dict[str, dict[str, float]]:
    """Every contiguous state's departure for each month and measure, as {"<month>:<measure>": {state: value}}."""
    pool: dict[str, dict[str, float]] = {}
    for month in MONTHS:
        for measure in MEASURES:
            found: dict[str, float] = {}
            for state_id in state_ids:
                path = Path(cache) / f"{month}-{measure}-{state_id}.json"
                if path.exists():
                    reply = json.loads(path.read_text(encoding="utf-8"))
                else:
                    url = API.format(state=state_id, measure=measure, month=month)
                    try:
                        reply = get(url)
                    except (OSError, ValueError) as exc:
                        raise SourceError(f"could not fetch {url}: {exc}") from None
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(reply), encoding="utf-8")
                read = reading(reply, month)
                if read is not None and read[0] in REGION_OF:
                    found[read[0]] = read[1]
            pool[f"{month}:{measure}"] = dict(sorted(found.items()))
    return pool


def pool_bytes(pool: Mapping[str, Mapping[str, float]]) -> bytes:
    return (json.dumps(pool, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def load_pool(path: str | Path, sha256: str) -> dict[str, dict[str, float]]:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SourceError(f"{path} has sha256 {digest}, not the recorded {sha256}; run `fetch` again")
    return json.loads(data)


def load_index(index: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """The readings the index records, checked against its own sha256.

    The index is committed, so a checkout with no cache rebuilds the same set from it (success criterion 1).
    """
    readings = index["readings"]
    digest = hashlib.sha256(pool_bytes(readings)).hexdigest()
    if digest != index["sha256"]:
        raise SourceError(f"the index's readings have sha256 {digest}, not the recorded {index['sha256']}; "
                          f"run `fetch` again")
    return readings


# --- 4.3 choosing the triples ---

def margin(triple: Sequence[str], values: Mapping[str, float]) -> float:
    """The gap between first and second place, rounded away from the float error of a 0.1-precision subtraction."""
    first, second, _ = sorted((values[state] for state in triple), reverse=True)
    return round(first - second, 4)


def usable(triple: Sequence[str], values: Mapping[str, float], band: tuple[float, float]) -> bool:
    """Three states from three regions whose first-to-second gap falls in the band (design 4.3)."""
    if len({REGION_OF[state] for state in triple}) < 3:
        return False
    first, second, third = sorted((values[state] for state in triple), reverse=True)
    if first == second or second == third:
        return False
    if first <= 0:
        return False  # the question asks which state was furthest above its normal, so one state must be
    low, high = band
    return low <= margin(triple, values) < high


def choose(set_name: str, pool: Mapping[str, Mapping[str, float]], band: str, count: int,
           exclude: Sequence[Sequence[str]] = ()) -> list[dict[str, Any]]:
    """`count` triples, alternating measure and month, each state used at most MAX_PER_STATE times.

    The order of the keys and of the candidate triples is fixed by the set name, so the same set is rebuilt
    identically (design 4.3, 4.4).
    """
    taken = {frozenset(triple) for triple in exclude}
    used: dict[str, int] = {}
    chosen: list[dict[str, Any]] = []
    for index in range(count):
        # measure alternates every task, month every two tasks: tavg/7, pcp/7, tavg/8, pcp/8, tavg/7, ...
        measure = MEASURES[index % len(MEASURES)]
        month = MONTHS[(index // len(MEASURES)) % len(MONTHS)]
        key = f"{month}:{measure}"
        if key not in pool:
            raise SourceError(f"the pool has no {key}; run `fetch` again")
        values = pool[key]
        limits = BANDS[measure][band]
        order = shuffled(["|".join(t) for t in itertools.combinations(sorted(values), 3)], f"{set_name}:{key}:{index}")
        for packed in order:
            triple = tuple(packed.split("|"))
            if frozenset(triple) in taken or not usable(triple, values, limits):
                continue
            if any(used.get(state, 0) >= MAX_PER_STATE for state in triple):
                continue
            taken.add(frozenset(triple))
            for state in triple:
                used[state] = used.get(state, 0) + 1
            chosen.append({"month": month, "measure": measure, "states": list(triple),
                           "departures": {state: values[state] for state in triple},
                           "regions": {state: REGION_OF[state] for state in triple},
                           "margin": margin(triple, values)})
            break
        else:
            raise SourceError(f"{set_name}: only {len(chosen)} of {count} tasks could be built; {key} band "
                              f"{band!r} ran out of triples (a state may appear at most {MAX_PER_STATE} times)")
    return chosen


# --- 4.4 the task and the files ---

def question(task: Mapping[str, Any], order: Sequence[str]) -> str:
    return QUESTION.format(month=MONTH_NAMES[task["month"]], candidates=", ".join(order),
                           measure=MEASURE_WORDS[task["measure"]], unit=UNITS[task["measure"]])


def make_task(set_name: str, index: int, chosen: Mapping[str, Any]) -> dict[str, Any]:
    """One task's file body, gold entry and record."""
    task_id = f"{set_name}-{index + 1:02d}"
    order = shuffled(list(chosen["states"]), task_id)
    winner = max(chosen["states"], key=lambda state: chosen["departures"][state])
    body = {"id": task_id, "question": question(chosen, order), "candidates": order,
            "category": "analytical", "data_sensitivity": "public"}
    gold = {"approved": [winner], "failed": sorted(state for state in chosen["states"] if state != winner)}
    record = {"month": chosen["month"], "measure": chosen["measure"], "departures": chosen["departures"],
              "regions": chosen["regions"], "margin": chosen["margin"], "winner": winner}
    return {"task": body, "gold": gold, "record": record}


def build(set_name: str, band: str, count: int, pool: Mapping[str, Mapping[str, float]], source: Mapping[str, Any],
          tasks_dir: str | Path, gold_dir: str | Path, exclude: Sequence[Sequence[str]] = ()) -> list[Path]:
    """Write the task files, gold.json and generation.json; nothing is written if a band runs out."""
    if band not in BAND_NAMES:
        raise SourceError(f"unknown band {band!r}; use one of {', '.join(BAND_NAMES)}")
    tasks_dir, gold_dir = Path(tasks_dir), Path(gold_dir)
    ids = [f"{set_name}-{i + 1:02d}" for i in range(count)]
    stale = [f"{path} is not built by this set; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise SourceError("; ".join(stale))
    made = [make_task(set_name, i, chosen) for i, chosen in enumerate(choose(set_name, pool, band, count, exclude))]
    bodies = {task["task"]["id"]: json.dumps(task["task"], ensure_ascii=False, indent=2) + "\n" for task in made}
    # A finished run is scored against gold.json, so a task that moved under its own id would score old answers
    # against new truth. Changing a built task means a new set name.
    moved = [f"{tasks_dir / name}.json is already built and this build would change it; use another set name"
             for name, body in bodies.items()
             if (tasks_dir / f"{name}.json").exists()
             and (tasks_dir / f"{name}.json").read_text(encoding="utf-8") != body]
    if moved:
        raise SourceError("; ".join(moved))
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in made:
        path = tasks_dir / f"{task['task']['id']}.json"
        path.write_text(bodies[task["task"]["id"]], encoding="utf-8")
        written.append(path)
    head = dict(source) | {"set": set_name, "band": band}
    for name, body in (("gold.json", {"source": head, "tasks": {t["task"]["id"]: t["gold"] for t in made}}),
                       ("generation.json", {"source": head, "tasks": {t["task"]["id"]: t["record"] for t in made}})):
        (gold_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written


def triples_of(gold_dir: str | Path) -> list[list[str]]:
    """The triples a built set used, for the next set to exclude."""
    path = Path(gold_dir) / "generation.json"
    if not path.exists():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    return [sorted(task["departures"]) for task in record["tasks"].values()]
