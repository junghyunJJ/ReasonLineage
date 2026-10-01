"""The synthetic hidden-law gold set (gold synth design 4): models, fits, bands, tasks and files."""

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
