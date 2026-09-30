"""Resume after a crash, replay another run, and share generation 0 across conditions (spec 6.3, 6.5)."""

import asyncio
import json
import shutil
from collections import Counter

import pytest

from fakes import Clock, Crash, FakeModel, decisions, events_of, make_runner
from reasonlineage.engine.calls import ReplaySource, call_file, gen0_writing
from reasonlineage.engine.errors import ResumeMismatch
from reasonlineage.protocol import ROOT, load_protocol

NAMES = ("opus", "gpt", "grok", "qwen")


def test_resume_after_a_crash_reproduces_the_uninterrupted_run(tmp_path):
    whole, _ = make_runner(tmp_path, run_name="whole")
    expected = asyncio.run(whole.run())

    crashing, _ = make_runner(tmp_path, run_name="cut", clock=Clock(crash_at=25))
    with pytest.raises(Crash):
        asyncio.run(crashing.run())
    resumed, _ = make_runner(tmp_path, run_name="cut", resume=True)
    summary = asyncio.run(resumed.run())

    assert summary["best"] == expected["best"]
    assert [d for d in decisions(tmp_path / "cut") if d["event"] != "run.started"] == \
           [d for d in decisions(tmp_path / "whole") if d["event"] != "run.started"]
    completed = Counter(r["name"] for r in events_of(tmp_path / "cut", "call.completed"))
    assert set(completed.values()) == {1}  # no call was made twice


def test_resume_notices_a_changed_record(tmp_path):
    runner, _ = make_runner(tmp_path)
    asyncio.run(runner.run())
    path = call_file(runner.run_dir, "g0/judge/c001/gpt")
    record = json.loads(path.read_text())
    record["response"]["data"]["novelty"] = 0.01 if record["response"]["data"]["novelty"] > 0.5 else 0.99
    path.write_text(json.dumps(record))
    again, _ = make_runner(tmp_path, resume=True)
    with pytest.raises(ResumeMismatch):
        asyncio.run(again.run())


def test_replay_reproduces_a_run_without_calling_any_model(tmp_path):
    clock = Clock()
    original, _ = make_runner(tmp_path, run_name="a", models={n: FakeModel(n, clock, fresh=True) for n in NAMES})
    expected = asyncio.run(original.run())

    dead = {n: FakeModel(n, fail_roles={"author", "judge"}) for n in NAMES}
    replay, _ = make_runner(tmp_path, run_name="b", models=dead, replay=ReplaySource(tmp_path / "a"))
    summary = asyncio.run(replay.run())
    assert summary["best"] == expected["best"]
    assert all(r["replayed"] for r in events_of(tmp_path / "b", "call.completed"))


def test_replay_calls_only_what_changed(tmp_path):
    original, _ = make_runner(tmp_path, run_name="a")
    asyncio.run(original.run())
    changed_root = tmp_path / "protocol"
    shutil.copytree(ROOT, changed_root, ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    judge_system = changed_root / "prompts" / "judge_system.md"
    judge_system.write_text(judge_system.read_text() + "\nBe brief.")
    replay, _ = make_runner(tmp_path, run_name="b", replay=ReplaySource(tmp_path / "a"), protocol=load_protocol(changed_root))
    asyncio.run(replay.run())
    calls = events_of(tmp_path / "b", "call.completed")
    assert all(c["replayed"] for c in calls if c["name"].startswith("g0/write/"))
    assert not any(c["replayed"] for c in calls if "/judge/" in c["name"])


def test_gen0_from_shares_generation_zero_only(tmp_path):
    clock = Clock()
    first, _ = make_runner(tmp_path, run_name="a", models={n: FakeModel(n, clock, fresh=True) for n in NAMES})
    asyncio.run(first.run())
    second, _ = make_runner(tmp_path, run_name="b", judges="all", replay=ReplaySource(tmp_path / "a", keep=gen0_writing),
                            models={n: FakeModel(n, clock, fresh=True) for n in NAMES})
    asyncio.run(second.run())
    seeds_a = [c["answer"] for c in events_of(tmp_path / "a", "candidate.created") if c["generation"] == 0]
    seeds_b = [c["answer"] for c in events_of(tmp_path / "b", "candidate.created") if c["generation"] == 0]
    assert seeds_a == seeds_b
    calls = events_of(tmp_path / "b", "call.completed")
    assert all(c["replayed"] == c["name"].startswith("g0/write/") for c in calls)
