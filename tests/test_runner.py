"""The runner's main flow with four deterministic fake models."""

import asyncio
import json
from collections import Counter

import pytest

from fakes import events_of, make_runner

QUESTION_WITH_SYMBOLS = 'Which drug for IPF? Budget $5 {x} "quoted" — 한국어 질문'


def run(tmp_path, **kwargs):
    runner, models = make_runner(tmp_path, **kwargs)
    summary = asyncio.run(runner.run())
    return runner.run_dir, summary, models


def test_a_full_run_has_four_seeds_three_selections_and_six_offspring(tmp_path):
    run_dir, summary, _ = run(tmp_path)
    created = events_of(run_dir, "candidate.created")
    assert [c["id"] for c in created] == [f"c{i:03d}" for i in range(1, 11)]
    assert Counter(c["operator"] for c in created) == {"seed": 4, "mutation": 3, "crossover": 3}
    assert [s["generation"] for s in events_of(run_dir, "selection")] == [0, 1, 2]
    assert summary["termination"] == "generation_limit" and summary["generations"] == 3
    result = json.loads((run_dir / "result.json").read_text())
    assert result["best"]["id"] == summary["best"]["id"]
    assert events_of(run_dir, "run.completed")[0]["best"] == summary["best"]["id"]


def test_recused_judges_never_score_their_own_answer_and_score_each_answer_once(tmp_path):
    run_dir, _, _ = run(tmp_path)
    scored = events_of(run_dir, "judge.scored")
    assert all(s["judge"] != s["author"] for s in scored)
    assert set(Counter(s["candidate"] for s in scored).values()) == {3}  # survivors are not scored again
    assert all(s["judges_axis"] == "recuse" and s["context"] == "isolated" for s in scored)


def test_mutation_and_crossover_follow_the_fixed_rules(tmp_path):
    run_dir, _, _ = run(tmp_path)
    created = {c["id"]: c for c in events_of(run_dir, "candidate.created")}
    for selection in events_of(run_dir, "selection"):
        offspring = [c for c in created.values() if c["generation"] == selection["generation"] + 1]
        mutation = next(c for c in offspring if c["operator"] == "mutation")
        crossover = next(c for c in offspring if c["operator"] == "crossover")
        top = created[selection["survivors"][0]]
        assert mutation["parents"] == [top["id"]] and mutation["author"] == top["author"]
        assert crossover["parents"] == selection["survivors"]
        assert crossover["author"] not in {created[p]["author"] for p in crossover["parents"]}


def test_two_models_write_two_seeds_each_with_different_approaches(tmp_path):
    run_dir, _, models = run(tmp_path, names=("opus", "gpt"))
    seeds = [c for c in events_of(run_dir, "candidate.created") if c["operator"] == "seed"]
    assert [s["author"] for s in seeds] == ["opus", "opus", "gpt", "gpt"]
    opus_prompts = [r.prompt for r in models["opus"].seen[:2]]
    assert "Take this approach: mechanism-centered." in opus_prompts[0]
    assert "Take this approach: clinical-evidence-centered." in opus_prompts[1]
    assert events_of(run_dir, "anomaly")[0]["kind"] == "reliability"


def test_the_question_reaches_every_prompt_unchanged(tmp_path):
    _, _, models = run(tmp_path, question=QUESTION_WITH_SYMBOLS, generations=1)
    prompts = [r.prompt for m in models.values() for r in m.seen]
    assert prompts and all(QUESTION_WITH_SYMBOLS in p for p in prompts)


def test_judges_see_the_prose_with_the_final_ranking_block(tmp_path):
    _, _, models = run(tmp_path, generations=1)
    judge_prompts = [r.prompt for m in models.values() for r in m.seen if "Candidate answer to evaluate" in r.prompt]
    assert judge_prompts and all("Final ranking:" in p and "PMIDs:" in p for p in judge_prompts)
    systems = {r.system for m in models.values() for r in m.seen if "Candidate answer to evaluate" in r.prompt}
    assert len(systems) == 1 and "Dimensions: evidenceCoverage, specificity, novelty, actionability." in systems.pop()


def test_judges_see_the_rule_the_authors_had(tmp_path):
    _, _, models = run(tmp_path, generations=1)
    rule = "Rank exactly these items, each once, using these exact names: metformin, imatinib, sildenafil."
    seen = [r for m in models.values() for r in m.seen]
    judge_prompts = [r.prompt for r in seen if "Candidate answer to evaluate" in r.prompt]
    assert all(rule in r.system for r in seen if "Candidate answer to evaluate" not in r.prompt)
    assert judge_prompts and all(f"Rule the author had to follow: {rule}" in p for p in judge_prompts)


def test_exploration_stops_early_once_the_threshold_is_met(tmp_path):
    from fakes import FakeModel
    names = ("opus", "gpt", "grok", "qwen")
    run_dir, summary, _ = run(tmp_path, mode="exploration", models={n: FakeModel(n, judge_value=0.9) for n in names})
    assert summary["termination"] == "threshold_met"
    assert events_of(run_dir, "selection") == []


def test_judge_axes_and_contexts(tmp_path):
    run_dir, _, _ = run(tmp_path / "self", judges="self", generations=1)
    assert all(s["judge"] == s["author"] for s in events_of(run_dir, "judge.scored"))
    run_dir, _, _ = run(tmp_path / "all", judges="all", generations=1)
    assert set(Counter(s["candidate"] for s in events_of(run_dir, "judge.scored")).values()) == {4}
    _, _, models = run(tmp_path / "label", context="author_label", generations=1)
    judge_prompts = [r.prompt for r in models["gpt"].seen if "Candidate answer to evaluate" in r.prompt]
    assert all("Author of this answer: model-" in p for p in judge_prompts)
    _, _, models = run(tmp_path / "trace", context="shared_trace", generations=1)
    first = next(r.prompt for r in models["gpt"].seen if "Candidate answer to evaluate" in r.prompt)
    assert "Current population" in first and "not scored yet" in first


def test_invalid_run_options_fail_before_any_call(tmp_path):
    with pytest.raises(ValueError, match="generation_limit"):
        make_runner(tmp_path, generations=11)


def test_generations_zero_writes_and_judges_generation_zero_only(tmp_path):
    run_dir, summary, models = run(tmp_path, generations=0)
    assert sum(len(m.seen) for m in models.values()) == 16  # 4 answers + 12 judge calls
    assert [c["generation"] for c in events_of(run_dir, "candidate.created")] == [0, 0, 0, 0]
    assert events_of(run_dir, "selection") == []
    assert summary["termination"] == "generation_limit" and summary["generations"] == 0
