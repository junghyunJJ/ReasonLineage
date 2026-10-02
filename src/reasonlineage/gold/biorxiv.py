"""bioRxiv preprints as the source of gold set A (bioRxiv design).

Each task shows the background and methods sentences of an abstract first posted on or after 2026-07-01 and three
results: the abstract's own results and two versions rewritten by DeepSeek, which is outside the panel. The truth is
what the study reported, so it cannot be worked out from the prompt.
"""

import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

API = "https://api.biorxiv.org/details/biorxiv/{start}/{end}/{cursor}?category={category}"
START, END = "2026-07-01", "2026-10-01"
CATEGORIES = ("pharmacology_and_toxicology", "cancer_biology", "immunology", "neuroscience", "cell_biology")
MIN_WORDS = 120
CACHE = Path.home() / ".cache" / "reasonlineage" / "biorxiv"
WITHDRAWN = re.compile(r"^\s*withdrawn|\b(manuscript|preprint|article) (has been|was|is being) withdrawn", re.I)


class SourceError(RuntimeError):
    """The bioRxiv API failed, the saved pool is not the recorded one, or a field ran out of usable papers."""


# --- 4.1 the pool ---

def _get(url: str, tries: int = 4, wait_s: float = 5.0) -> dict[str, Any]:
    """One API page; the server sometimes drops a connection, so a failure is tried again after a pause."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                page = json.load(response)
            time.sleep(0.5)  # be gentle with a free API
            return page
        except (OSError, ValueError):
            if attempt == tries:
                raise
            time.sleep(wait_s * attempt)
    raise AssertionError("unreachable")


def fetch_category(category: str, cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """Every record the API lists for `category` in the window, page by page; each page is fetched once."""
    records: list[dict[str, Any]] = []
    cursor = 0
    while True:
        path = Path(cache) / category / f"{cursor}.json"
        if path.exists():
            page = json.loads(path.read_text(encoding="utf-8"))
        else:
            url = API.format(start=START, end=END, cursor=cursor, category=category)
            try:
                page = get(url)
            except (OSError, ValueError) as exc:
                raise SourceError(f"could not fetch {url}: {exc}") from None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(page), encoding="utf-8")
        batch = page.get("collection") or []
        records += batch
        cursor += len(batch)
        if not batch or cursor >= int(page["messages"][0].get("total", 0)):
            return records


def keep(record: Mapping[str, Any]) -> bool:
    """A first version posted in the window, new results, not in a journal, a real abstract, not withdrawn (4.1)."""
    abstract = record.get("abstract") or ""
    return (record.get("version") == "1" and START <= (record.get("date") or "") <= END
            and record.get("type") == "new results" and record.get("published") == "NA"
            and len(abstract.split()) >= MIN_WORDS
            and not WITHDRAWN.search(record.get("title") or "") and not WITHDRAWN.search(abstract))


def build_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """The kept papers of the five fields, one per DOI, in DOI order."""
    papers: dict[str, dict[str, Any]] = {}
    for category in CATEGORIES:
        for record in fetch_category(category, cache, get):
            if keep(record) and record["doi"] not in papers:
                papers[record["doi"]] = {"doi": record["doi"], "category": category, "date": record["date"],
                                         "title": " ".join(record["title"].split()),
                                         "abstract": " ".join(record["abstract"].split())}
    return [papers[doi] for doi in sorted(papers)]


def pool_bytes(papers: Sequence[Mapping[str, Any]]) -> bytes:
    return (json.dumps(list(papers), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def load_pool(path: str | Path, sha256: str) -> list[dict[str, Any]]:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SourceError(f"{path} has sha256 {digest}, not the recorded {sha256}; run `fetch` again")
    return json.loads(data)
