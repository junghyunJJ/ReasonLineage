"""The basket set build script (basket design 3, 7)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_basket.py"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=env)


def test_the_script_builds_a_set(tmp_path):
    result = run("basket-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""  # no fit warnings
    assert sorted(p.name for p in (tmp_path / "tasks").iterdir()) == ["basket-test-01.json", "basket-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold").iterdir()) == ["generation.json", "gold.json"]


@pytest.mark.parametrize("args, message", [
    (("basket-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("Synth_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("basket-test", "--band", "easy", "--tasks", 0), "--tasks must be at least 1"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    result = run(*args, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_stale_task_file_stops_the_build(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "basket-test-09.json").write_text("{}")
    result = run("basket-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 1 and "cannot build basket-test: " in result.stderr and "basket-test-09.json" in result.stderr
