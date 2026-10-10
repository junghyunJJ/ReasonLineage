"""Every model call goes through CallRecorder (spec 6.3, 6.5).

It names the call, derives its seed, retries once, saves the request and response under
calls/, and serves an answer it already has: one recorded in this run (resume) or one
recorded by another run (replay and --gen0-from).
"""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from ..backends.base import BackendError, ModelBackend, ModelRequest, ModelResponse, ProviderRefusal
from .errors import RunCorrupted, RunStopped
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


def _provider_refused(response: ModelResponse) -> bool:
    """Explicit provider refusal markers; do not infer refusals from ordinary prose."""
    return (isinstance(response.data, Mapping) and bool(response.data.get('refusal'))
            or (response.raw or {}).get('finish_reason') == 'content_filter')


class ReplaySource:
    """Answers recorded by another run, offered by cache key. When both runs use the same call
    name the matching call is used; otherwise identical requests are matched in order.

    With `required`, every call that `keep` selects must come from this source (--gen0-from):
    a missing one stops the run instead of calling the model."""

    def __init__(self, run_dir: str | Path, keep: Callable[[str], bool] | None = None, required: bool = False) -> None:
        self.run_dir = Path(run_dir)
        self.keep = keep
        self.required = required
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

    def requires(self, name: str) -> bool:
        return self.required and (self.keep is None or self.keep(name))


class CallRecorder:
    def __init__(self, run_dir: str | Path, events: EventLog, run_seed: int,
                 replay: ReplaySource | None = None, attempts: int = 2, *,
                 retry_backend_errors: bool = True,
                 unusable_sanitizer: Callable[[Any], Any] | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.events = events
        self.run_seed = run_seed
        self.replay = replay
        self.attempts = attempts
        self.retry_backend_errors = retry_backend_errors
        self.unusable_sanitizer = unusable_sanitizer

    async def call(self, name: str, member: str, backend: ModelBackend, request: ModelRequest,
                   check: Callable[[ModelResponse], Any] | None = None) -> ModelResponse:
        """`check` raises ValueError for output the engine cannot use. It may be retried with
        a new seed, but never becomes the call's answer. An optional sanitizer enables a
        separate audit of unusable outputs. Provider refusals are never retried."""
        key = cache_key(member, request)
        if self.events.recorded_call(name) is not None:
            if self.replay is not None:
                self.replay.mark_used(key, name)
            return ModelResponse(**_load_call(self.run_dir, name)["response"])
        given_up = self.events.gave_up(name)
        if given_up is not None and self.events.replaying:
            # The recorded decisions ahead were made with this call failing, so it fails the same way.
            raise BackendError(given_up["error"])
        if self.replay is not None:
            stored = self.replay.take(key, name)
            if stored is not None:
                response = ModelResponse(**stored["response"])
                return self._save(name, member, request, key, response, stored["request"].get("seed"), replayed=True)
            if self.replay.requires(name):
                raise RunStopped(f"{name} must come from {self.replay.run_dir}, which has no matching answer; "
                                 "generation 0 is shared only between runs of the same task, protocol, and panel")
        errors = []
        terminal_error = None
        first = self.events.failed_attempts(name)  # after a resume, the attempts go on with new seeds
        for attempt in range(first, first + self.attempts):
            seed = derive_seed(self.run_seed, name, attempt)
            audit = {}
            try:
                response = await backend.complete(replace(request, seed=seed))
            except BackendError as exc:
                error = str(exc)
                if isinstance(exc, ProviderRefusal) or not self.retry_backend_errors:
                    terminal_error = exc
            else:
                if _provider_refused(response):
                    error = 'provider refused request'
                    terminal_error = ProviderRefusal(error)
                else:
                    error = _unusable(check, response)
                if error is None:
                    return self._save(name, member, request, key, response, seed, replayed=False)
                if self.unusable_sanitizer is not None:
                    path = self._save_unusable(name, member, request, response, seed, attempt, error)
                    audit['file'] = path.relative_to(self.run_dir).as_posix()
            errors.append(error)
            self.events.append_call("call.failed", name=name, member=member, attempt=attempt, error=error[:500], **audit)
            if terminal_error is not None:
                break
        message = f"{name} failed after {len(errors)} attempt(s): {errors}"
        self.events.append_call("call.gave_up", name=name, member=member, error=message)
        if terminal_error is not None:
            raise terminal_error
        raise BackendError(message)

    def _save_unusable(self, name: str, member: str, request: ModelRequest,
                       response: ModelResponse, seed: int, attempt: int, error: str) -> Path:
        path = self.run_dir / 'unusable' / name / f'attempt-{attempt}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'attempt': attempt, 'error': error,
                  'request': {'member': member, **asdict(replace(request, seed=seed))},
                  'response': asdict(response)}
        record = self.unusable_sanitizer(record)
        path.write_text(json.dumps(record, ensure_ascii=False, default=str, indent=1), encoding='utf-8')
        return path

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
