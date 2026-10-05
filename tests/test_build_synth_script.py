"""The synthetic set build script (gold synth design 3, 7)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_synth.py"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=env)


def test_the_script_builds_a_set(tmp_path):
    pytest.importorskip("scipy")
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""  # no fit warnings
    assert sorted(p.name for p in (tmp_path / "tasks").iterdir()) == ["synth-test-01.json", "synth-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold").iterdir()) == ["generation.json", "gold.json"]


@pytest.mark.parametrize("args, message", [
    (("synth-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("Synth_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("synth-test", "--band", "easy", "--tasks", 0), "--tasks must be at least 1"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    result = run(*args, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_without_scipy_the_script_says_how_to_install_it(tmp_path):
    fake = tmp_path / "fake" / "scipy"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("raise ImportError('No module named scipy')\n")
    env = os.environ | {"PYTHONPATH": str(tmp_path / "fake")}
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", env=env)
    assert result.returncode == 1 and "pip install -e '.[gold]'" in result.stderr


def test_a_stale_task_file_stops_the_build(tmp_path):
    pytest.importorskip("scipy")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "synth-test-09.json").write_text("{}")
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 1 and "cannot build synth-test: " in result.stderr and "synth-test-09.json" in result.stderr
