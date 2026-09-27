"""Append-only JSONL record of a run: every candidate, every raw judge score, every selection."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import Candidate
from .selection import SelectionResult


class LineageLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def candidate_created(self, candidate: Candidate) -> None:
        self.write(
            "candidate.created",
            id=candidate.id,
            author=candidate.author,
            operator=candidate.operator,
            parent_ids=list(candidate.parent_ids),
            generation=candidate.generation,
            content=candidate.content,
        )

    def candidate_scored(self, candidate: Candidate) -> None:
        self.write(
            "candidate.scored",
            id=candidate.id,
            fitness=candidate.fitness,
            scores=candidate.scores,
            judges=[asdict(score) for score in candidate.judge_scores],
            critique=candidate.critique,
        )

    def selection(self, generation: int, result: SelectionResult) -> None:
        self.write(
            "selection",
            generation=generation,
            survivors=[c.id for c in result.survivors],
            eliminated=[c.id for c in result.eliminated],
            excluded=[c.id for c in result.excluded],
            tie_break_swap=result.tie_break_swap,
        )

    @staticmethod
    def read(path: str | Path) -> list[dict]:
        with Path(path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
