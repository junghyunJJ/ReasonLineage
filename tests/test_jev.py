"""JevChecker against a local fake server that speaks jev's request and response format."""

import asyncio

import pytest

from fake_http import FakeServer
from reasonlineage.checks.base import CheckerError
from reasonlineage.checks.jev import JevChecker, parse_jev
from reasonlineage.checks.questions import j1_questions
from reasonlineage.protocol import load_protocol

QUESTIONS = j1_questions(load_protocol(), "metformin")
REPLY = {"model": "jev-1.13.0", "usage": {"input_tokens": 300, "output_tokens": 12}, "answers": {
    "answer_type": {"type": "choice", "choice": "answer", "confidence": 0.9,
                    "probabilities": {"answer": 0.95, "refusal": 0.01, "meta": 0.02, "grader": 0.02}},
    "top_item_argument": {"type": "noul", "noul": 0.97},
    "argument_coverage": {"type": "score", "score": 2.74, "confidence": 0.7, "legend": {},
                          "probabilities": {"0": 0.01, "1": 0.04, "2": 0.15, "3": 0.80}},
}}


@pytest.fixture
def server():
    fake = FakeServer(reply={"status": 200, "body": REPLY})
    yield fake
    fake.close()


def test_private_data_is_refused_at_construction():
    with pytest.raises(ValueError, match="public"):
        JevChecker("key", "jev-1.13.0", data_sensitivity="private")


def test_request_and_answers(server):
    checker = JevChecker("secret", "jev-1.13.0", data_sensitivity="public", base_url=server.url)
    result = asyncio.run(checker.ask("Question: Q\n\nanswer text", QUESTIONS))
    assert server.paths == ["/v1/systemone"]
    assert server.headers[0]["Authorization"] == "Bearer secret"
    body = server.requests[0]
    assert body["model"] == "jev-1.13.0" and body["state"].startswith("Question: Q")
    assert body["questions"]["top_item_argument"]["type"] == "noul"
    assert result.model == "jev-1.13.0"
    assert result.answers["top_item_argument"].value == 0.97
    assert result.answers["answer_type"].probabilities["answer"] == 0.95
    assert round(result.answers["argument_coverage"].value, 2) == 2.74


def test_errors_become_checker_errors(server):
    server.reply = {"status": 422, "body": {"detail": [{"msg": "bad question"}]}}
    with pytest.raises(CheckerError, match="422"):
        asyncio.run(JevChecker("k", "jev-1.13.0", data_sensitivity="public", base_url=server.url).ask("s", QUESTIONS))
    server.reply = {"status": 200, "body": {"model": "jev-1.13.0", "answers": {}}}
    with pytest.raises(CheckerError, match="no answer"):
        asyncio.run(JevChecker("k", "jev-1.13.0", data_sensitivity="public", base_url=server.url).ask("s", QUESTIONS))


@pytest.mark.parametrize("answers", [
    [],
    {**REPLY["answers"], "answer_type": {"type": "choice", "choice": "answer"}},
    {**REPLY["answers"], "top_item_argument": {"type": "noul", "noul": "high"}},
], ids=["answers-not-an-object", "no-probabilities", "not-a-number"])
def test_a_malformed_reply_is_a_checker_error(answers):
    with pytest.raises(CheckerError, match="unexpected jev"):
        parse_jev({"model": "jev-1.13.0", "answers": answers}, QUESTIONS)
