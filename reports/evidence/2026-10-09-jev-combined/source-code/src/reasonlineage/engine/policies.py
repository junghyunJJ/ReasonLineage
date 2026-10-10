"""The decision points as swappable policies (spec 3.3). Stage 1 uses FixedPolicies only."""

from collections import Counter
from dataclasses import dataclass
from typing import Protocol, Sequence

from ..core.models import Candidate
from ..core.roles import pick_crossover_synthesizer, rank_synthesizers


@dataclass(frozen=True)
class CrossoverPlan:
    parents: tuple[Candidate, ...]
    synthesizer: str
    # True when every model wrote a parent, so a parent's author has to synthesize.
    fallback: bool


class Policies(Protocol):
    def mutation_parent(self, survivors: Sequence[Candidate]) -> Candidate: ...

    def crossover_plan(self, survivors: Sequence[Candidate], active: Sequence[str], history: Sequence[str]) -> CrossoverPlan: ...

    def recovery_author(self, survivors: Sequence[Candidate], active: Sequence[str]) -> str: ...


class FixedPolicies:
    """Stage-1 rules: mutate the top survivor, cross all survivors, rotate the synthesizer."""

    def mutation_parent(self, survivors: Sequence[Candidate]) -> Candidate:
        return max(survivors, key=lambda c: c.fitness)

    def crossover_plan(self, survivors: Sequence[Candidate], active: Sequence[str], history: Sequence[str]) -> CrossoverPlan:
        parents = tuple(survivors)
        authors = [c.author for c in parents]
        chosen = pick_crossover_synthesizer(authors, active, authors, history)
        if chosen is not None:
            return CrossoverPlan(parents, chosen, fallback=False)
        return CrossoverPlan(parents, rank_synthesizers(active, active, authors, history)[0], fallback=True)

    def recovery_author(self, survivors: Sequence[Candidate], active: Sequence[str]) -> str:
        counts = Counter(c.author for c in survivors)
        return min(active, key=lambda b: (counts[b], active.index(b)))
