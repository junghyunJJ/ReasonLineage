"""The climate-departure gold set: the pool, the regions, the bands, and the files (weather design 8).

No test calls NCEI or a model. The replies are the shape of a real one, saved from Alabama's August 2026 reading.
"""

import json

import pytest

from reasonlineage.engine.config import load_task
from reasonlineage.gold import weather as w

# ids 1-4 of NCEI's alphabetical statewide numbering, plus Alaska, which no climate region holds.
NAMES = {1: "Alabama", 2: "Arizona", 3: "Arkansas", 4: "California", 50: "Alaska"}
TAVG = {1: 2.4, 2: 6.1, 3: 4.1, 4: 5.3, 50: 1.2}
PCP = {1: 1.1, 2: -0.4, 3: 0.2, 4: 0.8, 50: 0.3}


def reply(state: str, month: int, measure: str, departure: float | None) -> dict:
    kind = "Average Temperature" if measure == "tavg" else "Precipitation"
    body = {"description": {"title": f"{state} {w.MONTH_NAMES[month]} {kind}",
                            "units": "Degrees Fahrenheit" if measure == "tavg" else "Inches",
                            "base_period": "1901-2000", "base_period_average": 79.3},
            "data": {f"2026{month:02d}": {"value": 81.7}}}
    if departure is not None:
        body["data"][f"2026{month:02d}"]["departure"] = departure
    return body


def fake_get(missing: tuple[int, ...] = ()) -> tuple:
    """A `get` over the four buckets, and the list of urls it was asked for."""
    asked: list[str] = []

    def get(url: str) -> dict:
        asked.append(url)
        state, measure, _, month_text = url.split("time-series/")[1].split("/")[:4]
        state_id, month = int(state), int(month_text)
        table = TAVG if measure == "tavg" else PCP
        value = None if state_id in missing else table[state_id] + (0.5 if month == 7 else 0.0)
        return reply(NAMES[state_id], month, measure, value)

    return get, asked


def pool(**buckets: dict[str, float]) -> dict[str, dict[str, float]]:
    """A pool with the same values in every bucket unless a bucket is given by name, e.g. pool(**{"7:tavg": {...}})."""
    base = {"Alabama": 2.4, "Arizona": 6.1, "Arkansas": 4.1, "California": 5.3}
    return {key: dict(buckets.get(key, base)) for key in ("7:tavg", "7:pcp", "8:tavg", "8:pcp")}


# --- 4.1 the pool ---

def test_reading_takes_the_state_name_from_the_reply():
    assert w.reading(reply("North Dakota", 8, "tavg", 1.7), 8) == ("North Dakota", 1.7)


def test_reading_skips_a_month_with_no_departure():
    assert w.reading(reply("Ohio", 7, "pcp", None), 7) is None


def test_the_state_ids_are_the_48_contiguous_states():
    """NCEI's numbering runs 1 (Alabama) to 48 (Wyoming); 49 is unused, and 50 (Alaska) and 51 (Hawaii)
    have a shorter base period than the 1901-2000 normal the question names."""
    ids = tuple(w.STATE_IDS)
    assert len(ids) == len(w.REGION_OF) == 48
    assert ids[0] == 1 and ids[-1] == 48
    assert 49 not in ids and 50 not in ids and 51 not in ids


def test_fetch_pool_keeps_the_contiguous_states_with_a_departure(tmp_path):
    get, asked = fake_get(missing=(3,))
    found = w.fetch_pool(tmp_path, get, state_ids=(1, 2, 3, 4, 50))
    assert sorted(found) == ["7:pcp", "7:tavg", "8:pcp", "8:tavg"]
    assert found["8:tavg"] == {"Alabama": 2.4, "Arizona": 6.1, "California": 5.3}  # no Arkansas, no Alaska
    assert found["7:tavg"]["Alabama"] == pytest.approx(2.9)  # July's own reading, not August's
    assert len(asked) == 20


def test_fetch_pool_reads_the_cache_instead_of_asking_again(tmp_path):
    get, asked = fake_get()
    w.fetch_pool(tmp_path, get, state_ids=(1, 2))
    again, asked_again = fake_get()
    found = w.fetch_pool(tmp_path, again, state_ids=(1, 2))
    assert asked_again == []
    assert found["8:tavg"] == {"Alabama": 2.4, "Arizona": 6.1}
    assert len(asked) == 8


