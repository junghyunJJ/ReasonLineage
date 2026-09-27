"""Model backends. Every call is one isolated request: a system prompt, one user prompt, no shared context."""

from .base import BackendError, ModelBackend, ModelRequest, ModelResponse
from .claude_cli import ClaudeCLIBackend

__all__ = ["BackendError", "ClaudeCLIBackend", "ModelBackend", "ModelRequest", "ModelResponse"]
