"""The weather set build script (weather design 3, 7). No test calls NCEI."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_weather.py"
sys.path.insert(0, str(ROOT / "src"))

from reasonlineage.gold import weather as wx  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def write_pool(tmp_path: Path) -> Path:
    """A saved pool and the index that points at it, as `fetch` leaves them."""
    states = sorted(wx.REGION_OF)
    pool = {}
    for shift, key in enumerate(("7:tavg", "7:pcp", "8:tavg", "8:pcp")):
        order = states[shift:] + states[:shift]
        pool[key] = {state: round(0.5 * i + 0.1 * (i % 4), 1) for i, state in enumerate(order)}
    data = wx.pool_bytes(pool)
    full = tmp_path / "pool-full.json"
    full.write_bytes(data)
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"api": wx.API, "months": list(wx.MONTHS), "measures": list(wx.MEASURES),
                                 "full_pool": str(full), "sha256": hashlib.sha256(data).hexdigest(),
                                 "readings": pool}), encoding="utf-8")
    return index


def test_the_script_builds_a_set(tmp_path):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "medium", "--tasks", 2)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""
    assert sorted(p.name for p in (tmp_path / "tasks" / "weather-test").iterdir()) == \
        ["weather-test-01.json", "weather-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold" / "weather-test").iterdir()) == ["generation.json", "gold.json"]
    gold = json.loads((tmp_path / "gold" / "weather-test" / "gold.json").read_text(encoding="utf-8"))
    assert gold["source"]["pool_sha256"] == json.loads(index.read_text(encoding="utf-8"))["sha256"]


def test_another_sets_triples_can_be_left_out(tmp_path):
    index = write_pool(tmp_path)
    common = ["--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks"]
    assert run(*common, "build", "weather-calib", "--band", "easy", "--tasks", 2).returncode == 0
    result = run(*common, "build", "weather-main", "--band", "easy", "--tasks", 2, "--exclude-set", "weather-calib")
    assert result.returncode == 0, result.stderr
    first = wx.triples_of(tmp_path / "gold" / "weather-calib")
    assert all(triple not in first for triple in wx.triples_of(tmp_path / "gold" / "weather-main"))


def test_a_missing_pool_says_to_fetch_first(tmp_path):
    result = run("--index", tmp_path / "none.json", "--gold-root", tmp_path / "gold",
                 "--tasks-root", tmp_path / "tasks", "build", "weather-test", "--band", "easy", "--tasks", 2)
    assert result.returncode == 1 and "run `fetch` first" in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_changed_pool_file_says_to_fetch_again(tmp_path):
    index = write_pool(tmp_path)
    (tmp_path / "pool-full.json").write_bytes(b'{"7:tavg": {}}\n')
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "easy", "--tasks", 2)
    assert result.returncode == 1 and "run `fetch` again" in result.stderr


@pytest.mark.parametrize("args, message", [
    (("build", "weather-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("build", "Weather_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("build", "weather-test", "--band", "easy", "--tasks", 0), "must be at least 1"),
    (("build", "weather-test", "--tasks", 2), "the following arguments are required: --band"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks", *args)
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_band_that_runs_out_stops_the_build(tmp_path):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "easy", "--tasks", 400)
    assert result.returncode == 1 and "cannot build weather-test: " in result.stderr
    assert "ran out of triples" in result.stderr
    assert not (tmp_path / "gold" / "weather-test").exists()
