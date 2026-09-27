from reasonlineage.core import CATEGORY_PRESETS
from reasonlineage.prompts import candidate_prompt, score_schema, strict_evaluator_system

PRESET = CATEGORY_PRESETS["biomedical"]
DIMS = list(PRESET.weights)


def test_evaluator_prompt_carries_dimensions_and_emphasis():
    system = strict_evaluator_system(DIMS, PRESET.evaluator_emphasis)
    assert PRESET.evaluator_emphasis in system
    assert all(dim in system for dim in DIMS)


def test_score_schema_requires_every_dimension_and_critique():
    schema = score_schema(DIMS)
    assert schema["required"] == [*DIMS, "critique"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["evidenceCoverage"] == {"type": "number", "minimum": 0, "maximum": 1}


def test_candidate_prompt_keeps_question_and_answer_separate():
    prompt = candidate_prompt("Q?", "A.")
    assert prompt.index("Q?") < prompt.index("Candidate answer to evaluate") < prompt.index("A.")
