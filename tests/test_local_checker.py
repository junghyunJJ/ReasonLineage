"""Reading probabilities from the final answer token of a local model."""

import asyncio
import math

import pytest

from reasonlineage.backends.base import BackendError, ModelResponse
from reasonlineage.checks.base import CheckerError
from reasonlineage.checks.local import LocalLLMChecker, options_for, prompt_for, read_probabilities
from reasonlineage.checks.questions import j1_questions
from reasonlineage.protocol import load_protocol

QUESTIONS = j1_questions(load_protocol(), "metformin")


def tok(token, p, alts=()):
    return {"token": token, "logprob": math.log(p), "top_logprobs": [{"token": t, "logprob": math.log(q)} for t, q in alts]}


def test_the_last_option_token_is_the_answer_not_one_inside_the_reasoning():
    tokens = [tok("yes", 0.9), tok(" the", 0.5), tok("A", 0.8), tok(" no", 0.7, [(" no", 0.7), (" yes", 0.3)])]
    probs = read_probabilities(tokens, ["yes", "no"])
    assert probs == pytest.approx({"yes": 0.3, "no": 0.7})


def test_the_chosen_token_counts_even_when_missing_from_the_top_list():
    probs = read_probabilities([tok("B", 0.6, [("A", 0.2)])], ["A", "B"])
    assert probs == pytest.approx({"A": 0.25, "B": 0.75})


def test_no_option_token_is_an_error():
    with pytest.raises(CheckerError, match="no answer token"):
        read_probabilities([tok("maybe", 0.9)], ["yes", "no"])


def test_prompts_list_the_options():
    choice, noul, score = QUESTIONS
    assert options_for(choice) == ["A", "B", "C", "D"]
    assert "A) answer: An answer to the question" in prompt_for("text", choice)
    assert prompt_for("text", noul).endswith("Reply with exactly one word: yes or no.")
    assert options_for(score) == ["0", "1", "2", "3"] and "3) All of the items" in prompt_for("text", score)


class Stub:
    """Answers each question with a fixed token and alternatives."""

    def __init__(self, fail=False):
        self.fail = fail
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if self.fail:
            raise BackendError("down")
        if "exactly one letter" in request.prompt:
            logprobs = [tok("A", 0.9, [("A", 0.9), ("D", 0.1)])]
        elif "yes or no" in request.prompt:
            logprobs = [tok("no", 0.8, [("no", 0.8), ("yes", 0.2)])]
        else:
            logprobs = [tok("3", 0.7, [("3", 0.7), ("2", 0.3)])]
        return ModelResponse("deepseek", request.model, "x", None, 0.1, None, "", {"logprobs": logprobs})


def test_ask_maps_letters_back_to_option_names():
    stub = Stub()
    checker = LocalLLMChecker(stub, "deepseek-ai/DeepSeek-V4-Flash-0731", "max")
    result = asyncio.run(checker.ask("state", QUESTIONS))
    assert result.answers["answer_type"].probabilities == pytest.approx({"answer": 0.9, "refusal": 0, "meta": 0, "grader": 0.1})
    assert result.answers["top_item_argument"].value == pytest.approx(0.2)
    assert result.answers["argument_coverage"].value == pytest.approx(2.7)
    assert all(r.top_logprobs == 10 and r.effort == "max" for r in stub.requests)
    assert checker.pinned_version is None


def test_backend_failures_become_checker_errors():
    with pytest.raises(CheckerError, match="down"):
        asyncio.run(LocalLLMChecker(Stub(fail=True), "m", "max").ask("state", QUESTIONS))
