"""bioRxiv preprints as the source of gold set A (bioRxiv design).

Each task shows the background and methods sentences of an abstract first posted on or after 2026-07-01 and three
results: the abstract's own results and two versions rewritten by DeepSeek, which is outside the panel. The truth is
what the study reported, so it cannot be worked out from the prompt.
"""

import asyncio
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..backends.base import BackendError, ModelBackend, ModelRequest
from .build import shuffled

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


# The API writes some characters as markup ("{beta}", "[&ge;]"). The real result is the abstract's own text, so
# undecoded markup would set it apart from DeepSeek's rewrites (final review, 2026-10-02).
SYMBOLS = {"micro": "µ", "degrees": "°", "+/-": "±", "-": "−", "approx": "≈", "square": "²", "triangleup": "△",
           "schwa": "ə", "propto": "∝", "uparrow": "↑", "downarrow": "↓", ",": ",", "varepsilon": "ε", "varphi": "φ"}
# List, figure and glued-heading residue of structured abstracts: left out rather than repaired.
RESIDUE = re.compile(r"\b[OC]_(?:LI|FIG|TBL)|O_LINK|\b(?:Summary|Significance Statement|Highlights|Graphical Abstract|"
                     r"Abstract|Background|Introduction|Methods|Results|Conclusions?|Objectives?|Aims?|Purpose)[A-Z][a-z]")


def _symbol(match: re.Match) -> str:
    name = match.group(1)
    if name in SYMBOLS:
        return SYMBOLS[name]
    try:
        return unicodedata.lookup(f"GREEK {'CAPITAL' if name[0].isupper() else 'SMALL'} LETTER {name.upper()}")
    except KeyError:
        return match.group(0)  # unknown markup stays, and the abstract is left out below


def clean_abstract(text: str) -> str | None:
    """The abstract with the API's markup decoded; None when residue or unknown markup is left."""
    if RESIDUE.search(text):
        return None
    text = re.sub(r"\{([^{}\s]{1,20})\}", _symbol, text)
    text = html.unescape(re.sub(r"\[(&[a-zA-Z]+;|~)\]", r"\1", text))
    if re.search(r"\{[^{}]*\}|&[a-zA-Z#0-9]+;", text):
        return None
    return " ".join(text.split())


def build_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """The kept papers of the five fields, one per DOI, in DOI order.

    A paper withdrawn in any version is left out, though its first version looks usable on its own.
    """
    records = [(category, record) for category in CATEGORIES for record in fetch_category(category, cache, get)]
    withdrawn = {r["doi"] for _, r in records if r.get("type") == "withdrawn" or WITHDRAWN.search(r.get("title") or "")}
    papers: dict[str, dict[str, Any]] = {}
    for category, record in records:
        if record["doi"] in withdrawn or record["doi"] in papers or not keep(record):
            continue
        abstract = clean_abstract(record["abstract"])
        if abstract is not None:
            papers[record["doi"]] = {"doi": record["doi"], "category": category, "date": record["date"],
                                     "title": " ".join(record["title"].split()), "abstract": abstract}
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
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[^\W_])")  # any letter or digit may start one
_LAST_WORD = re.compile(r"(?<![\w\-}])([A-Za-z][A-Za-z.]*)\.$")  # a whole word, not the end of "2D" or "κB"


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


# --- 4.3-4.5 DeepSeek ---

LETTERS = ("A", "B", "C")
LABEL_SYSTEM = ("You read the abstract of a biology preprint, split into numbered sentences. Find the first sentence "
                "that reports a finding or a conclusion of this study itself (what the authors found or showed, not "
                "what was known before or what they set out to do or how they did it). Every sentence from that one "
                "to the end will be treated as the study's results.")
