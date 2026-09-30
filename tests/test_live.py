"""Live checks against the real servers. Not part of the default run: `python -m pytest -m live`."""

import asyncio
import os
from pathlib import Path

import pytest

from reasonlineage.backends.base import ModelRequest
from reasonlineage.backends.http import HttpBackend
from reasonlineage.cli import build_checker
from reasonlineage.checks.local import LocalLLMChecker
from reasonlineage.checks.questions import Question
from reasonlineage.engine.answer import answer_schema, normalize_answer, validate_answer
from reasonlineage.engine.config import Task, build_backend, load_setup
from reasonlineage.protocol import load_protocol

pytestmark = pytest.mark.live
SETUP = load_setup(Path(__file__).resolve().parents[1] / "configs" / "main.json")
GLM = next(m for m in SETUP.panel if m.name == "glm")
DEEPSEEK = SETUP.local_checkers["deepseek"]
CANDIDATES = ["metformin", "imatinib", "sildenafil"]


def test_glm_serves_the_configured_model_and_writes_format_b():
    backend = build_backend(GLM, 1)
    assert GLM.model in backend.served_models()
    request = ModelRequest(system="Answer as JSON.", prompt="Rank metformin, imatinib, sildenafil for IPF in two sentences.",
                           model=GLM.model, effort="low", json_schema=answer_schema(CANDIDATES), max_tokens=8000, timeout_s=600)
    data = normalize_answer(asyncio.run(backend.complete(request)).data, CANDIDATES)
    assert validate_answer(data, CANDIDATES).hard == ()


def test_deepseek_checker_answers_a_plain_question():
    checker = LocalLLMChecker(HttpBackend("deepseek", DEEPSEEK.base_url), DEEPSEEK.model, DEEPSEEK.effort)
    question = Question("color", "noul", "Does the text name a color?")
    result = asyncio.run(checker.ask("The sky was blue this morning.", [question]))
    assert result.answers["color"].value > 0.5


def test_jev_answers_as_the_pinned_version():
    checker, why = build_checker(SETUP, Task("live", "Q?", None, "biomedical", "public"), load_protocol(), os.environ)
    if checker is None:
        pytest.skip(why)
    result = asyncio.run(checker.ask("The sky was blue this morning.", [Question("color", "noul", "Does the text name a color?")]))
    assert result.model == SETUP.jev.version
    assert result.answers["color"].value > 0.5
