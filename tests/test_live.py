"""Live checks against the real servers. Not part of the default run: `python -m pytest -m live`."""

import asyncio
import os
from pathlib import Path

import pytest

from reasonlineage.backends.base import ModelRequest
from reasonlineage.backends.http import HttpBackend
from reasonlineage.checks.jev import JevChecker
from reasonlineage.checks.local import LocalLLMChecker
from reasonlineage.checks.questions import Question
from reasonlineage.engine.answer import answer_schema, normalize_answer, validate_answer
from reasonlineage.engine.config import load_setup

pytestmark = pytest.mark.live
SETUP = load_setup(Path(__file__).resolve().parents[1] / "configs" / "main.json")
QWEN = next(m for m in SETUP.panel if m.name == "qwen")
DEEPSEEK = SETUP.local_checkers["deepseek"]
CANDIDATES = ["metformin", "imatinib", "sildenafil"]


def test_qwen_serves_the_configured_model_and_writes_format_b():
    backend = HttpBackend("qwen", QWEN.base_url)
    assert QWEN.model in backend.served_models()
    request = ModelRequest(system="Answer as JSON.", prompt="Rank metformin, imatinib, sildenafil for IPF in two sentences.",
                           model=QWEN.model, effort="low", json_schema=answer_schema(CANDIDATES), max_tokens=8000, timeout_s=600)
    data = normalize_answer(asyncio.run(backend.complete(request)).data, CANDIDATES)
    assert validate_answer(data, CANDIDATES).hard == ()


def test_qwen_repeats_itself_with_the_same_seed():
    backend = HttpBackend("qwen", QWEN.base_url)
    request = ModelRequest(system="Be brief.", prompt="Name one drug studied for IPF.", model=QWEN.model,
                           effort="low", seed=42, max_tokens=2000, timeout_s=600)
    first, second = (asyncio.run(backend.complete(request)) for _ in range(2))
    assert first.text == second.text and first.raw["reasoning"] == second.raw["reasoning"]


def test_deepseek_checker_answers_a_plain_question():
    checker = LocalLLMChecker(HttpBackend("deepseek", DEEPSEEK.base_url), DEEPSEEK.model, DEEPSEEK.effort)
    question = Question("color", "noul", "Does the text name a color?")
    result = asyncio.run(checker.ask("The sky was blue this morning.", [question]))
    assert result.answers["color"].value > 0.5


@pytest.mark.skipif(not os.environ.get("JEV_API_KEY"), reason="needs JEV_API_KEY")
def test_jev_answers_as_the_pinned_version():
    checker = JevChecker(os.environ["JEV_API_KEY"], SETUP.jev.version, data_sensitivity="public")
    result = asyncio.run(checker.ask("The sky was blue this morning.", [Question("color", "noul", "Does the text name a color?")]))
    assert result.model == SETUP.jev.version
    assert result.answers["color"].value > 0.5