ALTER_SYSTEM = (
    "You write two false versions of the results passage of a biology abstract, for a test in which experts read "
    "the background and methods and must pick the real results from three versions. Both versions must never "
    "contradict anything the background and methods state (organisms, cells, targets, techniques, definitions, "
    "numbers): change only what the study found, so that the background alone cannot rule a version out.\n"
    '- "reversed": reverse the direction of one central finding (increase and decrease, promotes and inhibits, '
    "required and dispensable, present and absent) and adjust the rest so the passage stays internally consistent. "
    "If the passage reports how well a method performs, do not make the method fail; reverse which comparison, "
    "condition or group shows the effect instead.\n"
    '- "altered": keep the direction but change one central detail so that the conclusion differs: the cell type or '
    "tissue, the target, the condition, the mechanism, or the size of the effect.\n"
    "Both versions must read like results that authors would publish: keep the authors' confident, positive "
    "framing, keep every value physically possible (no negative rates or counts), and keep the number of sentences, "
    "the length (within 20%), the style, the terminology and the number format of the real passage. A reader who "
    "knows only that the passage comes from a published abstract must not be able to reject either version for "
    "sounding like a failed study, for an impossible value or for an internal contradiction. Each version must reach "
    "a conclusion clearly different from the real passage and from the other version. Never say that anything was "
    "changed.")
TELL_SYSTEM = ("Exactly one of three passages is the real results text of a published biology abstract; the other "
               "two were rewritten. Say which one is real.")
LABEL_SCHEMA = {"type": "object", "properties": {"first_result": {"type": "integer"}}, "required": ["first_result"],
                "additionalProperties": False}
ALTER_SCHEMA = {"type": "object", "properties": {"reversed": {"type": "string"}, "altered": {"type": "string"}},
                "required": ["reversed", "altered"], "additionalProperties": False}
TELL_SCHEMA = {"type": "object", "properties": {"real": {"type": "string", "enum": list(LETTERS)}},
               "required": ["real"], "additionalProperties": False}
ROTATIONS = ((0, 1, 2), (1, 2, 0), (2, 0, 1))  # the real passage lands on A, C and B


def _request(member: Any, system: str, prompt: str, schema: Mapping[str, Any]) -> ModelRequest:
    return ModelRequest(system=system, prompt=prompt, model=member.model, effort=member.effort,
                        json_schema=dict(schema), timeout_s=1800, max_tokens=64000)


def label_request(member: Any, parts: Sequence[str]) -> ModelRequest:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(parts, 1))
    return _request(member, LABEL_SYSTEM, f"Abstract:\n{numbered}", LABEL_SCHEMA)


def alter_request(member: Any, context: str, result: str) -> ModelRequest:
    return _request(member, ALTER_SYSTEM, f"Background and methods:\n{context}\n\nReal results:\n{result}", ALTER_SCHEMA)


def tell_request(member: Any, passages: Sequence[str], context: str | None = None) -> ModelRequest:
    """The wording check (no context) or, with `context`, the background check."""
    lines = "\n\n".join(f"Result {letter}: {text}" for letter, text in zip(LETTERS, passages))
    prompt = f"Background and methods:\n{context}\n\n{lines}" if context else lines
    return _request(member, TELL_SYSTEM, prompt, TELL_SCHEMA)


async def _ask(backend: ModelBackend, request: ModelRequest, valid: Callable[[Mapping[str, Any]], bool]):
    """The answer's data, asking once more if the call fails or the answer is not usable; None after two tries."""
    for _ in range(2):
        try:
            data = (await backend.complete(request)).data
        except BackendError:
            continue
        if isinstance(data, Mapping) and valid(data):
            return dict(data)
    return None


