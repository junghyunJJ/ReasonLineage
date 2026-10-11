import asyncio
import json

import pytest

from reasonlineage.backends.base import BackendError, ModelRequest, ModelResponse, ProviderRefusal
from reasonlineage.engine.calls import CallRecorder, ReplaySource, cache_key, call_file, call_role, derive_seed, gen0_writing
from reasonlineage.engine.errors import RunCorrupted
from reasonlineage.engine.events import EventLog, read_events


class Counter:
    """Answers with a running number, so a second real call would look different."""

    def __init__(self, fail_first=0):
        self.requests = []
        self.fail_first = fail_first

    async def complete(self, request):
        self.requests.append(request)
        if len(self.requests) <= self.fail_first:
            raise BackendError("timeout")
        n = len(self.requests)
        return ModelResponse("m", request.model, f"answer {n}", {"n": n}, 0.1, None, request.prompt_sha256, {"usage": {"input_tokens": 5}})


def request(prompt="p", **overrides):
    return ModelRequest(system="s", prompt=prompt, model="m", **overrides)


def recorder(run_dir, **kwargs):
    events = EventLog(run_dir / "events.jsonl", resume=kwargs.pop("resume", False))
    return CallRecorder(run_dir, events, 7, **kwargs), events


def test_seed_depends_on_run_seed_name_and_attempt():
    assert derive_seed(7, "g0/write/c001/opus", 0) == derive_seed(7, "g0/write/c001/opus", 0)
    assert len({derive_seed(7, "g0/write/c001/opus", 0), derive_seed(8, "g0/write/c001/opus", 0),
                derive_seed(7, "g0/write/c002/opus", 0), derive_seed(7, "g0/write/c001/opus", 1)}) == 4
    assert 0 <= derive_seed(7, "x", 0) < 16 ** 8


def test_cache_key_ignores_seed_and_timeout_only():
    assert cache_key("qwen", request(seed=1, timeout_s=5)) == cache_key("qwen", request(seed=2, timeout_s=9))
    assert cache_key("qwen", request()) != cache_key("gpt", request())
    assert cache_key("qwen", request()) != cache_key("qwen", request(prompt="other"))


def test_call_names():
    assert call_role("g1/judge/c006/opus") == (1, "judge")
    assert gen0_writing("g0/realign/c002/gpt") and not gen0_writing("g0/judge/c002/gpt") and not gen0_writing("g1/write/c005/gpt")


def test_a_call_is_saved_and_served_from_the_record_on_resume(tmp_path):
    rec, _ = recorder(tmp_path)
    backend = Counter()
    first = asyncio.run(rec.call("g0/write/c001/opus", "opus", backend, request()))
    assert first.data == {"n": 1}
    assert call_file(tmp_path, "g0/write/c001/opus").exists()
    record = read_events(tmp_path / "events.jsonl")[-1]
    assert record["event"] == "call.completed" and record["seed"] == derive_seed(7, "g0/write/c001/opus", 0)
    assert record["tokens"] == {"input": 5, "output": None} and record["replayed"] is False

    again, _ = recorder(tmp_path, resume=True)
    assert asyncio.run(again.call("g0/write/c001/opus", "opus", backend, request())).data == {"n": 1}
    assert len(backend.requests) == 1  # served from the record, not called again


def test_one_retry_with_a_new_seed(tmp_path):
    rec, _ = recorder(tmp_path)
    backend = Counter(fail_first=1)
    asyncio.run(rec.call("g0/judge/c001/gpt", "gpt", backend, request()))
    assert [r.seed for r in backend.requests] == [derive_seed(7, "g0/judge/c001/gpt", 0), derive_seed(7, "g0/judge/c001/gpt", 1)]
    assert [r["event"] for r in read_events(tmp_path / "events.jsonl")] == ["call.failed", "call.completed"]
    with pytest.raises(BackendError, match="2 attempt"):
        asyncio.run(rec.call("g0/judge/c002/gpt", "gpt", Counter(fail_first=5), request()))


def test_replay_serves_another_runs_answers(tmp_path):
    source, _ = recorder(tmp_path / "a")
    asyncio.run(source.call("g0/write/c001/opus", "opus", Counter(), request("p1")))
    asyncio.run(source.call("g0/judge/c001/gpt", "gpt", Counter(), request("p2")))

    backend = Counter()
    rec, _ = recorder(tmp_path / "b", replay=ReplaySource(tmp_path / "a"))
    assert asyncio.run(rec.call("g0/write/c001/opus", "opus", backend, request("p1"))).text == "answer 1"
    assert backend.requests == []
    assert read_events(tmp_path / "b" / "events.jsonl")[-1]["replayed"] is True
    asyncio.run(rec.call("g0/write/c009/opus", "opus", backend, request("new prompt")))
    assert len(backend.requests) == 1  # a changed request is called anew


