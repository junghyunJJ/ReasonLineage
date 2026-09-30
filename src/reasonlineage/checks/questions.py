"""The J1 and J2 question sets, built from protocol.json. The same objects go to jev and to the local checker."""

from dataclasses import dataclass
from string import Template
from typing import Any, Mapping

from ..protocol import ProtocolSpec


@dataclass(frozen=True)
class Question:
    name: str
    kind: str                                   # "noul" | "choice" | "score"
    instructions: str
    choices: tuple[tuple[str, str], ...] = ()   # choice: (option name, description)
    levels: tuple[str, ...] = ()                # score: description of level 0, 1, ...

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "instructions": self.instructions,
                "choices": [list(c) for c in self.choices], "levels": list(self.levels)}

    def to_jev(self) -> dict[str, Any]:
        """The question in jev's request format (POST /v1/systemone)."""
        if self.kind == "noul":
            return {"type": "noul", "instructions": self.instructions}
        if self.kind == "choice":
            return {"type": "choice", "instructions": self.instructions, "criteria": dict(self.choices)}
        return {"type": "score", "instructions": self.instructions, "criteria": list(self.levels)}


def question_from_spec(name: str, spec: Mapping[str, Any], **values: str) -> Question:
    instructions = Template(spec["instructions"]).substitute(values)
    if spec["type"] == "choice":
        return Question(name, "choice", instructions, choices=tuple(spec["criteria"].items()))
    if spec["type"] == "score":
        return Question(name, "score", instructions, levels=tuple(spec["criteria"]))
    return Question(name, "noul", instructions)


def j1_questions(protocol: ProtocolSpec, top_item: str) -> list[Question]:
    return [question_from_spec(name, spec, top_item=top_item) for name, spec in protocol.j1["questions"].items()]


def j2_question(protocol: ProtocolSpec, name: str, **values: str) -> Question:
    return question_from_spec(name, protocol.j2["questions"][name], **values)