async def make_candidate(paper: Mapping[str, Any], backend: ModelBackend, member: Any) -> dict[str, Any]:
    """One paper through splitting, rewriting and the wording check; status "kept" or "dropped" with the reason."""
    entry: dict[str, Any] = {key: paper[key] for key in ("doi", "category", "date", "title", "abstract")}

    def dropped(reason: str) -> dict[str, Any]:
        return entry | {"status": "dropped", "reason": reason}

    parts = sentences(paper["abstract"])
    entry["sentences"] = parts
    label = await _ask(backend, label_request(member, parts), lambda d: "first_result" in d)
    if label is None:
        return dropped("DeepSeek gave no usable split")
    entry["first_result"] = label["first_result"]
    problems = split_problems(parts, label["first_result"])
    if problems:
        return dropped("; ".join(problems))
    k = label["first_result"]
    entry["context"], entry["result"] = " ".join(parts[:k - 1]), " ".join(parts[k - 1:])
    rewrite = await _ask(backend, alter_request(member, entry["context"], entry["result"]),
                         lambda d: not alteration_problems(entry["result"], d.get("reversed"), d.get("altered")))
    if rewrite is None:
        return dropped("DeepSeek gave no usable rewritten results")
    entry["reversed"], entry["altered"] = (" ".join(rewrite[k].split()) for k in ("reversed", "altered"))
    texts = (entry["result"], entry["reversed"], entry["altered"])
    votes = await asyncio.gather(*(_ask(backend, tell_request(member, [texts[i] for i in order]),
                                        lambda d: d.get("real") in LETTERS) for order in ROTATIONS))
    if any(v is None for v in votes):
        return dropped("DeepSeek gave no usable answer in the wording check")
    entry["tell"] = [LETTERS[order.index(0)] == v["real"] for order, v in zip(ROTATIONS, votes)]
    if all(entry["tell"]):
        return dropped("the real result can be told from the wording alone (3 of 3)")
    # The first pilot hit the ceiling because rewrites contradicted the background (pilot, 2026-10-02).
    votes = await asyncio.gather(*(_ask(backend, tell_request(member, [texts[i] for i in order], entry["context"]),
                                        lambda d: d.get("real") in LETTERS) for order in ROTATIONS))
    if any(v is None for v in votes):
        return dropped("DeepSeek gave no usable answer in the background check")
    entry["tell_context"] = [LETTERS[order.index(0)] == v["real"] for order, v in zip(ROTATIONS, votes)]
    if all(entry["tell_context"]):
        return dropped("the real result follows from the background (3 of 3)")
    return entry | {"status": "kept"}


async def candidates(set_name: str, papers: Sequence[Mapping[str, Any]], per_category: int, backend: ModelBackend,
                     member: Any, exclude: set[str] = frozenset(), previous: Sequence[Mapping[str, Any]] = (),
                     dropped: set[str] = frozenset()) -> list[dict[str, Any]]:
    """Papers tried for each field in sample order until `per_category` are kept (4.2); earlier results are reused.

    `exclude` skips papers (another set's); `dropped` are papers the review dropped: they stay on record, so the
    review can still name them, but do not count toward `per_category`.
    """
    done = {entry["doi"]: dict(entry) for entry in previous}
    by_doi = {paper["doi"]: paper for paper in papers}

    def usable(tried: list[dict[str, Any]]) -> int:
        return sum(e["status"] == "kept" and e["doi"] not in dropped for e in tried)

    async def field(category: str) -> list[dict[str, Any]]:
        order = shuffled(sorted(d for d, p in by_doi.items() if p["category"] == category), f"{set_name}:{category}")
        tried: list[dict[str, Any]] = []
        for doi in order:
            if usable(tried) >= per_category:
                return tried
            if doi in exclude:
                continue
            tried.append(done.get(doi) or await make_candidate(by_doi[doi], backend, member))
        if usable(tried) < per_category:
            raise SourceError(f"{category}: only {usable(tried)} of {per_category} papers usable after trying all "
                              f"{len(tried)}")
        return tried

    return [entry for batch in await asyncio.gather(*(field(c) for c in CATEGORIES)) for entry in batch]


# --- 4.6 review and 4.7 files ---

class ReviewError(ValueError):
    """The review record breaks a rule of bioRxiv design 4.6, or the task folder holds files `build` does not make."""


QUESTION = ("Three candidate results follow. Exactly one is what this study reported.\n{lines}\n"
            "Which result did this study report? Rank the candidates, and give the mechanism, the key evidence, and "
            "a validation experiment for the top pick.")


def review_sample(found: Sequence[Mapping[str, Any]], dropped: set[str] = frozenset()) -> list[str]:
    """The DOIs to review: the first kept paper of each field not dropped in review (4.6)."""
    sample = []
    for category in CATEGORIES:
        for entry in found:
            if entry["category"] == category and entry["status"] == "kept" and entry["doi"] not in dropped:
                sample.append(entry["doi"])
                break
    return sample


