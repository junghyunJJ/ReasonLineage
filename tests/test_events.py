import json

import pytest

from reasonlineage.engine.errors import ResumeMismatch
from reasonlineage.engine.events import EventLog, read_events


def test_a_new_log_writes_decisions_and_refuses_an_existing_file(tmp_path):
    log = EventLog(tmp_path / "run" / "events.jsonl")
    log.emit("selection", generation=0, survivors=["c001"])
    records = read_events(log.path)
    assert records[0]["event"] == "selection" and records[0]["survivors"] == ["c001"] and "ts" in records[0]
    with pytest.raises(FileExistsError):
        EventLog(log.path)


def test_resume_checks_recorded_decisions_then_appends(tmp_path):
    path = tmp_path / "events.jsonl"
    first = EventLog(path)
    first.emit("run.started", seed=7)
    first.append_call("call.completed", name="g0/write/c001/opus", key="k")
    first.emit("candidate.created", id="c001", scores={"a": 0.5})
    size = path.stat().st_size

    again = EventLog(path, resume=True)
    assert again.recorded_call("g0/write/c001/opus")["key"] == "k"
    again.emit("run.started", seed=7)
    again.emit("candidate.created", id="c001", scores={"a": 0.5})
    assert path.stat().st_size == size  # checked, not rewritten
    again.emit("selection", generation=0)
    again.finish()
    assert [r["event"] for r in read_events(path)][-1] == "selection"


def test_resume_stops_on_a_different_decision(tmp_path):
    path = tmp_path / "events.jsonl"
    EventLog(path).emit("candidate.scored", candidate="c001", fitness=0.61)
    again = EventLog(path, resume=True)
    with pytest.raises(ResumeMismatch, match="differs"):
        again.emit("candidate.scored", candidate="c001", fitness=0.62)


def test_finish_notices_missing_decisions(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.emit("a")
    log.emit("b")
    again = EventLog(path, resume=True)
    again.emit("a")
    with pytest.raises(ResumeMismatch, match="1 more"):
        again.finish()


def test_half_written_last_line_is_cut_on_resume(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.emit("a")
    with path.open("a") as handle:
        handle.write('{"event": "b", "half')
    assert [r["event"] for r in read_events(path)] == ["a"]
    again = EventLog(path, resume=True)
    again.emit("a")
    again.emit("c")
    assert [json.loads(line)["event"] for line in path.read_text().splitlines()] == ["a", "c"]


def test_failed_calls_and_notes_are_not_decisions(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append_call("call.failed", name="g0/judge/c001/gpt", attempt=0, error="timeout")
    log.stop("judge failed")
    again = EventLog(path, resume=True)
    assert again.recorded_call("g0/judge/c001/gpt") is None
    again.note("run.resumed", warnings=[])
    again.emit("run.started")
    again.finish()
    with pytest.raises(ValueError):
        again.note("selection")
