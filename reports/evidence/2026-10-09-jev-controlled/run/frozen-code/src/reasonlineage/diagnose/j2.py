"""J2 (spec 7.1): after the run, ask the checker three kinds of questions about the stored text.

Results go to diagnostics/j2.jsonl. Running it again skips what already has an answer and
retries what failed.
"""

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..checks.base import Checker, CheckerError, check_key
from ..checks.questions import j2_question
from ..engine.config import ConfigError
from ..engine.events import read_events
from ..protocol import ProtocolSpec


def load_gold_items(path: str | Path) -> list[dict[str, str]]:
    """{"items": [{"item": "...", "outcome_date": "YYYY-MM-DD"}]} -> the list of items."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = [{"item": str(e["item"]), "outcome_date": str(e["outcome_date"])} for e in raw["items"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"gold items file {path}: {exc}") from None
    return items


def j2_jobs(events: Sequence[Mapping[str, Any]], protocol: ProtocolSpec, question: str,
            gold_items: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    style = j2_question(protocol, "style_inflation")
    severity = j2_question(protocol, "critique_severity")
    jobs = []
    for event in events:
        if event["event"] == "candidate.created":
            prose = event["answer"]["answer"]
            jobs.append({"kind": "style_inflation", "candidate": event["id"], "state": prose, "questions": [style]})
            for gold in gold_items:
                jobs.append({
                    "kind": "outcome_mention", "candidate": event["id"], "item": gold["item"],
                    "outcome_date": gold["outcome_date"], "state": f"Question:\n{question}\n\nAnswer:\n{prose}",
                    "questions": [j2_question(protocol, "outcome_mention", gold_item=gold["item"])],
                })
        elif event["event"] == "judge.scored":
            jobs.append({
                "kind": "critique_severity", "candidate": event["candidate"], "judge": event["judge"],
                "author": event["author"], "state": "\n".join(f"- {c}" for c in event["critique"]), "questions": [severity],
            })
    return jobs


async def run_j2(run_dir: str | Path, checker: Checker, protocol: ProtocolSpec, question: str,
                 gold_items: Sequence[Mapping[str, str]] = ()) -> Path:
    run_dir = Path(run_dir)
    out = run_dir / "diagnostics" / "j2.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {r["key"] for r in read_events(out) if r.get("error") is None}
    for job in j2_jobs(read_events(run_dir / "events.jsonl"), protocol, question, gold_items):
        key = check_key(checker.name, job["questions"], job["state"])
        if key in done:
            continue
        record = {k: v for k, v in job.items() if k not in ("state", "questions")}
        record.update({"key": key, "checker": checker.name, "protocol_hash": protocol.hash})
        try:
            result = await checker.ask(job["state"], job["questions"])
            answers = {name: a.to_dict() for name, a in result.answers.items()}
            record.update({"model": result.model, "answers": answers, "error": None})
            done.add(key)
        except CheckerError as exc:
            record.update({"model": None, "answers": None, "error": str(exc)})
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out