def test_get_tries_again_after_a_failure(monkeypatch):
    calls = []

    def flaky(url, timeout=None):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("connection reset")
        raise _Done()

    class _Done(Exception):
        pass

    monkeypatch.setattr(w.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(w.time, "sleep", lambda seconds: None)
    with pytest.raises(_Done):
        w._get("https://example.invalid/x")
    assert len(calls) == 3


def test_fetch_pool_says_which_reading_it_could_not_get(tmp_path):
    def get(url):
        raise OSError("503")

    with pytest.raises(w.SourceError) as exc:
        w.fetch_pool(tmp_path, get, state_ids=(1,))
    assert "/1/tavg/1/7/" in str(exc.value)


def test_load_pool_refuses_a_file_that_changed(tmp_path):
    path = tmp_path / "pool.json"
    path.write_bytes(w.pool_bytes(pool()))
    with pytest.raises(w.SourceError) as exc:
        w.load_pool(path, "0" * 64)
    assert "fetch" in str(exc.value)


# --- 4.2 the regions ---

def test_the_regions_hold_the_48_contiguous_states_once_each():
    named = [state for states in w.REGIONS.values() for state in states]
    assert len(named) == 48
    assert len(set(named)) == 48
    assert "Alaska" not in named and "Hawaii" not in named
    assert w.REGION_OF["Wyoming"] == "Northern Rockies and Plains"


# --- 4.3 the triples ---

def test_usable_refuses_two_states_from_one_region():
    values = {"Oregon": 4.0, "Washington": 1.0, "Idaho": 0.5}  # all Northwest
    assert not w.usable(("Oregon", "Washington", "Idaho"), values, w.BANDS["tavg"]["easy"])


def test_usable_refuses_a_tie():
    values = {"Oregon": 4.0, "Texas": 4.0, "Maine": 1.0}
    assert not w.usable(("Oregon", "Texas", "Maine"), values, w.BANDS["tavg"]["easy"])
    assert not w.usable(("Oregon", "Texas", "Maine"), values, w.BANDS["tavg"]["medium"])


@pytest.mark.parametrize("measure, gap, band", [
    ("tavg", 2.0, "easy"), ("tavg", 1.9, "medium"), ("tavg", 1.0, "medium"),
    ("tavg", 0.9, "hard"), ("tavg", 0.4, "hard"), ("tavg", 0.3, None),
    ("pcp", 1.5, "easy"), ("pcp", 1.4, "medium"), ("pcp", 0.7, "medium"),
    ("pcp", 0.6, "hard"), ("pcp", 0.3, "hard"), ("pcp", 0.2, None),
])
def test_a_gap_falls_in_one_band_only(measure, gap, band):
    values = {"Oregon": 5.0 + gap, "Texas": 5.0, "Maine": 0.0}
    triple = ("Oregon", "Texas", "Maine")
    assert w.margin(triple, values) == gap
    held = [name for name in w.BAND_NAMES if w.usable(triple, values, w.BANDS[measure][name])]
    assert held == ([band] if band else [])


def test_choose_alternates_the_measure_and_the_month():
    chosen = w.choose("weather-v1", _wide_pool(), "hard", 8)
    assert [(c["measure"], c["month"]) for c in chosen] == [
        ("tavg", 7), ("pcp", 7), ("tavg", 8), ("pcp", 8)] * 2


def test_choose_keeps_every_state_under_the_reuse_cap():
    chosen = w.choose("weather-v1", _wide_pool(), "medium", 20)
    counts: dict[str, int] = {}
    for task in chosen:
        for state in task["states"]:
            counts[state] = counts.get(state, 0) + 1
    assert counts and max(counts.values()) <= w.MAX_PER_STATE


def test_choose_leaves_out_the_triples_it_is_given():
    first = w.choose("weather-v1", _wide_pool(), "easy", 4)
    used = [sorted(task["states"]) for task in first]
    again = w.choose("weather-v1", _wide_pool(), "easy", 4, exclude=used)
    assert all(sorted(task["states"]) not in used for task in again)


def test_choose_says_how_far_it_got_when_a_band_runs_out():
    with pytest.raises(w.SourceError) as exc:
        w.choose("weather-v1", pool(), "easy", 4)
    assert "only 1 of 4" in str(exc.value) and "easy" in str(exc.value)


def test_choose_reports_a_pool_without_the_bucket():
    thin = {key: values for key, values in _wide_pool().items() if key != "8:pcp"}
    with pytest.raises(w.SourceError) as exc:
        w.choose("weather-v1", thin, "easy", 4)
    assert "8:pcp" in str(exc.value)


# --- 4.4 the task and the files ---

def test_the_question_states_the_normal_and_asks_for_the_departure():
    made = w.make_task("weather-v1", 0, _one())
    text = made["task"]["question"]
    assert "1901-2000" in text and "furthest above" in text
    assert "July 2026" in text
    assert sorted(made["task"]["candidates"]) == ["California", "Maine", "Texas"]


def test_the_question_leaks_no_departure_figure():
    made = w.make_task("weather-v1", 0, _one())
    text = made["task"]["question"]
    for value in _one()["departures"].values():
        assert str(value) not in text
    assert "normal" in text and "Northwest" not in text  # the regions stay out of the task


def test_the_gold_names_the_largest_departure():
    made = w.make_task("weather-v1", 0, _one())
    assert made["gold"] == {"approved": ["California"], "failed": ["Maine", "Texas"]}
    assert made["record"]["margin"] == 2.0
    assert made["record"]["regions"]["Maine"] == "Northeast"


def test_build_writes_the_tasks_the_gold_and_the_record(tmp_path):
    written = w.build("weather-v1", "easy", 4, _wide_pool(), {"api": w.API, "pool_sha256": "abc"},
                      tmp_path / "tasks", tmp_path / "gold")
    assert [path.name for path in written] == [f"weather-v1-0{i}.json" for i in range(1, 5)]
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text(encoding="utf-8"))
    record = json.loads((tmp_path / "gold" / "generation.json").read_text(encoding="utf-8"))
    assert gold["source"] == {"api": w.API, "pool_sha256": "abc", "set": "weather-v1", "band": "easy"}
    assert sorted(gold["tasks"]) == sorted(record["tasks"]) == [f"weather-v1-0{i}" for i in range(1, 5)]
    for task_id, truth in gold["tasks"].items():
        assert len(truth["approved"]) == 1 and len(truth["failed"]) == 2
        assert truth["approved"][0] == record["tasks"][task_id]["winner"]


