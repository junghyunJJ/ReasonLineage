"""The evolution state machine (SKILL.md v1.6.0, State Machine).

scoring -> ready_to_select -> mutating -> scoring ... -> completed | failed

The engine drives it: register candidates, record panel scores, call select().
This class only enforces the order, the limits, and the arithmetic.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence

from .fitness import composite_fitness, median_scores, normalize_weights
from .models import Candidate, JudgeScore
from .selection import SelectionResult, select_survivors

_EPS = 1e-9


class Status(StrEnum):
    SCORING = "scoring"
    READY_TO_SELECT = "ready_to_select"
    MUTATING = "mutating"
    COMPLETED = "completed"
    FAILED = "failed"


class Termination(StrEnum):
    THRESHOLD_MET = "threshold_met"
    GENERATION_LIMIT = "generation_limit"
    STAGNATION = "stagnation"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ProtocolError(RuntimeError):
    """An operation was called in the wrong status or broke a limit."""


@dataclass(frozen=True)
class EvolutionConfig:
    weights: Mapping[str, float]
    threshold: float = 0.75
    population_limit: int = 3
    generation_limit: int = 3
    survivor_count: int = 2
    # False runs every generation regardless of threshold (fixed-generation experiments).
    early_stop: bool = True
    stagnation_threshold: float = 0.02
    stagnation_window: int = 2
    # False turns stagnation detection off, so experiment runs do every planned generation.
    stagnation_recovery: bool = True
    tie_margin: float = 0.02
    dominance_margin: float = 0.02
    author_diversity: bool = True
    # Optional hard cap on panel-scored candidates; None means no cap.
    max_evaluations: int | None = None

    def __post_init__(self) -> None:
        normalize_weights(self.weights)
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        if not 2 <= self.population_limit <= 10:
            raise ValueError("population_limit must be in [2, 10]")
        if not 1 <= self.generation_limit <= 10:
            raise ValueError("generation_limit must be in [1, 10]")
        if not 1 <= self.survivor_count < self.population_limit:
            raise ValueError("survivor_count must be at least 1 and leave one new-candidate slot")
        if self.stagnation_window < 1:
            raise ValueError("stagnation_window must be at least 1")

    @property
    def new_candidate_slots(self) -> int:
        return self.population_limit - self.survivor_count

    @classmethod
    def for_roster(cls, n_active: int, weights: Mapping[str, float], **overrides) -> "EvolutionConfig":
        """Sizing from the live roster (engine spec 5.2).

        Each model writes s = ceil(4 / N) first answers, the population is P = N * s, and
        k = P - 2 survive, so every generation adds one mutation and one crossover.
        """
        population = n_active * seeds_per_model(n_active)
        sizing = {
            "population_limit": population,
            "survivor_count": population - 2,
            "generation_limit": 3,
            "tie_margin": 0.03,
            "dominance_margin": 0.03,
            "stagnation_threshold": 0.03,
        }
        return cls(weights=weights, **{**sizing, **overrides})


def seeds_per_model(n_active: int) -> int:
    """First answers each model writes in generation 0: ceil(4 / N)."""
    if n_active < 1:
        raise ValueError("n_active must be at least 1")
    return math.ceil(4 / n_active)


def _merge_critique(judge_scores: Sequence[JudgeScore]) -> list[str]:
    seen, merged = set(), []
    for score in judge_scores:
        for point in score.critique:
            if point not in seen:
                seen.add(point)
                merged.append(point)
    return merged


class EvolutionState:
    def __init__(
        self,
        config: EvolutionConfig,
        seeds: Sequence[Candidate] = (),
        prescored: Sequence[Candidate] = (),
    ) -> None:
        if not seeds and not prescored:
            raise ValueError("need at least one seed or pre-scored candidate")
        if len(seeds) + len(prescored) > config.population_limit:
            raise ValueError("initial candidates exceed population_limit")
        self.config = config
        self.generation = 0
        self.population: list[Candidate] = []
        self.pending: list[Candidate] = []
        self.archive: dict[str, Candidate] = {}
        self.best_history: list[float] = []
        self.evaluations = 0
        self.status = Status.SCORING
        self.termination: Termination | None = None
        # Set by select() when stagnation is detected; the engine answers it by
        # registering one "recovery" candidate this generation.
        self.recovery_due = False
        self._recovery_baseline: float | None = None

        for candidate in prescored:
            if not candidate.is_scored:
                raise ValueError(f"pre-scored candidate {candidate.id!r} has no fitness")
            self._add(candidate)
            self.population.append(candidate)
        for candidate in seeds:
            self._add(candidate)
            self.pending.append(candidate)
        if not self.pending:
            self._after_scoring()

    # --- queries ---

    @property
    def best(self) -> Candidate | None:
        scored = [c for c in self.population if c.is_scored]
        return max(scored, key=lambda c: c.fitness) if scored else None

    @property
    def new_candidate_slots(self) -> int:
        return self.config.population_limit - len(self.population) - len(self.pending)

    @property
    def is_done(self) -> bool:
        return self.status in {Status.COMPLETED, Status.FAILED}

    def state_block(self) -> str:
        best = self.best
        population = ", ".join(
            f"{c.id}: fitness={c.fitness:.3f}, author={c.author}" for c in self.population if c.is_scored
        )
        return "\n".join([
            "=== EVOLUTION STATE ===",
            f"Generation: {self.generation}/{self.config.generation_limit}",
            f"Status: {self.status}",
            f"Population: [{population}]",
            f"Pending: [{', '.join(c.id for c in self.pending)}]",
            f"Best: {best.id} fitness={best.fitness:.3f}" if best else "Best: none",
            f"Threshold: {self.config.threshold}",
            "========================",
        ])

    # --- transitions ---

    def register(self, candidate: Candidate) -> Candidate:
        """Add a mutation, crossover, or recovery candidate during the mutating phase."""
        self._require(Status.MUTATING)
        if self.new_candidate_slots <= 0:
            raise ProtocolError("population_limit reached; no new-candidate slots left this generation")
        missing = [p for p in candidate.parent_ids if p not in self.archive]
        if missing:
            raise ProtocolError(f"unknown parent ids: {missing}")
        candidate.generation = self.generation
        self._add(candidate)
        self.pending.append(candidate)
        if candidate.operator == "recovery":
            self.recovery_due = False
        return candidate

    def start_scoring(self) -> None:
        """Close registration for this generation."""
        self._require(Status.MUTATING)
        if self.pending:
            self.status = Status.SCORING
        else:
            self._after_scoring()

    def record_score(self, candidate_id: str, judge_scores: Sequence[JudgeScore]) -> Candidate:
        """Store the panel's raw scores; fitness comes from the per-dimension median."""
        if self.status == Status.MUTATING:
            self.start_scoring()
        self._require(Status.SCORING)
        candidate = next((c for c in self.pending if c.id == candidate_id), None)
        if candidate is None:
            raise ProtocolError(f"{candidate_id!r} is not pending")
        if not judge_scores:
            raise ValueError("need at least one judge score")
        cap = self.config.max_evaluations
        if cap is not None and self.evaluations >= cap:
            self.status, self.termination = Status.FAILED, Termination.BUDGET_EXHAUSTED
            raise ProtocolError(f"evaluation budget ({cap}) exhausted")

        dims = list(self.config.weights)
        candidate.judge_scores = list(judge_scores)
        candidate.scores = median_scores([s.scores for s in judge_scores], dims)
        candidate.fitness = composite_fitness(candidate.scores, self.config.weights)
        candidate.critique = _merge_critique(judge_scores)
        self.pending.remove(candidate)
        self.population.append(candidate)
        self.evaluations += 1
        if not self.pending:
            self._after_scoring()
        return candidate

    def select(self) -> SelectionResult | None:
        """Run one selection. Returns None when the run completes instead."""
        self._require(Status.READY_TO_SELECT)
        if self.generation >= self.config.generation_limit:
            self._complete(Termination.GENERATION_LIMIT)
            return None

        best_fitness = self.best.fitness
        if self._recovery_baseline is not None:
            improved = best_fitness > self._recovery_baseline + self.config.stagnation_threshold + _EPS
            self._recovery_baseline = None
            if not improved:
                self._complete(Termination.STAGNATION)
                return None
        elif self.config.stagnation_recovery and self._stagnated():
            self._recovery_baseline = best_fitness
            self.recovery_due = True

        result = select_survivors(
            self.population,
            self.config.survivor_count,
            dominance_margin=self.config.dominance_margin,
            tie_margin=self.config.tie_margin,
            author_diversity=self.config.author_diversity,
        )
        self.population = list(result.survivors)
        self.generation += 1
        self.status = Status.MUTATING
        return result

    # --- internals ---

    def _after_scoring(self) -> None:
        best = self.best
        self.best_history.append(best.fitness)
        if self.config.early_stop and best.fitness >= self.config.threshold - _EPS:
            self._complete(Termination.THRESHOLD_MET)
        else:
            self.status = Status.READY_TO_SELECT

    def _stagnated(self) -> bool:
        window, history = self.config.stagnation_window, self.best_history
        if len(history) <= window:
            return False
        return all(
            history[-i] - history[-i - 1] <= self.config.stagnation_threshold + _EPS
            for i in range(1, window + 1)
        )

    def _complete(self, reason: Termination) -> None:
        self.status, self.termination = Status.COMPLETED, reason

    def _add(self, candidate: Candidate) -> None:
        if candidate.id in self.archive:
            raise ProtocolError(f"duplicate candidate id {candidate.id!r}")
        self.archive[candidate.id] = candidate

    def _require(self, status: Status) -> None:
        if self.status != status:
            raise ProtocolError(f"expected status {status}, but it is {self.status}")
