"""HttpBackend against a local fake server (no network, no GPU)."""

import asyncio

import pytest

from fake_http import FakeServer
from reasonlineage.backends import BackendError, ModelRequest
from reasonlineage.backends.http import HttpBackend, clean_content

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
    assert body["messages"] == [{"role": "system", "content": "You are a strict evaluator."}, {"role": "user", "content": "hello"}]
    assert body["reasoning_effort"] == "xhigh"
    assert body["seed"] == 7 and body["max_tokens"] == 64000
    assert body["response_format"]["json_schema"] == {"name": "output", "schema": SCHEMA, "strict": True}
    assert "logprobs" not in body


def test_logprobs_are_requested_only_when_asked():
    body = HttpBackend("deepseek", "http://x/v1").build_body(request(top_logprobs=10))
    assert body["logprobs"] is True and body["top_logprobs"] == 10


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


def test_http_error_and_truncation_raise(server):
    server.reply = {"status": 400, "body": {"error": "bad reasoning_effort"}}
    with pytest.raises(BackendError, match="HTTP 400"):
        asyncio.run(HttpBackend("qwen", server.url).complete(request()))
    server.reply = chat_reply('{"score": 0.4', finish="length")
    with pytest.raises(BackendError, match="cut off"):
        asyncio.run(HttpBackend("qwen", server.url).complete(request(json_schema=SCHEMA)))


def test_unreachable_server_raises_backend_error():
    with pytest.raises(BackendError, match="failed"):
        asyncio.run(HttpBackend("qwen", "http://127.0.0.1:9/v1").complete(request(timeout_s=2)))


def test_served_models(server):
    assert HttpBackend("qwen", server.url).served_models() == ["Qwen/Qwen3.8-Flash-Next-FP8"]
