"""Candidate and judge-score records."""

from dataclasses import dataclass, field
from typing import Mapping

# How a candidate came to exist. "recovery" is the one fresh seed or radical
# mutation allowed after stagnation is detected.
OPERATORS = frozenset({"seed", "mutation", "crossover", "recovery"})


@dataclass(frozen=True)
class JudgeScore:
    """One judge's raw scores and critique for one candidate."""

    judge: str
    scores: Mapping[str, float]
    critique: tuple[str, ...] = ()


@dataclass
class Candidate:
    """One individual: a complete answer (ranking, mechanism, validation plan) and its lineage.

    `author` is the backend that actually wrote `content`. It is never inherited
    from a parent; panel recusal depends on it being truthful.
    """

    id: str
    content: str
    author: str
    operator: str = "seed"
    parent_ids: tuple[str, ...] = ()
    generation: int = 0
    judge_scores: list[JudgeScore] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    fitness: float | None = None
    critique: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.operator not in OPERATORS:
            raise ValueError(f"unknown operator {self.operator!r}; expected one of {sorted(OPERATORS)}")
        if self.operator in {"mutation", "crossover"} and not self.parent_ids:
            raise ValueError(f"{self.operator} candidate {self.id!r} needs parent_ids")

    @property
    def is_scored(self) -> bool:
        return self.fitness is not None