def review_sheet(found: Sequence[Mapping[str, Any]], sample: Sequence[str]) -> str:
    by_doi = {entry["doi"]: entry for entry in found}
    lines = ["# Review sheet", "",
             "For each paper: are both rewritten results plausible yet clearly a different conclusion from the real "
             "one, and does the background leak no result? Write review.json as "
             '{"keep": [doi, ...], "drop": [{"doi": ..., "why": ...}]}.', ""]
    for doi in sample:
        e = by_doi[doi]
        lines += [f"## {e['category']} — {doi}", "", f"**Background and methods.** {e['context']}", "",
                  f"**Real result.** {e['result']}", "", f"**Reversed.** {e['reversed']}", "",
                  f"**Altered.** {e['altered']}", ""]
    return "\n".join(lines)


def check_review(review: Mapping[str, Any], found: Sequence[Mapping[str, Any]]) -> list[str]:
    """What breaks the review rules (4.6); empty when the record is usable."""
    kept = {e["doi"] for e in found if e["status"] == "kept"}
    keep_list = list(review.get("keep", []))
    drops = list(review.get("drop", []))
    named = keep_list + [d.get("doi") for d in drops]
    problems = [f"{doi}: reviewed twice" for doi in sorted({d for d in named if named.count(d) > 1})]
    problems += [f"{doi}: not a kept candidate" for doi in named if doi not in kept]
    problems += [f"{d.get('doi')}: dropped without a reason ('why')" for d in drops if not str(d.get("why", "")).strip()]
    dropped = {d.get("doi") for d in drops}
    problems += [f"{doi}: not reviewed" for doi in review_sample(found, dropped) if doi not in named]
    return problems


def build(set_name: str, found: Sequence[Mapping[str, Any]], review: Mapping[str, Any], per_category: int,
          source: Mapping[str, Any], tasks_dir: str | Path, gold_path: str | Path) -> list[Path]:
    """Write the task files and the gold file; nothing is written if the review breaks a rule (4.7)."""
    problems = check_review(review, found)
    if problems:
        raise ReviewError("; ".join(problems))
    dropped = {d["doi"] for d in review.get("drop", [])}
    chosen = []
    for category in CATEGORIES:
        usable = [e for e in found if e["category"] == category and e["status"] == "kept" and e["doi"] not in dropped]
        if len(usable) < per_category:
            raise ReviewError(f"{category}: {len(usable)} usable papers for {per_category} tasks; run `candidates` "
                              f"again to replace the papers dropped in review")
        chosen += usable[:per_category]
    ids = [f"{set_name}-{i:02d}" for i in range(1, len(chosen) + 1)]
    tasks_dir, gold_path = Path(tasks_dir), Path(gold_path)
    stale = [f"{path} is not built by this review; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise ReviewError("; ".join(stale))
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold = {"source": dict(source), "tasks": {}}
    written = []
    # The real result's letter is spread evenly over the set, in an order fixed by the set name (final review).
    real_letters = shuffled([LETTERS[i % len(LETTERS)] for i in range(len(chosen))], f"{set_name}:letters")
    for task_id, entry, real in zip(ids, chosen, real_letters):
        others = shuffled([x for x in LETTERS if x != real], task_id)
        letter = {"result": real, "reversed": others[0], "altered": others[1]}
        lines = "\n".join(f"- Result {letter[kind]}: {entry[kind]}" for kind in sorted(letter, key=letter.get))
        body = {"id": task_id, "question": entry["context"] + "\n\n" + QUESTION.format(lines=lines),
                "candidates": [f"Result {x}" for x in LETTERS], "category": "analytical", "data_sensitivity": "public"}
        path = tasks_dir / f"{task_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        gold["tasks"][task_id] = {"approved": [f"Result {letter['result']}"],
                                  "failed": sorted(f"Result {letter[k]}" for k in ("reversed", "altered")),
                                  "doi": entry["doi"]}
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
