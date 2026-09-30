"""Every model call goes through CallRecorder (spec 6.3, 6.5).

It names the call, derives its seed, retries once, saves the request and response under
calls/, and serves an answer it already has: one recorded in this run (resume) or one
recorded by another run (replay and --gen0-from).
"""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

from ..backends.base import BackendError, ModelBackend, ModelRequest, ModelResponse
from .errors import RunCorrupted
from .events import EventLog, read_events


def derive_seed(run_seed: int, name: str, attempt: int) -> int:
    """The first 8 hex digits of sha256("<run seed>:<call name>:<attempt>") as an integer."""
    return int(hashlib.sha256(f"{run_seed}:{name}:{attempt}".encode()).hexdigest()[:8], 16)


def cache_key(member: str, request: ModelRequest) -> str:
    """What makes two requests the same for replay. The seed and the timeout are left out."""
    payload = {
        "member": member,
        "model": request.model,
        "effort": request.effort,
        "system": request.system,
        "prompt": request.prompt,
        "schema": request.json_schema,
        "max_tokens": request.max_tokens,
        "top_logprobs": request.top_logprobs,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def call_file(run_dir: Path, name: str) -> Path:
    return Path(run_dir) / "calls" / f"{name}.json"


def call_role(name: str) -> tuple[int, str]:
    """"g1/judge/c006/opus" -> (1, "judge")."""
    generation, role = name.split("/")[:2]
    return int(generation[1:]), role


def gen0_writing(name: str) -> bool:
    """The calls --gen0-from reuses: generation-0 writing, realigning, and J1 rewrites."""
    generation, role = call_role(name)
    return generation == 0 and role in {"write", "realign", "rewrite"}


def _load_call(run_dir: Path, name: str) -> dict[str, Any]:
    path = call_file(run_dir, name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunCorrupted(f"recorded call {name} has no readable {path}: {exc}") from None


def _usage(raw: Any) -> dict[str, Any]:
    usage = (raw or {}).get("usage") or {}
    return {
        "input": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output": usage.get("output_tokens", usage.get("completion_tokens")),
    }


def _unusable(check: Callable[[ModelResponse], Any] | None, response: ModelResponse) -> str | None:
    """Why the engine cannot use this output, or None when it can."""
    if check is None:
        return None
    try:
        check(response)
    except ValueError as exc:
        return f"unusable output: {exc}"
    return None


class ReplaySource:
    """Answers recorded by another run, offered by cache key. When both runs use the same call
    name the matching call is used; otherwise identical requests are matched in order."""

    def __init__(self, run_dir: str | Path, keep: Callable[[str], bool] | None = None) -> None:
        self.run_dir = Path(run_dir)
        self._names: dict[str, list[str]] = {}
        for record in read_events(self.run_dir / "events.jsonl"):
            if record["event"] == "call.completed" and (keep is None or keep(record["name"])):
                self._names.setdefault(record["key"], []).append(record["name"])
        self._used: set[str] = set()

    def take(self, key: str, name: str) -> dict[str, Any] | None:
        free = [n for n in self._names.get(key, []) if n not in self._used]
        if not free:
            return None
        chosen = name if name in free else free[0]
        self._used.add(chosen)
        return _load_call(self.run_dir, chosen)

    def mark_used(self, key: str, name: str) -> None:
        if name in self._names.get(key, []):
            self._used.add(name)


class CallRecorder:
    def __init__(self, run_dir: str | Path, events: EventLog, run_seed: int,
                 replay: ReplaySource | None = None, attempts: int = 2) -> None:
        self.run_dir = Path(run_dir)
        self.events = events
        self.run_seed = run_seed
        self.replay = replay
        self.attempts = attempts

    async def call(self, name: str, member: str, backend: ModelBackend, request: ModelRequest,
                   check: Callable[[ModelResponse], Any] | None = None) -> ModelResponse:
        """`check` raises ValueError for output the engine cannot use; that counts as a failed attempt,
        so it is retried with a new seed and never stored as the call's answer."""
        key = cache_key(member, request)
        if self.events.recorded_call(name) is not None:
            if self.replay is not None:
                self.replay.mark_used(key, name)
            return ModelResponse(**_load_call(self.run_dir, name)["response"])
        if self.replay is not None:
            stored = self.replay.take(key, name)
            if stored is not None:
                response = ModelResponse(**stored["response"])
                return self._save(name, member, request, key, response, stored["request"].get("seed"), replayed=True)
        errors = []
        first = self.events.failed_attempts(name)  # after a resume, the attempts go on with new seeds
        for attempt in range(first, first + self.attempts):
            seed = derive_seed(self.run_seed, name, attempt)
            try:
                response = await backend.complete(replace(request, seed=seed))
            except BackendError as exc:
                error = str(exc)
            else:
                error = _unusable(check, response)
                if error is None:
                    return self._save(name, member, request, key, response, seed, replayed=False)
            errors.append(error)
            self.events.append_call("call.failed", name=name, member=member, attempt=attempt, error=error[:500])
        raise BackendError(f"{name} failed after {self.attempts} attempt(s): {errors}")

    def _save(self, name: str, member: str, request: ModelRequest, key: str,
              response: ModelResponse, seed: int | None, replayed: bool) -> ModelResponse:
        path = call_file(self.run_dir, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"request": {"member": member, **asdict(replace(request, seed=seed))}, "response": asdict(response)}
        path.write_text(json.dumps(record, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
        self.events.append_call(
            "call.completed", name=name, member=member, model=request.model, effort=request.effort, seed=seed,
            key=key, duration_s=round(response.duration_s, 3), tokens=_usage(response.raw), replayed=replayed,
            file=path.relative_to(self.run_dir).as_posix(),
        )
        return response
