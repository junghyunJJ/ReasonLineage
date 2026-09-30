"""Deterministic stand-ins for models, and a helper that builds a runner around them."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from reasonlineage.backends.base import BackendError, ModelRequest, ModelResponse
from reasonlineage.engine.calls import CallRecorder
from reasonlineage.engine.config import Member, RunOptions, Task
from reasonlineage.engine.events import CALL_EVENTS, UNCHECKED_EVENTS, EventLog, read_events
from reasonlineage.engine.runner import Runner
from reasonlineage.protocol import load_protocol

CANDIDATES = ("metformin", "imatinib", "sildenafil")
QUESTION = "Which approved drug is most promising to repurpose for idiopathic pulmonary fibrosis?"
FAMILY = {"opus": "anthropic", "sonnet": "anthropic", "gpt": "openai", "luna": "openai", "grok": "xai", "qwen": "alibaba"}


class Crash(Exception):
    """Stands for the process dying mid-run. Not a BackendError, so nothing retries it."""


@dataclass
class Clock:
    """Counts calls across all fake models, so a test can crash the run at call N."""

    calls: int = 0
    crash_at: int | None = None


def digest(*parts: str) -> int:
    return int(hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:8], 16)


def is_judge_call(request: ModelRequest) -> bool:
    return "critique" in (request.json_schema or {}).get("properties", {})


class FakeModel:
    """A model whose output depends only on its name and the prompt, so reruns agree.

    fail_roles: {"author", "judge"} calls that raise BackendError.
    bad_first: the first N author calls leave an item out of the ranking.
    bad_when: author calls whose prompt contains this text leave an item out.
    judge_value: a fixed score for every dimension (otherwise a hash of the prompt).
    fresh: add the call count to the hash, so every call answers differently.
    """

    def __init__(self, name, clock=None, *, fail_roles=(), bad_first=0, bad_when=None, judge_value=None, fresh=False):
        self.name = name
        self.clock = clock or Clock()
        self.fail_roles = set(fail_roles)
        self.bad_first = bad_first
        self.bad_when = bad_when
        self.judge_value = judge_value
        self.fresh = fresh
        self.seen: list[ModelRequest] = []
        self._author_calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.clock.calls += 1
        if self.clock.crash_at is not None and self.clock.calls >= self.clock.crash_at:
            raise Crash(f"crash at call {self.clock.calls}")
        self.seen.append(request)
        role = "judge" if is_judge_call(request) else "author"
        if role in self.fail_roles:
            raise BackendError(f"{self.name}: injected {role} failure")
        salt = str(self.clock.calls) if self.fresh else ""
        if role == "judge":
            data = self._judge(request, salt)
        else:
            self._author_calls += 1
            bad = self._author_calls <= self.bad_first or (self.bad_when is not None and self.bad_when in request.prompt)
            data = self._answer(request, salt, bad)
        return ModelResponse(backend=self.name, model=request.model, text=json.dumps(data), data=data, duration_s=0.01,
                             cost_usd=None, prompt_sha256=request.prompt_sha256,
                             raw={"usage": {"input_tokens": 100, "output_tokens": 50}})

    def _answer(self, request, salt, bad):
        h = digest(self.name, request.prompt, salt)
        order = list(CANDIDATES[h % 3:] + CANDIDATES[:h % 3])
        if bad:
            order = order[:2]
        prose = f"{self.name} answer {h % 1000}: " + ", then ".join(order) + "."
        ranking = [{"item": item, "promisingness": round(0.9 - 0.2 * i, 2), "confidence": 0.6,
                    "pmids": [str(20000000 + h % 1000 + i)]} for i, item in enumerate(order)]
        return {"answer": prose, "ranking": ranking}

    def _judge(self, request, salt):
        h = digest(self.name, request.prompt, salt)
        value = self.judge_value if self.judge_value is not None else round(0.4 + (h % 400) / 1000, 3)
        dims = request.json_schema["required"][:-1]
        return {**{d: value for d in dims}, "critique": [f"{self.name}: tighten point {h % 97}"]}


def make_runner(tmp_path, *, names=("opus", "gpt", "grok", "qwen"), mode="experiment", judges="recuse",
                context="isolated", generations=3, seed=7, question=QUESTION, gate=None, clock=None,
                models=None, resume=False, replay=None, protocol=None, run_name="run"):
    run_dir = Path(tmp_path) / run_name
    members = [Member(n, "http", f"model-{n}", "xhigh", "http://fake/v1", FAMILY[n]) for n in names]
    task = Task("t1", question, CANDIDATES, "biomedical", "public")
    options = RunOptions(mode=mode, judges=judges, context=context, generations=generations, seed=seed)
    events = EventLog(run_dir / "events.jsonl", resume=resume)
    recorder = CallRecorder(run_dir, events, seed, replay=replay)
    clock = clock or Clock()
    models = models or {n: FakeModel(n, clock) for n in names}
    runner = Runner(run_dir=run_dir, run_id=run_name, task=task, members=members, backends=models,
                    protocol=protocol or load_protocol(), options=options, events=events, recorder=recorder, gate=gate)
    return runner, models


def decisions(run_dir) -> list[dict]:
    """The decision lines of a run, without timestamps."""
    out = []
    for record in read_events(Path(run_dir) / "events.jsonl"):
        if record["event"] in CALL_EVENTS | UNCHECKED_EVENTS:
            continue
        record = dict(record)
        record.pop("ts", None)
        out.append(record)
    return out


def events_of(run_dir, kind) -> list[dict]:
    return [r for r in read_events(Path(run_dir) / "events.jsonl") if r["event"] == kind]


class FakeGate:
    """A J1 gate that asks for one rewrite of the listed candidates."""

    def __init__(self, rewrite_ids=()):
        self.rewrite_ids = set(rewrite_ids)
        self.calls = []

    async def __call__(self, candidate_id, generation, author, answer, attempt):
        from reasonlineage.engine.gating import GateDecision

        self.calls.append((candidate_id, attempt))
        if candidate_id in self.rewrite_ids and attempt == 0:
            return GateDecision(True, ("The top-ranked item has no specific argument.",))
        return GateDecision(False)


class FakeChecker:
    """A checker with fixed probabilities: `normal` for "a direct answer", `argued` for the top-item question."""

    name = "fake"

    def __init__(self, *, normal=0.9, argued=0.9, model="fake-1", pinned=None, fail=False):
        self.pinned_version = pinned
        self.model = model
        self.normal = normal
        self.argued = argued
        self.fail = fail
        self.asked = []

    async def ask(self, state, questions):
        from reasonlineage.checks.base import CheckAnswer, CheckerError, CheckResult

        self.asked.append((state, [q.name for q in questions]))
        if self.fail:
            raise CheckerError("fake outage")
        answers = {}
        for q in questions:
            if q.name == "answer_type":
                probs = {"answer": self.normal, "refusal": 0.0, "meta": 0.0, "grader": round(1 - self.normal, 4)}
            elif q.kind == "noul":
                probs = {"yes": self.argued, "no": round(1 - self.argued, 4)}
            elif q.kind == "score":
                probs = {str(i): (1.0 if i == len(q.levels) - 1 else 0.0) for i in range(len(q.levels))}
            else:
                probs = {name: 1.0 / len(q.choices) for name, _ in q.choices}
            answers[q.name] = CheckAnswer(q.kind, probs)
        return CheckResult(self.model, answers)
