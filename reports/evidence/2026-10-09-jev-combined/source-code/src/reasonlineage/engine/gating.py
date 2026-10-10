"""The engine's side of the J1 gate.

The engine never imports the checks package: cli.py builds a gate there and passes it in,
and the engine only sees the rewrite decision.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class GateDecision:
    rewrite: bool
    reasons: tuple[str, ...] = ()


class J1Gate(Protocol):
    async def __call__(self, candidate_id: str, generation: int, author: str,
                       answer: Mapping[str, Any], attempt: int) -> GateDecision: ...
