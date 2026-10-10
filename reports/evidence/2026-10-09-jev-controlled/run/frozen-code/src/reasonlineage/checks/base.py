"""What every checker returns: probabilities per question, the way jev reports them."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .questions import Question


class CheckerError(RuntimeError):
    """A checker could not answer (network, server, or unreadable output)."""


@dataclass(frozen=True)
class CheckAnswer:
    kind: str                            # "noul" | "choice" | "score"
    probabilities: Mapping[str, float]   # noul: yes/no; choice: option -> p; score: "0".."n" -> p

    @property
    def value(self) -> float:
        """P(yes) for noul, the expected level for score, the top probability for choice."""
        if self.kind == "noul":
            return self.probabilities.get("yes", 0.0)
        if self.kind == "score":
            return sum(int(level) * p for level, p in self.probabilities.items())
        return max(self.probabilities.values())

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "probabilities": dict(self.probabilities), "value": round(self.value, 4)}


@dataclass(frozen=True)
class CheckResult:
    model: str
    answers: Mapping[str, CheckAnswer]
    usage: Mapping[str, int] | None = None


class Checker(Protocol):
    name: str
    pinned_version: str | None

    async def ask(self, state: str, questions: Sequence[Question]) -> CheckResult: ...


def check_key(checker: str, questions: Sequence[Question], state: str) -> str:
    """The same checker, questions, and text give the same key; results are reused by it."""
    payload = {"checker": checker, "questions": [q.to_dict() for q in questions], "state": state}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
