"""The run's event log, events.jsonl (spec 6.2, 6.3).

Two kinds of lines share the file:
- call lines (`call.completed`, `call.failed`) are a memo of model calls, written as calls
  finish, in any order;
- decision lines (everything else) come in a fixed order that depends only on the answers
  the calls returned.
On resume the engine runs again from the start. Recorded calls come back from the memo, and
each decision is checked against the recorded one before any new line is written.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ResumeMismatch

CALL_EVENTS = frozenset({"call.completed", "call.failed"})
# Notes about the run itself, not decisions; never checked on resume.
UNCHECKED_EVENTS = frozenset({"run.stopped", "run.resumed"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _plain(record: dict[str, Any]) -> dict[str, Any]:
    """The record as it reads back from JSON, without its timestamp."""
    clean = json.loads(json.dumps(record, ensure_ascii=False, default=str))
    clean.pop("ts", None)
    return clean


def read_events(path: str | Path) -> list[dict[str, Any]]:
    """Every complete line of a JSONL file; an unreadable line (a half-written last one) is skipped."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


class EventLog:
    def __init__(self, path: str | Path, *, resume: bool = False) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._calls: dict[str, dict[str, Any]] = {}
        self._failed: dict[str, int] = {}
        self._expected: list[dict[str, Any]] = []
        self._cursor = 0
        if not resume:
            if self.path.exists() and self.path.stat().st_size:
                raise FileExistsError(f"{self.path} already has events; resume the run instead")
            return
        self._cut_partial_line()
        for record in read_events(self.path):
            if record["event"] == "call.completed":
                self._calls[record["name"]] = record
            elif record["event"] == "call.failed":
                self._failed[record["name"]] = self._failed.get(record["name"], 0) + 1
            elif record["event"] not in CALL_EVENTS | UNCHECKED_EVENTS:
                self._expected.append(_plain(record))

    def _cut_partial_line(self) -> None:
        """Remove a half-written last line so new lines start cleanly."""
        if not self.path.exists():
            return
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            with self.path.open("r+b") as handle:
                handle.truncate(raw.rfind(b"\n") + 1)

    def recorded_call(self, name: str) -> dict[str, Any] | None:
        return self._calls.get(name)

    def failed_attempts(self, name: str) -> int:
        """How many attempts at this call have failed so far, in this run and before a resume."""
        return self._failed.get(name, 0)

    def append_call(self, event: str, **fields: Any) -> None:
        record = {"ts": _now(), "event": event, **fields}
        self._write(record)
        if event == "call.completed":
            self._calls[fields["name"]] = record
        elif event == "call.failed":
            self._failed[fields["name"]] = self._failed.get(fields["name"], 0) + 1

    def emit(self, event: str, **fields: Any) -> None:
        """Record a decision, or on resume check it against the recorded one."""
        record = _plain({"event": event, **fields})
        if self._cursor < len(self._expected):
            recorded = self._expected[self._cursor]
            if recorded != record:
                raise ResumeMismatch(f"decision {self._cursor} differs on resume:\n recorded {recorded}\n now      {record}")
            self._cursor += 1
            return
        self._write({"ts": _now(), **record})

    def note(self, event: str, **fields: Any) -> None:
        """Record something about the run itself (for example `run.resumed`); never checked."""
        if event not in UNCHECKED_EVENTS:
            raise ValueError(f"{event} is a decision; use emit()")
        self._write({"ts": _now(), "event": event, **fields})

    def stop(self, reason: str) -> None:
        self.note("run.stopped", reason=reason)

    def finish(self) -> None:
        if self._cursor < len(self._expected):
            raise ResumeMismatch(f"the recorded run has {len(self._expected) - self._cursor} more decisions than this one")

    def _write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
