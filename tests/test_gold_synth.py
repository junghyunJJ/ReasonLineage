"""The synthetic hidden-law gold set (gold synth design 4): models, fits, bands, tasks and files."""

from collections import Counter

import numpy as np
import pytest

pytest.importorskip("scipy")  # the gold extra; the base suite runs without it (design 8)

from reasonlineage.gold import synth  # noqa: E402


def test_each_family_has_three_models_with_their_own_names():
    names = [m.name for f in synth.FAMILIES for m in f.models]
    assert [f.key for f in synth.FAMILIES] == ["dose", "enzyme", "growth", "elimination"]
    assert all(len(f.models) == 3 for f in synth.FAMILIES) and len(set(names)) == 12


@pytest.mark.parametrize("f, args, expected", [
    (synth.hyperbolic, (1.0, 80, 1.0), 40.0),
    (synth.sigmoid, (2.0, 80, 1.0), 64.0),
    (synth.loglinear, (np.e, 10, 1.0), 10.0),
    (synth.competitive, ((20.0, 10.0), 20, 10, 10), 10.0),
    (synth.noncompetitive, ((20.0, 10.0), 20, 10, 10), 400 / 60),
    (synth.uncompetitive, ((20.0, 10.0), 20, 10, 10), 8.0),
    (synth.logistic, (np.log(9) / 0.3, 0.1, 0.3, 1.0), 0.5),
    (synth.gompertz, (0.0, 0.1, 0.3, 1.0), 0.1),
    (synth.monomolecular, (np.log(2) / 0.2, 0.0001, 0.2, 1.0), 0.50005),
    (synth.first_order, (np.log(2) / 0.5, 10, 0.5), 5.0),
    (synth.zero_order, (30.0, 10, 0.5), 0.0),
    (synth.second_order, (0.5, 10, 0.2), 5.0),
])
def test_each_model_gives_its_textbook_value(f, args, expected):
    x, *params = args
    assert float(f(np.asarray(x, dtype=float), *params)) == pytest.approx(expected)


@pytest.mark.parametrize("family", synth.FAMILIES, ids=lambda f: f.key)
@pytest.mark.parametrize("truth", [0, 1, 2])
def test_a_fit_to_clean_data_finds_the_true_model(family, truth):
    params = family.sample(np.random.default_rng(1), truth)
    y = family.models[truth].f(family.x, *params)
    fits = synth.posteriors(family, y, sigma=0.01 * float(np.max(y)))
    assert fits[truth]["rss"] == pytest.approx(0, abs=1e-6)
    assert fits[truth]["params"] == pytest.approx(list(params), rel=1e-2)
    assert fits[truth]["posterior"] > 0.999


def test_data_that_do_not_tell_the_models_apart_are_not_kept():
    # Without inhibition the three inhibition types are the same curve, so no posterior reaches 0.9.
    s, i = synth.ENZYME.x
    y = 30 * s / (10 + s)
    fits = synth.posteriors(synth.ENZYME, y, sigma=0.5)
    assert all(f["posterior"] < 0.9 for f in fits)
    assert synth.band_of(max(f["posterior"] for f in fits)) is None


@pytest.mark.parametrize("posterior, band", [
    (1.0, "easy"), (0.999, "easy"), (0.9989, "medium"), (0.97, "medium"),
    (0.9699, "hard"), (0.9, "hard"), (0.8999, None), (0.5, None),
])
def test_bands_split_the_true_models_posterior(posterior, band):
    assert synth.band_of(posterior) == band


def test_shown_values_have_three_significant_digits():
    assert synth.round3(np.array([123.456, 0.0012345, -9.8765])).tolist() == [123.0, 0.00123, -9.88]


def test_tasks_rotate_families_and_true_models():
    picks = [synth.assignment(i) for i in range(10)]
    assert Counter(f.key for f, _ in picks) == {"dose": 3, "enzyme": 3, "growth": 2, "elimination": 2}
    assert [t for f, t in picks if f.key == "dose"] == [0, 1, 2]
    assert [t for f, t in picks if f.key == "growth"] == [0, 1]


def test_a_task_shows_the_data_and_candidates_and_its_truth_is_in_the_band():
    made = synth.make_task("synth-test", 0, "easy")
    task, gold, record = made["task"], made["gold"], made["record"]
    names = [m.name for m in synth.DOSE.models]
    assert task["id"] == "synth-test-01" and sorted(task["candidates"]) == sorted(names)
    assert (task["category"], task["data_sensitivity"]) == ("analytical", "public")
    assert gold == {"approved": ["Hyperbolic Emax model"], "failed": sorted(names[1:])}
    assert record["family"] == "dose" and record["truth"] == "Hyperbolic Emax model"
    posterior = {f["model"]: f["posterior"] for f in record["fits"]}
    assert synth.band_of(posterior["Hyperbolic Emax model"]) == "easy"
    question = task["question"]
    assert f"Measurement error is Gaussian with SD {record['sigma']:.3g} %." in question
    assert "| concentration (µM) | effect (% of maximum) |" in question
    lines = [line for line in question.splitlines() if line.startswith("- ")]
    assert lines == [f"- {name}: {next(m.formula for m in synth.DOSE.models if m.name == name)}" for name in task["candidates"]]
    values = [float(row.split("|")[2]) for row in question.splitlines() if row.startswith("| ") and "µM" not in row and "---" not in row]
    assert len(values) == 10 and min(values) >= 0


def test_the_same_set_gives_the_same_task_and_another_set_other_data():
    first, again = synth.make_task("synth-test", 1, "easy"), synth.make_task("synth-test", 1, "easy")
    assert first == again
    assert synth.make_task("synth-other", 1, "easy")["task"]["question"] != first["task"]["question"]


def test_a_band_that_cannot_be_filled_stops_with_the_count(monkeypatch):
    monkeypatch.setattr(synth, "MAX_TRIES", 3)
    monkeypatch.setattr(synth, "draw", lambda *args: None)
    with pytest.raises(synth.SynthError, match="synth-test-01: no dose data .* band 'hard' after 3 draws"):
        synth.make_task("synth-test", 0, "hard")
