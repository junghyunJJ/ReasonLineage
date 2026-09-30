"""J2 diagnostics on a small hand-written event log."""

import asyncio
import json

import pytest

from diagnose_data import EVENTS, write_events
from fakes import FakeChecker
from reasonlineage.diagnose.j2 import j2_jobs, load_gold_items, run_j2
from reasonlineage.engine.config import ConfigError
from reasonlineage.engine.events import read_events
from reasonlineage.protocol import load_protocol

PROTOCOL = load_protocol()


def test_j2_asks_style_per_answer_outcome_per_gold_item_and_severity_per_judge_output():
    jobs = j2_jobs(EVENTS, PROTOCOL, "Q?", [{"item": "metformin", "outcome_date": "2026-03-01"}])
    assert [j["kind"] for j in jobs] == ["style_inflation", "outcome_mention", "critique_severity", "style_inflation", "outcome_mention"]
    assert "metformin" in jobs[1]["questions"][0].instructions
    assert jobs[2]["state"] == "- cite a trial" and jobs[2]["judge"] == "gpt"


def test_run_j2_writes_answers_and_skips_them_next_time(tmp_path):
    write_events(tmp_path)
    checker = FakeChecker()
    out = asyncio.run(run_j2(tmp_path, checker, PROTOCOL, "Q?"))
    assert len(read_events(out)) == 3 and len(checker.asked) == 3
    asyncio.run(run_j2(tmp_path, checker, PROTOCOL, "Q?"))
    assert len(checker.asked) == 3


def test_failed_j2_questions_are_retried(tmp_path):
    write_events(tmp_path)
    asyncio.run(run_j2(tmp_path, FakeChecker(fail=True), PROTOCOL, "Q?"))
    working = FakeChecker()
    asyncio.run(run_j2(tmp_path, working, PROTOCOL, "Q?"))
    assert len(working.asked) == 3


def test_gold_items_file(tmp_path):
    good = tmp_path / "gold.json"
    good.write_text(json.dumps({"items": [{"item": "metformin", "outcome_date": "2026-03-01"}]}))
    assert load_gold_items(good) == [{"item": "metformin", "outcome_date": "2026-03-01"}]
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    with pytest.raises(ConfigError):
        load_gold_items(bad)
