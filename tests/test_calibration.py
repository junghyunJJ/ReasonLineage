import pytest

from reasonlineage.backends.roster import parse_entry
from reasonlineage.calibration import (
    cell_means,
    discrimination,
    preference_analysis,
    within_judge_noise,
    zscore_by_judge,
)

FAMILY = {"opus": "anthropic", "sonnet": "anthropic", "gpt": "openai", "grok": "xai"}
JUDGES = list(FAMILY)
QUALITY = {"strong": 0.7, "weak": 0.3}
LENIENCY = {"opus": -0.06, "sonnet": 0.0, "gpt": 0.02, "grok": 0.04}
SELF = {"opus": 0.08, "sonnet": 0.0, "gpt": 0.05, "grok": 0.0}
FAMILY_PREF = {"opus": 0.03, "sonnet": 0.03}


def synthetic_cells(author_quality_shift=None):
    shift = author_quality_shift or {a: 0.0 for a in JUDGES}
    cells, author = {}, {}
    for a in JUDGES:
        for level, q in QUALITY.items():
            c = f"{a}-{level}"
            author[c] = a
            for j in JUDGES:
                y = q + shift[a] + LENIENCY[j]
                if j == a:
                    y += SELF[j]
                elif FAMILY[j] == FAMILY[a]:
                    y += FAMILY_PREF.get(j, 0.0)
                cells[c, j] = y
    return cells, author


def test_recovers_leniency_self_and_family_preference():
    cells, author = synthetic_cells({"opus": 0.05, "sonnet": -0.02, "gpt": 0.0, "grok": 0.03})
    result = preference_analysis(cells, author, FAMILY)
    for j in JUDGES:
        assert result["leniency"][j] == pytest.approx(LENIENCY[j] - sum(LENIENCY.values()) / 4, abs=1e-6)
        assert result["self_preference"][j] == pytest.approx(SELF[j], abs=1e-6)
    assert result["family_preference"]["opus"] == pytest.approx(0.03, abs=1e-6)
    assert result["family_preference"]["gpt"] is None  # no same-family candidates for gpt
    assert result["foreign_residual_sd"] == pytest.approx(0.0, abs=1e-6)


def test_self_preference_is_not_absorbed_into_leniency():
    # If self cells were used in the fit, opus's +0.08 would partly look like leniency.
    cells, author = synthetic_cells()
    result = preference_analysis(cells, author, FAMILY)
    assert result["leniency"]["opus"] == pytest.approx(-0.06 - 0.0, abs=1e-6)


def test_discrimination_and_noise():
    cells, _ = synthetic_cells()
    pairs = [(f"{a}-strong", f"{a}-weak") for a in JUDGES]
    d = discrimination(cells, pairs)
    assert d["gpt"]["correct_order"] == 1.0
    assert d["gpt"]["mean_gap"] == pytest.approx(0.4)
    records = [
        {"candidate": "c1", "judge": "opus", "fitness": 0.5},
        {"candidate": "c1", "judge": "opus", "fitness": 0.7},
        {"candidate": "c2", "judge": "opus", "fitness": 0.4},
        {"candidate": "c2", "judge": "opus", "fitness": 0.4},
    ]
    assert cell_means(records)["c1", "opus"] == pytest.approx(0.6)
    assert within_judge_noise(records)["opus"] == pytest.approx((0.02 / 2) ** 0.5)


def test_zscore_by_judge_standardizes_each_row():
    cells, _ = synthetic_cells()
    z, scale = zscore_by_judge(cells)
    opus = [v for (c, j), v in z.items() if j == "opus"]
    assert sum(opus) == pytest.approx(0.0, abs=1e-9)
    assert scale > 0


def test_parse_roster_entry():
    entry = parse_entry("gpt=codex:gpt-6-sol:xhigh")
    assert (entry.name, entry.backend, entry.model, entry.effort, entry.family) == ("gpt", "codex", "gpt-6-sol", "xhigh", "openai")
    assert parse_entry("opus=claude:claude-opus-5-5").effort is None
    for bad in ["gpt", "gpt=unknown:m", "gpt=codex:", "gpt=codex:m:x:y"]:
        with pytest.raises(ValueError):
            parse_entry(bad)
