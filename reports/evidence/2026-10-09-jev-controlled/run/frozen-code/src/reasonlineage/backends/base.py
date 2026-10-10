"""The backend interface. An API backend or a LangChain wrapper implements the same `complete`."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class BackendError(RuntimeError):
    """A model call failed after its retries (non-zero exit, timeout, error payload, bad output)."""


class ProviderRefusal(BackendError):
    """A provider safeguard declined the request; never retry automatically."""


@dataclass(frozen=True)
class ModelRequest:
    system: str
    prompt: str
    model: str
    effort: str | None = None
    # When set, the response must be a JSON object matching this schema.
    json_schema: Mapping[str, Any] | None = None
    timeout_s: float = 480.0
    # Only the HTTP backend uses these; the CLIs have no such options.
    seed: int | None = None
    max_tokens: int | None = None
    top_logprobs: int | None = None

    @property
    def prompt_sha256(self) -> str:
        """Fingerprint of exactly what the model saw, for the call log."""
        return hashlib.sha256(f"{self.system}\n\x00\n{self.prompt}".encode()).hexdigest()


@dataclass(frozen=True)
class ModelResponse:
    backend: str
    model: str
    text: str
    data: Mapping[str, Any] | None
    duration_s: float
    cost_usd: float | None
    prompt_sha256: str
    raw: Mapping[str, Any] = field(repr=False, default_factory=dict)


class ModelBackend(Protocol):
    name: str

    async def complete(self, request: ModelRequest) -> ModelResponse: ...
