import pytest

from helpers import scored
from reasonlineage.core import select_survivors


def ids(candidates):
    return [c.id for c in candidates]


def test_keeps_top_k_by_fitness():
    pop = [scored("a", 0.5), scored("b", 0.9, "x"), scored("c", 0.7, "y")]
    result = select_survivors(pop, 2)
    assert ids(result.survivors) == ["b", "c"]
    assert ids(result.eliminated) == ["a"]
    assert result.tie_break_swap is None


def test_mutation_worse_than_parent_is_excluded_not_ranked():
    parent = scored("seed-1", 0.70, "claude")
    child = scored("mut-gen-1-1", 0.60, "claude", "mutation", ("seed-1",))
    other = scored("seed-2", 0.50, "codex")
    result = select_survivors([parent, child, other], 2)
    assert ids(result.excluded) == ["mut-gen-1-1"]
    assert ids(result.survivors) == ["seed-1", "seed-2"]


def test_mutation_within_noise_of_parent_is_still_ranked():
    parent = scored("seed-1", 0.70, "claude")
    child = scored("mut-gen-1-1", 0.685, "claude", "mutation", ("seed-1",))
    result = select_survivors([parent, child], 1, author_diversity=False)
    assert result.excluded == []


def test_author_diversity_tie_break_matches_blueprint_example():
    # Blueprint figure 3: mut-gen-1-1 (claude 0.77), seed-1 (claude 0.71), seed-2 (codex 0.70)
    pop = [
        scored("seed-1", 0.71, "claude"),
        scored("seed-2", 0.70, "codex"),
        scored("mut-gen-1-1", 0.77, "claude", "mutation", ("seed-1",)),
    ]
    result = select_survivors(pop, 2)
    assert ids(result.survivors) == ["mut-gen-1-1", "seed-2"]
    assert result.tie_break_swap == ("seed-1", "seed-2")


def test_tie_break_does_not_override_a_real_gap():
    pop = [scored("m", 0.80, "claude"), scored("s1", 0.75, "claude"), scored("s2", 0.70, "codex")]
    result = select_survivors(pop, 2)
    assert ids(result.survivors) == ["m", "s1"]
    assert result.tie_break_swap is None


def test_tie_break_needs_a_new_author():
    pop = [scored("m", 0.80, "claude"), scored("s1", 0.71, "claude"), scored("s2", 0.70, "claude")]
    assert select_survivors(pop, 2).tie_break_swap is None


def test_rejects_unscored_population():
    pop = [scored("a", 0.5), scored("b", 0.6)]
    pop[1].fitness = None
    with pytest.raises(ValueError):
        select_survivors(pop, 1)
