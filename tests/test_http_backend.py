"""HttpBackend against a local fake server (no network, no GPU)."""

import asyncio
import json
import threading

import pytest

from fake_http import FakeServer
from reasonlineage.backends import BackendError, ModelRequest
from reasonlineage.backends.base import ProviderRefusal
from reasonlineage.backends.http import HttpBackend, clean_content
from reasonlineage.engine.calls import CallRecorder
from reasonlineage.engine.events import EventLog

SCHEMA = {"type": "object", "properties": {"score": {"type": "number"}}, "required": ["score"], "additionalProperties": False}


def chat_reply(content, finish="stop", **message):
    return {"status": 200, "body": {"model": "Qwen/Qwen3.8-Flash-Next-FP8", "usage": {"prompt_tokens": 12, "completion_tokens": 30},
                                    "choices": [{"finish_reason": finish, "message": {"content": content, **message},
                                                 "logprobs": {"content": [{"token": "yes", "logprob": -0.1, "top_logprobs": []}]}}]}}


@pytest.fixture
def server():
    fake = FakeServer()
    yield fake
    fake.close()


def request(**overrides):
    base = {"system": "You are a strict evaluator.", "prompt": "hello", "model": "Qwen/Qwen3.8-Flash-Next-FP8"}
    return ModelRequest(**{**base, **overrides})


def test_body_is_isolated_and_explicit():
    body = HttpBackend("qwen", "http://x/v1").build_body(request(effort="xhigh", seed=7, max_tokens=64000, json_schema=SCHEMA))
    assert "tools" not in body and "tool_choice" not in body
    system, user = body["messages"]
    assert system["role"] == "system" and user == {"role": "user", "content": "hello"}
    assert system["content"] == ("You are a strict evaluator.\n\nReply with only a JSON object that matches this JSON schema, "
                                 "and no other text:\n" + json.dumps(SCHEMA))
    assert body["reasoning_effort"] == "xhigh"
    assert body["seed"] == 7 and body["max_tokens"] == 64000
    assert body["response_format"]["json_schema"] == {"name": "output", "schema": SCHEMA, "strict": True}
    assert "logprobs" not in body


def test_logprobs_are_requested_only_when_asked():
    body = HttpBackend("deepseek", "http://x/v1").build_body(request(top_logprobs=10))
    assert body["logprobs"] is True and body["top_logprobs"] == 10
    assert body["messages"][0] == {"role": "system", "content": "You are a strict evaluator."}


def test_round_trip_parses_structured_output(server):
    server.reply = chat_reply('{"score": 0.7}', reasoning="thinking...")
    backend = HttpBackend("qwen", server.url)
    response = asyncio.run(backend.complete(request(json_schema=SCHEMA, effort="xhigh")))
    assert response.data == {"score": 0.7}
    assert response.raw["reasoning"] == "thinking..."
    assert response.raw["logprobs"][0]["token"] == "yes"
    assert server.paths == ["/v1/chat/completions"]
    assert server.requests[0]["reasoning_effort"] == "xhigh"


def test_think_block_and_code_fence_are_removed(server):
    server.reply = chat_reply('<think>long reasoning</think>\n```json\n{"score": 0.4}\n```')
    response = asyncio.run(HttpBackend("qwen", server.url).complete(request(json_schema=SCHEMA)))
    assert response.data == {"score": 0.4}
    assert clean_content("plain") == "plain"


def test_the_last_json_object_after_prose_is_the_output(server):
    server.reply = chat_reply('Prose that mentions {"score": 0.1} in passing.\n\nFinal:\n{"score": 0.6}')
    response = asyncio.run(HttpBackend("glm", server.url, api_key="k").complete(request(json_schema=SCHEMA)))
    assert response.data == {"score": 0.6}
    assert server.headers[0]["Authorization"] == "Bearer k"
    server.reply = chat_reply("Prose only, no JSON.")
    with pytest.raises(BackendError, match="no structured output"):
        asyncio.run(HttpBackend("glm", server.url).complete(request(json_schema=SCHEMA)))


def test_http_error_and_truncation_raise(server):
    server.reply = {"status": 400, "body": {"error": "bad reasoning_effort"}}
    with pytest.raises(BackendError, match="HTTP 400"):
        asyncio.run(HttpBackend("qwen", server.url).complete(request()))
    server.reply = chat_reply('{"score": 0.4', finish="length")
    with pytest.raises(BackendError, match="cut off"):
        asyncio.run(HttpBackend("qwen", server.url).complete(request(json_schema=SCHEMA)))


@pytest.mark.parametrize('content,finish,refusal', [
    (None, 'content_filter', None),
    (None, 'stop', 'Provider declined the request'),
    ('{"score": 0.7}', 'stop', 'Provider declined the request'),
])
def test_explicit_provider_refusal_stops_backend_and_recorder_retries(server, tmp_path, content, finish, refusal):
    server.reply = chat_reply(content, finish=finish, refusal=refusal)
    backend = HttpBackend('qwen', server.url, retries=2)
    recorder = CallRecorder(tmp_path, EventLog(tmp_path/'events.jsonl'), 7, attempts=3)
    with pytest.raises(ProviderRefusal):
        asyncio.run(recorder.call('g0/write/c001/qwen', 'qwen', backend, request(json_schema=SCHEMA)))
    assert len(server.requests) == 1


def test_unreachable_server_raises_backend_error():
    with pytest.raises(BackendError, match="failed"):
        asyncio.run(HttpBackend("qwen", "http://127.0.0.1:9/v1").complete(request(timeout_s=2)))


def test_served_models(server):
    assert HttpBackend("qwen", server.url).served_models() == ["Qwen/Qwen3.8-Flash-Next-FP8"]


def test_a_cancelled_request_keeps_its_slot_until_the_thread_finishes():
    started, release = threading.Event(), threading.Event()

    class BlockingHTTP(HttpBackend):
        def __init__(self):
            super().__init__("http", "http://unused", max_concurrency=1)
            self.calls = self.active = self.peak = 0

        def _send(self, path, body, timeout_s):
            self.calls += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                if self.calls == 1:
                    started.set()
                    release.wait(2)
                return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            finally:
                self.active -= 1

    service = BlockingHTTP()

    async def exercise():
        first = asyncio.create_task(service.complete(ModelRequest("s", "p", "fake")))
        assert await asyncio.to_thread(started.wait, 10), "the worker thread never started"
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(service.complete(ModelRequest("s", "p", "fake")))
        try:
            await asyncio.sleep(.03)
            assert service.calls == 1          # the cancelled thread still holds the only slot
        finally:
            release.set()
            await second
        assert service.peak == 1 and service.calls == 2

    asyncio.run(exercise())