def test_identical_requests_replay_in_order(tmp_path):
    source, _ = recorder(tmp_path / "a")
    backend = Counter()
    asyncio.run(source.call("g0/write/c001/opus", "opus", backend, request("same")))
    asyncio.run(source.call("g0/write/c002/opus", "opus", backend, request("same")))
    rec, _ = recorder(tmp_path / "b", replay=ReplaySource(tmp_path / "a"))
    names = ["g0/write/x1/opus", "g0/write/x2/opus"]  # names differ, so matching falls back to order
    texts = [asyncio.run(rec.call(n, "opus", Counter(), request("same"))).text for n in names]
    assert texts == ["answer 1", "answer 2"]


def test_gen0_filter_offers_only_generation_zero_writing(tmp_path):
    source, _ = recorder(tmp_path / "a")
    asyncio.run(source.call("g0/judge/c001/gpt", "gpt", Counter(), request("j")))
    replay = ReplaySource(tmp_path / "a", keep=gen0_writing)
    assert replay.take(cache_key("gpt", request("j")), "g0/judge/c001/gpt") is None


def test_missing_call_file_on_resume_is_a_clear_error(tmp_path):
    rec, _ = recorder(tmp_path)
    asyncio.run(rec.call("g0/write/c001/opus", "opus", Counter(), request()))
    call_file(tmp_path, "g0/write/c001/opus").write_text("{broken")
    again, _ = recorder(tmp_path, resume=True)
    with pytest.raises(RunCorrupted, match="g0/write/c001/opus"):
        asyncio.run(again.call("g0/write/c001/opus", "opus", Counter(), request()))


def test_unusable_output_is_a_failed_attempt(tmp_path):
    rec, _ = recorder(tmp_path)

    def check(response):
        if response.data["n"] < 2:
            raise ValueError("n is too small")

    assert asyncio.run(rec.call("g0/write/c001/opus", "opus", Counter(), request(), check=check)).data == {"n": 2}
    failed, completed = read_events(tmp_path / "events.jsonl")
    assert failed["event"] == "call.failed" and failed["error"] == "unusable output: n is too small"
    assert completed["event"] == "call.completed" and completed["seed"] == derive_seed(7, "g0/write/c001/opus", 1)


def test_a_resumed_call_retries_with_new_seeds(tmp_path):
    rec, _ = recorder(tmp_path)
    with pytest.raises(BackendError):
        asyncio.run(rec.call("g0/write/c001/opus", "opus", Counter(fail_first=5), request()))
    again, _ = recorder(tmp_path, resume=True)
    backend = Counter()
    asyncio.run(again.call("g0/write/c001/opus", "opus", backend, request()))
    assert [r.seed for r in backend.requests] == [derive_seed(7, "g0/write/c001/opus", 2)]


class Scripted:
    """Answers with the given data objects in order."""

    def __init__(self, *answers, raw=None):
        self.answers, self.raw, self.requests = list(answers), raw or {}, []

    async def complete(self, request):
        self.requests.append(request)
        data = self.answers[len(self.requests) - 1]
        return ModelResponse("m", request.model, json.dumps(data), data, 0.1, None, request.prompt_sha256, dict(self.raw))


def test_an_unusable_output_is_audited_through_the_sanitizer(tmp_path):
    def check(response):
        if response.data.get("ok") is not True:
            raise ValueError("no ok flag")

    def sanitize(record):
        record["request"]["prompt"] = "[REDACTED]"
        return record

    backend = Scripted({"ok": False, "detail": "first try"}, {"ok": True})
    rec, _ = recorder(tmp_path, unusable_sanitizer=sanitize)
    response = asyncio.run(rec.call("g0/write/c001/m", "m", backend, request("private prompt"), check=check))
    assert response.data == {"ok": True}
    (audit,) = (tmp_path / "unusable").rglob("*.json")
    saved = json.loads(audit.read_text())
    assert saved["attempt"] == 0 and saved["error"] == "unusable output: no ok flag"
    assert saved["request"]["prompt"] == "[REDACTED]" and saved["request"]["member"] == "m"
    assert saved["response"]["data"] == {"ok": False, "detail": "first try"}
    failed = [e for e in read_events(tmp_path / "events.jsonl") if e["event"] == "call.failed"]
    assert failed[0]["file"] == audit.relative_to(tmp_path).as_posix()


@pytest.mark.parametrize("data, raw", [({"refusal": "cannot help"}, {}), ({"answer": "x"}, {"finish_reason": "content_filter"})])
def test_an_explicit_refusal_in_the_answer_is_never_retried(tmp_path, data, raw):
    backend = Scripted(data, {"ok": True}, raw=raw)
    rec, _ = recorder(tmp_path, attempts=3)
    with pytest.raises(ProviderRefusal, match="provider refused request"):
        asyncio.run(rec.call("g0/write/c001/m", "m", backend, request()))
    assert len(backend.requests) == 1
    assert [e["event"] for e in read_events(tmp_path / "events.jsonl")] == ["call.failed", "call.gave_up"]
