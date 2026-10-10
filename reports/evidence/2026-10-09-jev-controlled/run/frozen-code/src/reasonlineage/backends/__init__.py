"""Model backends. Every call is one isolated request: a system prompt, one user prompt, no shared context."""

from .base import BackendError, ModelBackend, ModelRequest, ModelResponse
from .claude_cli import ClaudeCLIBackend
from .codex_cli import CodexCLIBackend
from .grok_cli import GrokCLIBackend
from .http import HttpBackend

__all__ = [
    "BackendError",
    "ClaudeCLIBackend",
    "CodexCLIBackend",
    "GrokCLIBackend",
    "HttpBackend",
    "ModelBackend",
    "ModelRequest",
    "ModelResponse",
]
