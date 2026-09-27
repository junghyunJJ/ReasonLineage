import pytest

from reasonlineage.core import CATEGORY_PRESETS, composite_fitness, judge_spread, median_scores, normalize_weights


def test_normalize_weights_rescales_to_one():
    assert normalize_weights({"a": 2, "b": 2}) == {"a": 0.5, "b": 0.5}


@pytest.mark.parametrize("weights", [{}, {"a": -1, "b": 2}, {"a": 0, "b": 0}])
def test_normalize_weights_rejects_bad_input(weights):
    with pytest.raises(ValueError):
        normalize_weights(weights)


def test_composite_fitness_matches_skill_example():
    # SKILL.md Phase 2 arithmetic table: 0.28 + 0.18 + 0.24 = 0.70
    weights = {"dim1": 0.4, "dim2": 0.3, "dim3": 0.3}
    assert composite_fitness({"dim1": 0.7, "dim2": 0.6, "dim3": 0.8}, weights) == pytest.approx(0.70)


def test_composite_fitness_missing_dimension_counts_as_zero():
    assert composite_fitness({"a": 1.0}, {"a": 0.5, "b": 0.5}) == pytest.approx(0.5)


def test_composite_fitness_ignores_unconfigured_dimensions():
    assert composite_fitness({"a": 1.0, "extra": 0.0}, {"a": 1.0}) == pytest.approx(1.0)


def test_composite_fitness_rejects_out_of_range_score():
    with pytest.raises(ValueError):
        composite_fitness({"a": 1.2}, {"a": 1.0})


def test_median_scores_odd_and_even_panels():
    panel = [{"a": 0.6}, {"a": 0.9}, {"a": 0.7}]
    assert median_scores(panel, ["a"]) == {"a": 0.7}
    assert median_scores(panel[:2], ["a"]) == {"a": pytest.approx(0.75)}


def test_median_scores_uses_only_judges_that_scored_the_dimension():
    panel = [{"a": 0.6, "b": 0.2}, {"a": 0.8}]
    assert median_scores(panel, ["a", "b", "c"]) == {"a": pytest.approx(0.7), "b": 0.2, "c": 0.0}


def test_judge_spread():
    panel = [{"a": 0.85, "b": 0.5}, {"a": 0.70}, {"a": 0.65}]
    spread = judge_spread(panel, ["a", "b"])
    assert spread["a"] == pytest.approx(0.20)
    assert spread["b"] == 0.0


def test_category_weights_sum_to_one():
    for name, preset in CATEGORY_PRESETS.items():
        assert sum(preset.weights.values()) == pytest.approx(1.0), name
