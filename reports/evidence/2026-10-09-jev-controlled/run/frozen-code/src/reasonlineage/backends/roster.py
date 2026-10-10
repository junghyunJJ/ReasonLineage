"""Roster entries: `name=backend:model[:effort]`, e.g. `gpt=codex:gpt-6-sol:xhigh`."""

from dataclasses import dataclass

from .base import ModelBackend
from .claude_cli import ClaudeCLIBackend
from .codex_cli import CodexCLIBackend
from .grok_cli import GrokCLIBackend

BACKENDS = {"claude": ClaudeCLIBackend, "codex": CodexCLIBackend, "grok": GrokCLIBackend}
FAMILIES = {"claude": "anthropic", "codex": "openai", "grok": "xai"}


@dataclass(frozen=True)
class RosterEntry:
    name: str
    backend: str
    model: str
    effort: str | None

    @property
    def family(self) -> str:
        return FAMILIES[self.backend]


def parse_entry(spec: str) -> RosterEntry:
    name, sep, rest = spec.partition("=")
    if not sep or not name:
        raise ValueError(f"expected name=backend:model[:effort], got {spec!r}")
    backend, model, *effort = rest.split(":")
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; expected one of {sorted(BACKENDS)}")
    if not model or len(effort) > 1:
        raise ValueError(f"expected name=backend:model[:effort], got {spec!r}")
    return RosterEntry(name, backend, model, effort[0] if effort else None)


def make_backend(entry: RosterEntry, max_concurrency: int = 2, retries: int = 1) -> ModelBackend:
    return BACKENDS[entry.backend](name=entry.name, max_concurrency=max_concurrency, retries=retries)
