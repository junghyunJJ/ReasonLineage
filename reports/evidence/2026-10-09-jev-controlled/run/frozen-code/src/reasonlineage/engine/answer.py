"""Answer format B: free prose plus a ranking with promisingness, confidence, and PMIDs (spec 5.5)."""

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_PMID = re.compile(r"^\s*(?:pmid\s*[:#]?\s*)?(\d{1,9})\s*$", re.I)


def answer_schema(candidates: Sequence[str] | None, open_items: tuple[int, int] = (3, 10)) -> dict[str, Any]:
    """JSON schema for an author's answer. With a candidate list, the ranking must hold exactly those names."""
    item_name: dict[str, Any] = {"type": "string"}
    if candidates:
        item_name = {"type": "string", "enum": list(candidates)}
        low = high = len(candidates)
    else:
        low, high = open_items
    item = {
        "type": "object",
        "properties": {
            "item": item_name,
            "promisingness": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "pmids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["item", "promisingness", "confidence", "pmids"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "ranking": {"type": "array", "items": item, "minItems": low, "maxItems": high},
        },
        "required": ["answer", "ranking"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class AnswerIssues:
    hard: tuple[str, ...] = ()  # the ranking does not match the task's items
    soft: tuple[str, ...] = ()  # a ranked item is never named in the prose

    def describe(self) -> str:
        return "\n".join(f"- {issue}" for issue in (*self.hard, *self.soft))


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


def normalize_pmids(values: Sequence[Any]) -> list[str]:
    """Keep entries that are a PMID ("29967351" or "PMID: 29967351"); drop others and repeats."""
    out: list[str] = []
    for value in values or []:
        match = _PMID.match(str(value))
        if match and match.group(1) not in out:
            out.append(match.group(1))
    return out


def _unit(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{field} must be a number in [0, 1], got {value!r}")
    return float(value)


def normalize_answer(data: Any, candidates: Sequence[str] | None) -> dict[str, Any]:
    """A clean copy: trimmed text, candidate names in the task's spelling, clean PMIDs.
    Raises ValueError when the structure itself is wrong."""
    if not isinstance(data, Mapping) or not isinstance(data.get("answer"), str) or not isinstance(data.get("ranking"), list):
        raise ValueError("an answer needs a string 'answer' and a list 'ranking'")
    canonical = {_key(c): c for c in candidates or ()}
    ranking = []
    for entry in data["ranking"]:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("item"), str):
            raise ValueError(f"ranking entry is not an item object: {entry!r}")
        name = " ".join(entry["item"].split())
        pmids = entry.get("pmids")
        if pmids is not None and not isinstance(pmids, list):
            raise ValueError(f"pmids must be a list of PMIDs, got {pmids!r}")
        ranking.append({
            "item": canonical.get(_key(name), name),
            "promisingness": _unit(entry.get("promisingness"), "promisingness"),
            "confidence": _unit(entry.get("confidence"), "confidence"),
            "pmids": normalize_pmids(pmids or []),
        })
    return {"answer": data["answer"].strip(), "ranking": ranking}


def validate_answer(data: Mapping[str, Any], candidates: Sequence[str] | None) -> AnswerIssues:
    items = [entry["item"] for entry in data["ranking"]]
    keys = [_key(item) for item in items]
    hard = []
    if not items:
        hard.append("The ranking is empty.")
    if candidates:
        expected = {_key(c) for c in candidates}
        missing = [c for c in candidates if _key(c) not in keys]
        extra = [item for item in items if _key(item) not in expected]
        repeated = sorted({item for item in items if keys.count(_key(item)) > 1})
        if missing:
            hard.append(f"The ranking leaves out: {', '.join(missing)}.")
        if extra:
            hard.append(f"The ranking has items that are not in the task: {', '.join(extra)}.")
        if repeated:
            hard.append(f"The ranking lists these items more than once: {', '.join(repeated)}.")
    elif len(set(keys)) != len(keys):
        hard.append("The ranking lists an item more than once.")
    prose = _key(data["answer"])
    soft = [f"The prose never names the ranked item {item}." for item in items if _key(item) not in prose]
    return AnswerIssues(tuple(hard), tuple(soft))


def render_for_judge(data: Mapping[str, Any]) -> str:
    """The prose with the final ranking block under it; judges and the J1 gate see exactly this."""
    lines = [data["answer"], "", "Final ranking:"]
    for rank, entry in enumerate(data["ranking"], 1):
        pmids = ", ".join(entry["pmids"]) or "none"
        lines.append(
            f"{rank}. {entry['item']} (promisingness {entry['promisingness']:.2f}, "
            f"confidence {entry['confidence']:.2f}; PMIDs: {pmids})"
        )
    return "\n".join(lines)


def top_item(data: Mapping[str, Any]) -> str:
    return data["ranking"][0]["item"]


def ranking_line(data: Mapping[str, Any]) -> str:
    return " > ".join(entry["item"] for entry in data["ranking"])


def to_content(data: Mapping[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def from_content(content: str) -> dict[str, Any]:
    return json.loads(content)
