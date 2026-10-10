"""Author x judge calibration analysis.

Model for a candidate c (written by author a) scored by judge j:

    fitness = quality[c] + leniency[j] + self_pref[j] * (j == a)
              + family_pref[j] * (j != a, same family) + noise

quality and leniency are fitted only on cross-family cells, where neither
preference can act. Self- and family preference are then the mean residuals
on the cells the fit left out, so they are not absorbed into leniency.
"""

import statistics
from collections import defaultdict
from typing import Callable, Mapping, Sequence

Cell = tuple[str, str]  # (candidate id, judge name)


def cell_means(records: Sequence[Mapping]) -> dict[Cell, float]:
    grouped = defaultdict(list)
    for r in records:
        grouped[r["candidate"], r["judge"]].append(r["fitness"])
    return {cell: statistics.mean(values) for cell, values in grouped.items()}


def within_judge_noise(records: Sequence[Mapping]) -> dict[str, float]:
    """Pooled SD of repeated scores of the same candidate, per judge."""
    grouped = defaultdict(list)
    for r in records:
        grouped[r["candidate"], r["judge"]].append(r["fitness"])
    variances = defaultdict(list)
    for (_, judge), values in grouped.items():
        if len(values) > 1:
            variances[judge].append(statistics.variance(values))
    return {judge: statistics.mean(v) ** 0.5 for judge, v in variances.items()}


def fit_additive(cells: Mapping[Cell, float], use: Callable[[str, str], bool], iterations: int = 500):
    """Least-squares quality[c] + leniency[j] on the selected cells; leniency centered to mean 0."""
    selected = {cell: y for cell, y in cells.items() if use(*cell)}
    candidates = sorted({c for c, _ in selected})
    judges = sorted({j for _, j in selected})
    leniency = {j: 0.0 for j in judges}
    quality = {}
    for _ in range(iterations):
        quality = {c: statistics.mean(y - leniency[j] for (cc, j), y in selected.items() if cc == c) for c in candidates}
        leniency = {j: statistics.mean(y - quality[c] for (c, jj), y in selected.items() if jj == j) for j in judges}
        shift = statistics.mean(leniency.values())
        leniency = {j: v - shift for j, v in leniency.items()}
    quality = {c: statistics.mean(y - leniency[j] for (cc, j), y in selected.items() if cc == c) for c in candidates}
    return quality, leniency


def zscore_by_judge(cells: Mapping[Cell, float]) -> tuple[dict[Cell, float], float]:
    """Standardize each judge's scores across candidates; also return the mean judge SD to map back."""
    by_judge = defaultdict(list)
    for (_, j), y in cells.items():
        by_judge[j].append(y)
    stats = {j: (statistics.mean(v), statistics.stdev(v)) for j, v in by_judge.items()}
    z = {(c, j): (y - stats[j][0]) / stats[j][1] for (c, j), y in cells.items()}
    return z, statistics.mean(sd for _, sd in stats.values())


def preference_analysis(
    cells: Mapping[Cell, float],
    author: Mapping[str, str],
    family: Mapping[str, str],
) -> dict:
    """`author` maps candidate -> roster name; `family` maps roster name -> vendor family."""

    def relation(c: str, j: str) -> str:
        if author[c] == j:
            return "self"
        return "family" if family[author[c]] == family[j] else "foreign"

    quality, leniency = fit_additive(cells, lambda c, j: relation(c, j) == "foreign")
    residual = {cell: y - quality[cell[0]] - leniency[cell[1]] for cell, y in cells.items()}
    foreign = [r for (c, j), r in residual.items() if relation(c, j) == "foreign"]
    dof = max(len(foreign) - len(quality) - len(leniency) + 1, 1)

    def mean_residual(j: str, kind: str) -> float | None:
        values = [r for (c, jj), r in residual.items() if jj == j and relation(c, jj) == kind]
        return statistics.mean(values) if values else None

    judges = sorted(leniency)
    return {
        "quality": quality,
        "leniency": leniency,
        "self_preference": {j: mean_residual(j, "self") for j in judges},
        "family_preference": {j: mean_residual(j, "family") for j in judges},
        "foreign_residual_sd": (sum(r * r for r in foreign) / dof) ** 0.5,
    }


def discrimination(cells: Mapping[Cell, float], pairs: Sequence[tuple[str, str]]) -> dict[str, dict]:
    """Per judge: mean (strong - weak) gap and the share of pairs ordered correctly."""
    judges = sorted({j for _, j in cells})
    out = {}
    for j in judges:
        gaps = [cells[strong, j] - cells[weak, j] for strong, weak in pairs if (strong, j) in cells and (weak, j) in cells]
        out[j] = {"mean_gap": statistics.mean(gaps), "correct_order": sum(g > 0 for g in gaps) / len(gaps)}
    return out
