"""The climate-departure gold set: the pool, the regions, the bands, and the files (weather design 8).

No test calls NCEI or a model. The replies are the shape of a real one, saved from Alabama's August 2026 reading.
"""

import pytest

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
