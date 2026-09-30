"""How the runner handles bad answers, failed calls, stagnation, and the J1 gate (spec 5.9, 5.10)."""

import asyncio

import pytest

from fakes import CANDIDATES, FakeGate, FakeModel, events_of, make_runner
from reasonlineage.engine.errors import RunStopped

NAMES = ("opus", "gpt", "grok", "qwen")


def models(**special):
    return {n: special.get(n) or FakeModel(n) for n in NAMES}


def test_a_ranking_with_a_missing_item_is_realigned_once(tmp_path):
    runner, _ = make_runner(tmp_path, generations=1, models=models(opus=FakeModel("opus", bad_first=1)))
    asyncio.run(runner.run())
    first = events_of(runner.run_dir, "candidate.created")[0]
    assert first["versions"] == ["g0/write/c001/opus", "g0/realign/c001/opus"]
    assert sorted(e["item"] for e in first["answer"]["ranking"]) == sorted(CANDIDATES)
    assert events_of(runner.run_dir, "anomaly") == []


def test_an_unfixable_answer_stops_an_experiment(tmp_path):
    runner, _ = make_runner(tmp_path, generations=1, models=models(opus=FakeModel("opus", bad_first=2)))
    with pytest.raises(RunStopped, match="write c001 by opus failed"):
        asyncio.run(runner.run())
    assert events_of(runner.run_dir, "run.stopped")[0]["reason"].startswith("write c001 by opus")


def test_exploration_substitutes_another_model_for_a_failed_writer(tmp_path):
    runner, _ = make_runner(tmp_path, mode="exploration", generations=1,
                            models=models(opus=FakeModel("opus", fail_roles={"author"})))
    asyncio.run(runner.run())
    first = events_of(runner.run_dir, "candidate.created")[0]
    assert first["author"] == "gpt" and first["versions"] == ["g0/write/c001/gpt"]
    anomaly = events_of(runner.run_dir, "anomaly")[0]
    assert anomaly["kind"] == "writing_failed" and anomaly["action"] == "substituted gpt"


def test_a_failed_judge_stops_an_experiment_but_is_skipped_in_exploration(tmp_path):
    broken = models(grok=FakeModel("grok", fail_roles={"judge"}))
    runner, _ = make_runner(tmp_path / "exp", generations=1, models=broken)
    with pytest.raises(RunStopped, match="judge grok"):
        asyncio.run(runner.run())
    runner, _ = make_runner(tmp_path / "explore", mode="exploration", generations=1,
                            models=models(grok=FakeModel("grok", fail_roles={"judge"})))
    asyncio.run(runner.run())
    skipped = [a for a in events_of(runner.run_dir, "anomaly") if a["kind"] == "judge_failed"]
    assert skipped and all(a["detail"].startswith("grok:") for a in skipped)
    assert all(s["judge"] != "grok" for s in events_of(runner.run_dir, "judge.scored"))


def test_exploration_tries_one_recovery_after_stagnation_then_stops(tmp_path):
    flat = {n: FakeModel(n, judge_value=0.5) for n in NAMES}
    runner, _ = make_runner(tmp_path, mode="exploration", generations=6, models=flat)
    summary = asyncio.run(runner.run())
    operators = [c["operator"] for c in events_of(runner.run_dir, "candidate.created")]
    assert operators.count("recovery") == 1
    assert summary["termination"] == "stagnation"


def test_experiments_never_recover(tmp_path):
    flat = {n: FakeModel(n, judge_value=0.5) for n in NAMES}
    runner, _ = make_runner(tmp_path, generations=4, models=flat)
    summary = asyncio.run(runner.run())
    assert "recovery" not in [c["operator"] for c in events_of(runner.run_dir, "candidate.created")]
    assert summary["termination"] == "generation_limit"


def test_the_gate_can_ask_for_one_rewrite(tmp_path):
    gate = FakeGate(rewrite_ids={"c001"})
    runner, _ = make_runner(tmp_path, generations=1, gate=gate)
    asyncio.run(runner.run())
    first = events_of(runner.run_dir, "candidate.created")[0]
    assert first["versions"] == ["g0/write/c001/opus", "g0/rewrite/c001/opus"]
    assert ("c001", 0) in gate.calls and ("c001", 1) in gate.calls
    assert ("c002", 1) not in gate.calls


def test_an_invalid_rewrite_keeps_the_earlier_answer(tmp_path):
    gate = FakeGate(rewrite_ids={"c001"})
    opus = FakeModel("opus", bad_when="An automatic check found")
    runner, _ = make_runner(tmp_path, generations=1, gate=gate, models=models(opus=opus))
    asyncio.run(runner.run())
    first = events_of(runner.run_dir, "candidate.created")[0]
    assert len(first["answer"]["ranking"]) == 3
    assert events_of(runner.run_dir, "anomaly")[0]["kind"] == "rewrite_invalid"
