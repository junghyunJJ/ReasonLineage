"""The J1 gate with a fake checker: shadow mode, enforcement, failures, reuse, and version pinning."""

import asyncio
from dataclasses import replace

import pytest

from fakes import FakeChecker
from reasonlineage.checks.gate import Gate
from reasonlineage.checks.questions import j1_questions
from reasonlineage.engine.errors import RunStopped
from reasonlineage.engine.events import read_events
from reasonlineage.protocol import load_protocol

PROTOCOL = load_protocol()
ENFORCED = replace(PROTOCOL, data={**PROTOCOL.data, "j1": {**PROTOCOL.j1, "enforce": True}})
ANSWER = {"answer": "metformin first; imatinib; sildenafil", "ranking": [
    {"item": "metformin", "promisingness": 0.8, "confidence": 0.6, "pmids": []},
    {"item": "imatinib", "promisingness": 0.5, "confidence": 0.6, "pmids": []},
    {"item": "sildenafil", "promisingness": 0.3, "confidence": 0.6, "pmids": []},
]}


def ask(gate, attempt=0, cid="c001"):
    return asyncio.run(gate(cid, 0, "opus", ANSWER, attempt))


def test_questions_follow_the_protocol_and_jev_format():
    questions = j1_questions(PROTOCOL, "metformin")
    assert [q.name for q in questions] == ["answer_type", "top_item_argument", "argument_coverage"]
    assert "metformin" in questions[1].instructions
    assert questions[0].to_jev()["criteria"]["answer"] == "An answer to the question"
    assert questions[1].to_jev() == {"type": "noul", "instructions": questions[1].instructions}
    assert questions[2].to_jev()["criteria"] == ["None of the items", "Some of the items", "Most of the items", "All of the items"]


def test_shadow_mode_records_but_never_rewrites(tmp_path):
    gate = Gate(tmp_path, FakeChecker(argued=0.1), PROTOCOL, "Q?", "experiment")
    decision = ask(gate)
    assert decision.rewrite is False
    record = read_events(tmp_path / "checks.jsonl")[0]
    assert record["would_rewrite"] is True and record["enforced"] is False
    assert record["reasons"] == ["The top-ranked item, metformin, has no specific argument (a reason, a mechanism, or a named study)."]


def test_an_enforced_gate_rewrites_once(tmp_path):
    gate = Gate(tmp_path, FakeChecker(normal=0.2), ENFORCED, "Q?", "experiment")
    first = ask(gate)
    assert first.rewrite is True and "direct answer" in first.reasons[0]
    assert ask(gate, attempt=1).rewrite is False


def test_a_checker_failure_passes_the_answer(tmp_path):
    gate = Gate(tmp_path, FakeChecker(fail=True), ENFORCED, "Q?", "experiment")
    assert ask(gate).rewrite is False
    assert read_events(tmp_path / "checks.jsonl")[0]["error"] == "fake outage"


def test_results_are_reused_on_resume_and_from_source_runs(tmp_path):
    checker = FakeChecker()
    ask(Gate(tmp_path / "a", checker, PROTOCOL, "Q?", "experiment"))
    ask(Gate(tmp_path / "a", checker, PROTOCOL, "Q?", "experiment"))
    assert len(checker.asked) == 1
    ask(Gate(tmp_path / "b", checker, PROTOCOL, "Q?", "experiment", sources=[tmp_path / "a"]))
    assert len(checker.asked) == 1
    assert read_events(tmp_path / "b" / "checks.jsonl")[0]["replayed"] is True


def test_identical_rewrite_reuses_judgment_but_records_both_attempts(tmp_path):
    checker = FakeChecker(argued=.1)
    gate = Gate(tmp_path, checker, ENFORCED, 'Q?', 'experiment')
    assert ask(gate).rewrite
    ask(gate, attempt=1)
    records = read_events(tmp_path / 'checks.jsonl')
    assert len(checker.asked) == 1
    assert [r['attempt'] for r in records] == [0, 1]
    assert records[1]['would_rewrite']
    ask(Gate(tmp_path, checker, ENFORCED, 'Q?', 'experiment'), attempt=1)
    assert len(read_events(tmp_path / 'checks.jsonl')) == 2


def test_a_different_checker_version_stops_experiments_and_warns_in_exploration(tmp_path):
    moved = FakeChecker(model="jev-1.14.0", pinned="jev-1.13.0")
    with pytest.raises(RunStopped, match="not the pinned jev-1.13.0"):
        ask(Gate(tmp_path / "exp", moved, PROTOCOL, "Q?", "experiment"))
    ask(Gate(tmp_path / "explore", moved, PROTOCOL, "Q?", "exploration"))
    assert "jev-1.14.0" in read_events(tmp_path / "explore" / "checks.jsonl")[0]["warning"]
