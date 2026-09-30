"""PMID check (spec 7.2): is each cited PMID a real paper about the item it supports?

A number that exists is not enough: 47 of 50 random numbers between 10M and 39M were real
papers (2026-09-29). So each record's title, abstract, MeSH headings, and substance names
must name the item.
"""

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..engine.events import read_events

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


@dataclass(frozen=True)
class PubmedRecord:
    pmid: str
    title: str
    text: str  # title, abstract, MeSH headings, and substance names


def efetch(pmids: Sequence[str]) -> str:
    query = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    with urllib.request.urlopen(f"{EFETCH}?{query}", timeout=60) as response:
        return response.read().decode("utf-8")


def parse_efetch(xml_text: str) -> dict[str, PubmedRecord]:
    records = {}
    for article in ET.fromstring(xml_text).iter("PubmedArticle"):
        pmid = (article.findtext("MedlineCitation/PMID") or "").strip()
        title_node = article.find("MedlineCitation/Article/ArticleTitle")
        title = "".join(title_node.itertext()).strip() if title_node is not None else ""
        abstract = " ".join("".join(node.itertext()) for node in article.iter("AbstractText"))
        mesh = " ".join(node.text or "" for node in article.iter("DescriptorName"))
        substances = " ".join(node.text or "" for node in article.iter("NameOfSubstance"))
        records[pmid] = PubmedRecord(pmid, title, " ".join([title, abstract, mesh, substances]))
    return records


def fetch_records(pmids: Sequence[str], fetch: Callable[[Sequence[str]], str] = efetch,
                  batch: int = 200, pause_s: float = 0.34) -> dict[str, PubmedRecord]:
    unique = sorted(set(pmids))
    found: dict[str, PubmedRecord] = {}
    for start in range(0, len(unique), batch):
        found.update(parse_efetch(fetch(unique[start:start + batch])))
        if start + batch < len(unique):
            time.sleep(pause_s)  # NCBI allows 3 requests per second without a key
    return found


def classify(item: str, record: PubmedRecord | None) -> str:
    """"missing" (no such PMID), "match" (the paper names the item), or "unrelated"."""
    if record is None:
        return "missing"
    text = " ".join(record.text.split()).casefold()
    parts = [p.strip() for p in item.split("–")] if "–" in item else [item]  # an A–B pair needs both names
    return "match" if all(" ".join(p.split()).casefold() in text for p in parts if p) else "unrelated"


def pmid_uses(events: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every cited PMID with its answer, item, and origin (inherited from a parent or new),
    and the ranked items that cite nothing."""
    cited: dict[str, dict[str, set[str]]] = {}
    uses, empty = [], []
    for event in events:
        if event["event"] != "candidate.created":
            continue
        ranking = event["answer"]["ranking"]
        cited[event["id"]] = {entry["item"]: set(entry["pmids"]) for entry in ranking}
        for entry in ranking:
            if not entry["pmids"]:
                empty.append({"candidate": event["id"], "generation": event["generation"], "item": entry["item"]})
            for pmid in entry["pmids"]:
                inherited = any(pmid in cited.get(parent, {}).get(entry["item"], set()) for parent in event["parents"])
                uses.append({"candidate": event["id"], "generation": event["generation"], "author": event["author"],
                             "operator": event["operator"], "item": entry["item"], "pmid": pmid,
                             "origin": "inherited" if inherited else "new"})
    return uses, empty


def run_pmid_check(run_dir: str | Path, fetch: Callable[[Sequence[str]], str] = efetch) -> dict[str, Any]:
    run_dir = Path(run_dir)
    uses, empty = pmid_uses(read_events(run_dir / "events.jsonl"))
    records = fetch_records([u["pmid"] for u in uses], fetch=fetch) if uses else {}
    out_dir = run_dir / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {"match": 0, "unrelated": 0, "missing": 0}
    with (out_dir / "pmid.jsonl").open("w", encoding="utf-8") as handle:
        for use in uses:
            record = records.get(use["pmid"])
            verdict = classify(use["item"], record)
            counts[verdict] += 1
            handle.write(json.dumps({**use, "verdict": verdict, "title": record.title if record else None}, ensure_ascii=False) + "\n")
    summary = {"citations": len(uses), **counts, "items_without_pmids": len(empty)}
    (out_dir / "pmid_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
