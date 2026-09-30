"""Task files, the setup file (panel and checkers), run options, and building backends (spec 5.1, 8)."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..backends.base import BackendError, ModelBackend
from ..backends.claude_cli import ClaudeCLIBackend
from ..backends.codex_cli import CodexCLIBackend
from ..backends.grok_cli import GrokCLIBackend
from ..backends.http import HttpBackend
from ..backends.roster import FAMILIES
from ..core.categories import CATEGORY_PRESETS

SENSITIVITY = ("public", "private")
BACKEND_KINDS = ("claude", "codex", "grok", "http")


class ConfigError(ValueError):
    """A task, setup, or option is invalid. The message says what to fix."""


def read_key_file(path: str | None) -> str | None:
    """The key stored in `path`, without surrounding whitespace; None when there is no readable file."""
    if not path:
        return None
    try:
        return Path(path).expanduser().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from None


@dataclass(frozen=True)
class Task:
    id: str
    question: str
    candidates: tuple[str, ...] | None
    category: str
    data_sensitivity: str

    @property
    def weights(self) -> Mapping[str, float]:
        return CATEGORY_PRESETS[self.category].weights

    @property
    def threshold(self) -> float:
        return CATEGORY_PRESETS[self.category].threshold

    @property
    def emphasis(self) -> str:
        return CATEGORY_PRESETS[self.category].evaluator_emphasis

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "candidates": list(self.candidates) if self.candidates else None,
            "category": self.category,
            "data_sensitivity": self.data_sensitivity,
        }


def task_from_dict(raw: Mapping[str, Any]) -> Task:
    problems = []
    for key in ("id", "question"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            problems.append(f"'{key}' must be a non-empty string")
    candidates = raw.get("candidates")
    if candidates is not None:
        if not isinstance(candidates, list) or len(candidates) < 2 or not all(isinstance(c, str) and c.strip() for c in candidates):
            problems.append("'candidates' must be a list of at least 2 non-empty strings, or left out")
        elif len({" ".join(c.split()).casefold() for c in candidates}) != len(candidates):
            problems.append("'candidates' lists the same item twice (case and spaces are ignored)")
    category = raw.get("category", "biomedical")
    if category not in CATEGORY_PRESETS:
        problems.append(f"'category' must be one of {sorted(CATEGORY_PRESETS)}")
    if raw.get("data_sensitivity") not in SENSITIVITY:
        problems.append("'data_sensitivity' must be 'public' or 'private'")
    if problems:
        raise ConfigError("task: " + "; ".join(problems))
    return Task(
        id=raw["id"].strip(),
        question=raw["question"].strip(),
        candidates=tuple(" ".join(c.split()) for c in candidates) if candidates else None,
        category=category,
        data_sensitivity=raw["data_sensitivity"],
    )


def load_task(path: str | Path) -> Task:
    return task_from_dict(_read_json(path))


@dataclass(frozen=True)
class Member:
    name: str
    backend: str
    model: str
    effort: str | None = None
    base_url: str | None = None
    family: str | None = None
    # An http member's key file, outside the repo (Ollama cloud); local vLLM servers need none.
    api_key_file: str | None = None

    @property
    def family_name(self) -> str:
        return self.family or FAMILIES[self.backend]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def member_from_dict(raw: Mapping[str, Any], where: str) -> Member:
    problems = []
    for key in ("name", "backend", "model"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            problems.append(f"'{key}' is required")
    backend = raw.get("backend")
    if backend not in BACKEND_KINDS:
        problems.append(f"'backend' must be one of {list(BACKEND_KINDS)}")
    if backend == "http":
        if not raw.get("base_url"):
            problems.append("an http member needs 'base_url'")
        if not raw.get("family"):
            problems.append("an http member needs 'family' (the company that made the model)")
    if problems:
        raise ConfigError(f"{where}: " + "; ".join(problems))
    return Member(raw["name"], backend, raw["model"], raw.get("effort"), raw.get("base_url"), raw.get("family"), raw.get("api_key_file"))


@dataclass(frozen=True)
class JevSettings:
    version: str
    api_key_env: str = "JEV_API_KEY"
    base_url: str = "https://api.typesafe.ai/v1"
    # A file outside the repo that holds only the key; the program reads it, nothing prints it.
    api_key_file: str | None = None


@dataclass(frozen=True)
class Setup:
    panel: tuple[Member, ...]
    jev: JevSettings | None = None
    local_checkers: Mapping[str, Member] = field(default_factory=dict)
    checker_for: Mapping[str, str] = field(default_factory=dict)
    concurrency: int = 2

    def to_dict(self) -> dict[str, Any]:
        checkers: dict[str, Any] = {
            name: {k: v for k, v in member.to_dict().items() if k != "name"} for name, member in self.local_checkers.items()
        }
        if self.jev is not None:
            checkers["jev"] = asdict(self.jev)
        return {
            "panel": [m.to_dict() for m in self.panel],
            "checkers": checkers,
            "checker_for": dict(self.checker_for),
            "concurrency_per_backend": self.concurrency,
        }


def setup_from_dict(raw: Mapping[str, Any]) -> Setup:
    panel_raw = raw.get("panel")
    if not isinstance(panel_raw, list) or not panel_raw:
        raise ConfigError("setup: 'panel' must be a non-empty list")
    panel = tuple(member_from_dict(m, f"panel[{i}]") for i, m in enumerate(panel_raw))
    names = [m.name for m in panel]
    if len(set(names)) != len(names):
        raise ConfigError("setup: panel names must be unique")
    jev, local = None, {}
    for key, value in (raw.get("checkers") or {}).items():
        if key == "jev":
            if not isinstance(value, Mapping) or not value.get("version"):
                raise ConfigError("setup: checkers.jev needs a pinned 'version'")
            jev = JevSettings(value["version"], value.get("api_key_env", "JEV_API_KEY"), value.get("base_url", "https://api.typesafe.ai/v1"),
                              value.get("api_key_file"))
        else:
            local[key] = member_from_dict({**value, "name": key}, f"checkers.{key}")
    checker_for = dict(raw.get("checker_for") or {})
    for sensitivity, choice in checker_for.items():
        if sensitivity not in SENSITIVITY:
            raise ConfigError(f"setup: checker_for key {sensitivity!r} must be 'public' or 'private'")
        if choice == "jev" and jev is None:
            raise ConfigError(f"setup: checker_for.{sensitivity} is jev, but 'checkers' has no jev entry")
        if choice != "jev" and choice not in local:
            raise ConfigError(f"setup: checker_for.{sensitivity} names {choice!r}, which is not under 'checkers'")
    if checker_for.get("private") == "jev":
        raise ConfigError("setup: jev is an outside service and must not check private data")
    return Setup(panel, jev, local, checker_for, int(raw.get("concurrency_per_backend", 2)))


def load_setup(path: str | Path) -> Setup:
    return setup_from_dict(_read_json(path))


@dataclass(frozen=True)
class RunOptions:
    mode: str = "experiment"
    judges: str = "recuse"
    context: str = "isolated"
    generations: int = 3
    seed: int = 0
    replay_from: str | None = None
    gen0_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def member_api_key(member: Member) -> str:
    """The key for an http member: read from its key file, or a placeholder when it has none."""
    if not member.api_key_file:
        return "EMPTY"
    key = read_key_file(member.api_key_file)
    if not key:
        raise BackendError(f"no API key in {member.api_key_file}")
    return key


def build_backend(member: Member, concurrency: int) -> ModelBackend:
    """The backend for a panel member. Retries stay at 0: CallRecorder retries once itself."""
    if member.backend == "claude":
        return ClaudeCLIBackend(name=member.name, max_concurrency=concurrency, retries=0)
    if member.backend == "codex":
        return CodexCLIBackend(name=member.name, max_concurrency=concurrency, retries=0)
    if member.backend == "grok":
        return GrokCLIBackend(name=member.name, max_concurrency=concurrency, retries=0)
    return HttpBackend(name=member.name, base_url=member.base_url, max_concurrency=concurrency, retries=0,
                       api_key=member_api_key(member))


def http_model_lister(member: Member) -> list[str]:
    return HttpBackend(member.name, member.base_url, api_key=member_api_key(member)).served_models()


def verify_http_members(members: Sequence[Member], list_models: Callable[[Member], list[str]]) -> list[str]:
    """Problems with model servers: no key, unreachable, or not serving the configured model."""
    problems = []
    for member in members:
        if member.backend != "http":
            continue
        try:
            served = list_models(member)
        except BackendError as exc:
            problems.append(f"{member.name}: {exc}")
            continue
        if member.model not in served:
            problems.append(f"{member.name}: {member.base_url} serves {served}, not {member.model}")
    return problems
