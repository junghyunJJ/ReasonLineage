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


# --- 4.3 sentences and the checks on DeepSeek's work ---

MAX_RESULT_WORDS = 400
ABBREVIATIONS = {"e.g", "i.e", "al", "fig", "figs", "vs", "approx", "ca", "cf", "no", "dr", "ref", "refs", "eq",
                 "resp", "incl", "st", "sp", "spp"}
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_LAST_WORD = re.compile(r"([A-Za-z][A-Za-z.]*)\.$")


def sentences(text: str) -> list[str]:
    """The abstract split into sentences; abbreviations, initials and decimals do not end one."""
    parts, start = [], 0
    for match in _BOUNDARY.finditer(text):
        word = _LAST_WORD.search(text[start:match.start()])
        if word and (word.group(1).lower() in ABBREVIATIONS or re.fullmatch(r"[A-Z]", word.group(1))):
            continue
        parts.append(text[start:match.start()].strip())
        start = match.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def split_problems(parts: Sequence[str], first_result: Any) -> list[str]:
    """Why the split at `first_result` (1-based) cannot make a task; empty when it can (4.3)."""
    if not isinstance(first_result, int) or not 2 <= first_result <= len(parts):
        return [f"first result sentence {first_result!r} leaves no background or no result"]
    words = len(" ".join(parts[first_result - 1:]).split())
    return [f"the results have {words} words, more than {MAX_RESULT_WORDS}"] if words > MAX_RESULT_WORDS else []


def alteration_problems(result: str, reversed_: Any, altered: Any) -> list[str]:
    """Why the two rewritten results cannot be used; empty when they can (4.4)."""
    if not isinstance(reversed_, str) or not isinstance(altered, str):
        return ["the rewritten results are not text"]
    norm = [" ".join(t.split()).casefold() for t in (result, reversed_, altered)]
    problems = []
    if len(set(norm)) < 3:
        problems.append("a rewritten result repeats the real one or the other")
    for name, text in (("reversed", reversed_), ("altered", altered)):
        ratio = len(text) / max(len(result), 1)
        if not 0.75 <= ratio <= 1.25:
            problems.append(f"the {name} result is {ratio:.2f} times as long as the real one")
    return problems
