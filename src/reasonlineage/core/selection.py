"""Survivor selection (SKILL.md v1.6.0, Step 3.3)."""

from dataclasses import dataclass
from typing import Sequence

from .models import Candidate

_EPS = 1e-9


@dataclass(frozen=True)
class SelectionResult:
    survivors: list[Candidate]
    eliminated: list[Candidate]
    # Mutations that scored below their own parent by more than the dominance
    # margin. Kept in the trace, never ranked.
    excluded: list[Candidate]
    # (dropped_id, kept_id) when the author-diversity tie-break fired.
    tie_break_swap: tuple[str, str] | None


def select_survivors(
    population: Sequence[Candidate],
    survivor_count: int,
    *,
    dominance_margin: float = 0.02,
    tie_margin: float = 0.02,
    author_diversity: bool = True,
) -> SelectionResult:
    if survivor_count < 1:
        raise ValueError("survivor_count must be at least 1")
    unscored = [c.id for c in population if not c.is_scored]
    if unscored:
        raise ValueError(f"cannot select with unscored candidates: {unscored}")

    by_id = {c.id: c for c in population}
    excluded_ids = {
        c.id
        for c in population
        if c.operator == "mutation"
        and c.parent_ids[0] in by_id
        and c.fitness < by_id[c.parent_ids[0]].fitness - dominance_margin - _EPS
    }
    excluded = [c for c in population if c.id in excluded_ids]
    # sorted() is stable, so equal fitness keeps population order.
    ranked = sorted((c for c in population if c.id not in excluded_ids), key=lambda c: -c.fitness)
    survivors, rest = ranked[:survivor_count], ranked[survivor_count:]

    swap = None
    if author_diversity and survivors and rest:
        last, challenger = survivors[-1], rest[0]
        kept_authors = {c.author for c in survivors[:-1]}
        if (
            last.fitness - challenger.fitness <= tie_margin + _EPS
            and last.author in kept_authors
            and challenger.author not in kept_authors
        ):
            survivors[-1], rest[0] = challenger, last
            swap = (last.id, challenger.id)

    return SelectionResult(survivors, rest, excluded, swap)
