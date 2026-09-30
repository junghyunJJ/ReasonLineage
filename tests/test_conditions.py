import pytest

from helpers import scored
from reasonlineage.engine.conditions import check_conditions, judge_context, judge_set
from reasonlineage.engine.config import ConfigError
from reasonlineage.engine.policies import FixedPolicies

PANEL = ["opus", "gpt", "grok", "qwen"]
FAMILY = {"opus": "anthropic", "sonnet": "anthropic", "gpt": "openai", "luna": "openai", "grok": "xai", "qwen": "alibaba"}


@pytest.mark.parametrize("axis, expected", [
    ("recuse", ["opus", "grok", "qwen"]),
    ("self", ["gpt"]),
    ("all", PANEL),
    ("other_vendor", ["opus", "grok", "qwen"]),
    ("same_family", []),
])
def test_judge_sets_for_a_gpt_answer(axis, expected):
    assert judge_set(axis, "gpt", PANEL, FAMILY) == expected


def test_same_family_needs_a_partner_for_every_author():
    with pytest.raises(ConfigError, match="same company"):
        check_conditions("same_family", "isolated", PANEL, FAMILY)
    pairs = ["opus", "sonnet", "gpt", "luna"]
    assert check_conditions("same_family", "isolated", pairs, FAMILY) == []
    assert judge_set("same_family", "opus", pairs, FAMILY) == ["sonnet"]


def test_small_panels_get_reliability_warnings():
    assert "judges its own" in check_conditions("recuse", "isolated", ["opus"], FAMILY)[0]
    assert "single judge" in check_conditions("recuse", "isolated", ["opus", "gpt"], FAMILY)[0]
    assert check_conditions("recuse", "shared_trace", PANEL, FAMILY) == []
    with pytest.raises(ConfigError, match="unknown context"):
        check_conditions("recuse", "gossip", PANEL, FAMILY)


def test_judge_context_blocks():
    assert judge_context("isolated", author_model="gpt-6.1-sol", trace="t") == ""
    assert judge_context("author_label", author_model="gpt-6.1-sol", trace="t") == "Author of this answer: gpt-6.1-sol\n\n"
    assert judge_context("shared_trace", author_model="x", trace="- c001: fitness 0.60").startswith("Current population")


def test_mutation_parent_is_the_top_survivor():
    survivors = [scored("c002", 0.7, "qwen"), scored("c001", 0.66, "opus")]
    assert FixedPolicies().mutation_parent(survivors).id == "c002"


def test_crossover_synthesizer_is_a_non_parent_and_rotates():
    survivors = [scored("c004", 0.69, "qwen"), scored("c001", 0.66, "opus")]
    policies = FixedPolicies()
    assert policies.crossover_plan(survivors, PANEL, []).synthesizer == "gpt"
    assert policies.crossover_plan(survivors, PANEL, ["gpt"]).synthesizer == "grok"
    plan = policies.crossover_plan(survivors, PANEL, [])
    assert [p.id for p in plan.parents] == ["c004", "c001"] and not plan.fallback


def test_crossover_falls_back_when_every_model_wrote_a_parent():
    survivors = [scored("c003", 0.7, "gpt"), scored("c001", 0.6, "opus")]
    plan = FixedPolicies().crossover_plan(survivors, ["opus", "gpt"], ["opus"])
    assert plan.fallback and plan.synthesizer == "gpt"


def test_recovery_author_has_the_fewest_survivors():
    survivors = [scored("c005", 0.5, "opus"), scored("c006", 0.5, "gpt")]
    assert FixedPolicies().recovery_author(survivors, PANEL) == "grok"
