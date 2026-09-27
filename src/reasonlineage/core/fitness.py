"""Fitness arithmetic: weight normalization, weighted sum, panel median, judge spread."""

from statistics import median
from typing import Iterable, Mapping, Sequence


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return {dim: w / total for dim, w in weights.items()}


def _check_score(dim: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"score for {dim!r} must be in [0, 1], got {value}")


def composite_fitness(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Weighted sum over the configured dimensions. A dimension with no score counts as 0.0."""
    total = 0.0
    for dim, weight in normalize_weights(weights).items():
        value = scores.get(dim, 0.0)
        _check_score(dim, value)
        total += value * weight
    return total


def median_scores(judge_scores: Sequence[Mapping[str, float]], dimensions: Iterable[str]) -> dict[str, float]:
    """Per-dimension median across the judges that scored it. A dimension no judge scored is 0.0."""
    result = {}
    for dim in dimensions:
        values = [scores[dim] for scores in judge_scores if dim in scores]
        for value in values:
            _check_score(dim, value)
        result[dim] = float(median(values)) if values else 0.0
    return result


def judge_spread(judge_scores: Sequence[Mapping[str, float]], dimensions: Iterable[str]) -> dict[str, float]:
    """max - min of the raw judge scores per dimension; 0.0 when fewer than two judges scored it."""
    result = {}
    for dim in dimensions:
        values = [scores[dim] for scores in judge_scores if dim in scores]
        result[dim] = max(values) - min(values) if len(values) >= 2 else 0.0
    return result
