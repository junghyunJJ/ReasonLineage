"""Prompt helpers shared by the engine and the calibration scripts.

The evaluator text lives in the protocol files (protocol/prompts/judge_system.md), so it is
part of the protocol hash.
"""

from typing import Sequence

from .protocol import load_protocol


def strict_evaluator_system(dimensions: Sequence[str], emphasis: str) -> str:
    return load_protocol().render("judge_system", emphasis=emphasis, dimensions=", ".join(dimensions))


def score_schema(dimensions: Sequence[str]) -> dict:
    """JSON schema for one judge's scores plus critique."""
    return {
        "type": "object",
        "properties": {
            **{dim: {"type": "number", "minimum": 0, "maximum": 1} for dim in dimensions},
            "critique": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        },
        "required": [*dimensions, "critique"],
        "additionalProperties": False,
    }


def candidate_prompt(question: str, answer: str) -> str:
    return load_protocol().render("judge_candidate", question=question, context="", candidate=answer)