def test_a_built_task_loads_in_the_engine_with_the_gold_candidates(tmp_path):
    w.build("weather-v1", "medium", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text(encoding="utf-8"))
    for path in sorted((tmp_path / "tasks").glob("*.json")):
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}  # what score_run checks
        assert task.category == "analytical"


def test_the_same_set_name_builds_the_same_files_and_another_name_does_not(tmp_path):
    w.build("weather-v1", "hard", 4, _wide_pool(), {}, tmp_path / "a", tmp_path / "ga")
    w.build("weather-v1", "hard", 4, _wide_pool(), {}, tmp_path / "b", tmp_path / "gb")
    w.build("weather-v2", "hard", 4, _wide_pool(), {}, tmp_path / "c", tmp_path / "gc")
    first = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "a").glob("*.json"))]
    same = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "b").glob("*.json"))]
    other = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "c").glob("*.json"))]
    assert first == same
    assert first != other


def test_build_stops_when_the_task_folder_holds_a_file_it_does_not_build(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "weather-v1-09.json").write_text("{}", encoding="utf-8")
    with pytest.raises(w.SourceError) as exc:
        w.build("weather-v1", "easy", 4, _wide_pool(), {}, tasks, tmp_path / "gold")
    assert "weather-v1-09.json" in str(exc.value)
    assert not (tmp_path / "gold").exists()


def test_build_refuses_an_unknown_band(tmp_path):
    with pytest.raises(w.SourceError) as exc:
        w.build("weather-v1", "medium-hard", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    assert "easy, medium, hard" in str(exc.value)


def test_triples_of_reads_back_what_a_set_used(tmp_path):
    w.build("weather-v1", "easy", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    used = w.triples_of(tmp_path / "gold")
    assert len(used) == 2 and all(len(triple) == 3 for triple in used)
    assert w.triples_of(tmp_path / "nothing") == []


# --- fixtures ---

def _wide_pool() -> dict[str, dict[str, float]]:
    """All 48 states, with 0.1-precision departures whose gaps land in every band, shifted per bucket."""
    states = sorted(w.REGION_OF)
    built = {}
    for shift, key in enumerate(("7:tavg", "7:pcp", "8:tavg", "8:pcp")):
        order = states[shift:] + states[:shift]
        built[key] = {state: round(0.5 * i + 0.1 * (i % 4), 1) for i, state in enumerate(order)}
    return built


def _one() -> dict:
    return {"month": 7, "measure": "tavg", "states": ["California", "Texas", "Maine"],
            "departures": {"California": 5.3, "Texas": 3.3, "Maine": 1.1},
            "regions": {"California": "West", "Texas": "South", "Maine": "Northeast"}, "margin": 2.0}
