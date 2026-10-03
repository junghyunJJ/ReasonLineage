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
STATE_IDS = range(1, 51)  # NCEI's statewide numbers, alphabetical
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
