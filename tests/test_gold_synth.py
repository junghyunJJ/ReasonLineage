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
