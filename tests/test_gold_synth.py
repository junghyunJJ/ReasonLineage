"""The synthetic hidden-law gold set (gold synth design 4): models, fits, bands, tasks and files."""

import json
from collections import Counter

import numpy as np
import pytest

pytest.importorskip("scipy")  # the gold extra; the base suite runs without it (design 8)

from reasonlineage.diagnose.gold import correctness  # noqa: E402
from reasonlineage.engine.config import load_task  # noqa: E402
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
    assert len(values) == 10


def test_the_same_set_gives_the_same_task_and_another_set_other_data():
    first, again = synth.make_task("synth-test", 1, "easy"), synth.make_task("synth-test", 1, "easy")
    assert first == again
    assert synth.make_task("synth-other", 1, "easy")["task"]["question"] != first["task"]["question"]


def test_a_band_that_cannot_be_filled_stops_with_the_count(monkeypatch):
    monkeypatch.setattr(synth, "MAX_TRIES", 3)
    monkeypatch.setattr(synth, "draw", lambda *args: None)
    with pytest.raises(synth.SynthError, match="synth-test-01: no dose data .* band 'hard' after 3 draws"):
        synth.make_task("synth-test", 0, "hard")


def test_build_writes_loadable_tasks_the_gold_file_and_the_generation_record(tmp_path):
    paths = synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    assert [p.name for p in paths] == ["synth-test-01.json", "synth-test-02.json"]
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text())
    record = json.loads((tmp_path / "gold" / "generation.json").read_text())
    assert gold["source"] == record["source"] == {"generator": "reasonlineage.gold.synth", "set": "synth-test", "band": "easy"}
    for path in paths:
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}  # what score_run checks
        assert correctness([*truth["approved"], *truth["failed"]], truth) == 1.0
        assert record["tasks"][task.id]["truth"] == truth["approved"][0]
    assert record["tasks"]["synth-test-02"]["family"] == "enzyme"


def test_build_refuses_files_it_does_not_make_and_writes_nothing(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "synth-test-03.json").write_text("{}")
    with pytest.raises(synth.SynthError, match="synth-test-03.json is not built by this set"):
        synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    assert not (tmp_path / "gold").exists()


def test_build_refuses_an_unknown_band(tmp_path):
    with pytest.raises(synth.SynthError, match="unknown band 'medium-hard'"):
        synth.build("synth-test", "medium-hard", 2, tmp_path / "tasks", tmp_path / "gold")


def test_building_the_same_set_again_gives_the_same_bytes(tmp_path):
    synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    before = {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]}
    synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    after = {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]}
    assert after == before


def test_the_symbols_in_a_question_survive_the_task_file(tmp_path):
    (path, _) = synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    question = load_task(path).question
    assert "µM" in question and "C²/(EC50² + C²)" in question and "Emax·C" in question


class Rigged:
    """An rng that takes the middle of every range and pushes only the first reading 3 SD down."""

    def uniform(self, low, high):
        return (low + high) / 2

    def normal(self, loc, scale, size):
        noise = np.zeros(size)
        noise[0] = -3 * scale
        return noise


def test_a_reading_below_zero_is_kept_because_the_error_is_gaussian():
    # Dropping such draws would make the error near zero half-normal, not the Gaussian the question states.
    drawn = [synth.draw(synth.DOSE, 1, band, Rigged()) for band in synth.BANDS]
    kept = [d for d in drawn if d is not None]
    assert len(kept) == 1 and kept[0]["y"][0] < 0


@pytest.mark.parametrize("family", synth.FAMILIES, ids=lambda f: f.key)
def test_the_fit_uses_the_x_values_the_table_shows(family):
    # The gold is computed on what the models read (design 4.2), so x holds no more digits than the table shows.
    assert np.array_equal(family.x, synth.round3(family.x))


@pytest.mark.parametrize("index, names", [(8, {"m", "C0"}), (7, {"C0", "k0"}), (0, {"Emax", "EC50"})])
def test_the_record_names_the_true_models_own_parameters(index, names):
    # Task 9 is dose with the log-linear truth, task 8 elimination with the zero-order truth.
    assert set(synth.make_task("synth-test", index, "easy")["record"]["params"]) == names
