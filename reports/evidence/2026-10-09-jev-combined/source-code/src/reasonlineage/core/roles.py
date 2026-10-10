"""Who judges, who synthesizes (SKILL.md v1.6.0, Role assignment)."""

from collections import Counter
from typing import Iterable, Sequence


def judges_for(author: str, active: Sequence[str]) -> list[str]:
    """Every active backend except the author (recusal panel, N-1 judges).

    With a single active backend nobody else exists, so it judges its own
    candidates. The engine must still run each of those calls in a fresh context.
    """
    if not active:
        raise ValueError("no active backends")
    others = [backend for backend in active if backend != author]
    return others or list(active)


def rank_synthesizers(
    options: Iterable[str],
    active: Sequence[str],
    survivor_authors: Sequence[str],
    history: Sequence[str] = (),
) -> list[str]:
    """Order models for the synthesizer role: fewest current survivors first, then the one that
    synthesized least recently (never is best), then roster order."""
    counts = Counter(survivor_authors)
    last_used = {backend: i for i, backend in enumerate(history)}
    return sorted(options, key=lambda b: (counts[b], last_used.get(b, -1), active.index(b)))


def pick_crossover_synthesizer(
    parent_authors: Iterable[str],
    active: Sequence[str],
    survivor_authors: Sequence[str],
    history: Sequence[str] = (),
) -> str | None:
    """A backend that authored none of the parents, preferring the one with the fewest survivors.

    Ties go to the model that synthesized least recently, then to roster order, so the role
    rotates and runs are reproducible. Returns None when every active backend authored a
    parent; the caller decides the fallback.
    """
    parents = set(parent_authors)
    options = [backend for backend in active if backend not in parents]
    if not options:
        return None
    return rank_synthesizers(options, active, survivor_authors, history)[0]


def crossover_has_distinct_voices(parent_authors: Iterable[str]) -> bool:
    """Multi-backend rule: combining texts from a single author adds no new voice."""
    return len(set(parent_authors)) >= 2
