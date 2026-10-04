"""Scoring answers against the gold file, and the level-1 and level-2 summaries (gold design 5.4, 6)."""

import json

import pytest

from reasonlineage.diagnose.gold import (author_judge, borda, change_verdict, correctness, format_analysis,
                                         level1, level2, score_run, summarize)

TRUTH = {"approved": ["A"], "failed": ["B", "C"]}
GOLD = {"tasks": {f"t{i}": TRUTH for i in range(1, 6)}}
DIMS = ["evidenceCoverage", "specificity", "novelty", "actionability"]
PANEL = ["opus", "gpt", "grok", "glm"]


def answer(cid, generation, author, ranking, fitness, operator=None):
    """One answer, judged by the three other panel models at its own fitness."""
    return {"id": cid, "generation": generation, "author": author, "ranking": ranking, "fitness": fitness,
            "operator": operator or ("seed" if generation == 0 else "mutation"),
            "judges": {j: fitness for j in PANEL if j != author}}


def write_run(root, name, task_id, answers, *, finished=True, candidates=("A", "B", "C"), final=None):
    run = root / name
    run.mkdir(parents=True)
    task = {"id": task_id, "question": "Q?", "candidates": list(candidates), "category": "biomedical", "data_sensitivity": "public"}
    (run / "header.json").write_text(json.dumps({"task": task}))
    lines = []
    for a in answers:
        ranking = [{"item": i, "promisingness": 0.5, "confidence": 0.5, "pmids": []} for i in a["ranking"]]
        lines.append({"event": "candidate.created", "id": a["id"], "author": a["author"], "operator": a["operator"], "parents": [],
                      "generation": a["generation"], "versions": [], "answer": {"answer": "x", "ranking": ranking}})
        for judge, value in a["judges"].items():
            lines.append({"event": "judge.scored", "candidate": a["id"], "judge": judge, "author": a["author"],
                          "generation": a["generation"], "scores": {d: value for d in DIMS}, "critique": ["x"]})
        lines.append({"event": "candidate.scored", "candidate": a["id"], "judges": list(a["judges"]), "scores": {}, "fitness": a["fitness"]})
    (run / "events.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    if finished:
        population = final or [a["id"] for a in answers]
        (run / "result.json").write_text(json.dumps({"population": [{"id": i} for i in population]}))
    return run


def aligned(fitness=(0.8, 0.6, 0.4, 0.3)):
    """Generation 0 where the approved drug A sits 1st, 2nd, 3rd, 3rd: correctness 1, 0.5, 0, 0."""
    rankings = [["A", "B", "C"], ["B", "A", "C"], ["B", "C", "A"], ["C", "B", "A"]]
    return [answer(f"c00{i + 1}", 0, author, rankings[i], fitness[i]) for i, author in enumerate(PANEL)]


def scored(tmp_path, runs):
    return [score_run(write_run(tmp_path, f"run{i}", f"t{i}", answers), GOLD) for i, answers in enumerate(runs, 1)]


@pytest.mark.parametrize("ranking, value", [(["A", "B", "C"], 1.0), (["B", "A", "C"], 0.5), (["C", "B", "A"], 0.0), (["B", "C"], None)])
def test_correctness_is_the_share_of_failed_drugs_ranked_below_the_approved_one(ranking, value):
    assert correctness(ranking, TRUTH) == value


def test_score_run_scores_every_answer_and_writes_gold_jsonl(tmp_path):
    run = write_run(tmp_path, "run1", "t1", aligned())
    result = score_run(run, GOLD)
    assert result["status"] == "scored" and result["task"] == "t1"
    assert [a["correctness"] for a in result["answers"]] == [1.0, 0.5, 0.0, 0.0]
    assert result["answers"][0]["judges"] == {"gpt": 0.8, "grok": 0.8, "glm": 0.8}
    lines = (run / "diagnostics" / "gold.jsonl").read_text().splitlines()
    assert len(lines) == 4 and json.loads(lines[1])["correctness"] == 0.5


def test_level1_finds_a_signal_when_fitness_follows_correctness(tmp_path):
    report = level1(scored(tmp_path, [aligned(), aligned(), aligned()]))
    assert (report["answers"], report["pairs"], report["concordance"]) == (12, 15, 1.0)
    assert report["share_correct"] == 0.25 and report["verdict"] == "signal"
    assert report["sign_test_p"] == pytest.approx(1 / 2 ** 15)
    assert report["by_model"] == {"opus": 1.0, "gpt": 0.5, "grok": 0.0, "glm": 0.0}


def test_level1_finds_no_signal_when_fitness_runs_the_other_way(tmp_path):
    backwards = (0.3, 0.4, 0.6, 0.8)
    report = level1(scored(tmp_path, [aligned(backwards)] * 3))
    assert report["concordance"] == 0.0 and report["verdict"] == "no signal"


def test_level1_holds_at_the_ceiling(tmp_path):
    easy = [answer(f"c00{i + 1}", 0, a, ["A", "B", "C"], 0.5 + i / 10) for i, a in enumerate(PANEL)]
    one_wrong = easy[:3] + [answer("c004", 0, "glm", ["B", "A", "C"], 0.9)]
    report = level1(scored(tmp_path, [easy, easy, one_wrong]))
    assert report["share_correct"] == 11 / 12 and report["verdict"] == "hold: ceiling"


def test_level1_holds_with_too_few_pairs(tmp_path):
    report = level1(scored(tmp_path, [aligned()]))
    assert report["pairs"] == 5 and report["verdict"] == "hold: too few pairs"


def test_equal_fitness_counts_as_half_agreement(tmp_path):
    tie = [answer("c001", 0, "opus", ["A", "B", "C"], 0.5), answer("c002", 0, "gpt", ["C", "B", "A"], 0.5)]
    report = level1(scored(tmp_path, [tie]))
    assert (report["pairs"], report["concordance"], report["sign_test_p"]) == (1, 0.5, None)


def test_judge_agreement_uses_only_pairs_the_judge_scored_both(tmp_path):
    report = level1(scored(tmp_path, [aligned()]))
    # opus wrote c001, so it judged only c002-c004: the pairs (0.5, 0) and (0.5, 0) differ in correctness.
    assert report["by_judge"]["opus"] == {"pairs": 2, "concordance": 1.0}
    assert report["by_judge"]["glm"] == {"pairs": 3, "concordance": 1.0}


def test_answers_that_leave_out_a_gold_drug_are_counted_but_not_scored(tmp_path):
    answers = aligned()
    answers[3] = answer("c004", 0, "glm", ["C", "B"], 0.3)
    report = level1(scored(tmp_path, [answers]))
    assert report["answers"] == 3 and report["unscorable"] == 1


def test_borda_adds_points_and_breaks_ties_by_candidate_order():
    assert borda([["A", "B", "C"], ["B", "A", "C"]], ["C", "B", "A"]) == ["B", "A", "C"]
    assert borda([["A", "B", "C"], ["C", "B", "A"]], ["C", "B", "A"]) == ["C", "B", "A"]


def test_level2_compares_the_best_answers_the_vote_and_each_generation(tmp_path):
    later = [answer("c005", 1, "opus", ["C", "A", "B"], 0.9), answer("c006", 1, "grok", ["A", "B", "C"], 0.7)]
    run = write_run(tmp_path, "run1", "t1", aligned() + later, final=["c005", "c001", "c006", "c002"])
    report = level2([score_run(run, GOLD)])
    (task,) = report["per_task"]
    # Borda over generation 0: B 6 points, A 3, C 3; the A-C tie keeps candidate order, so the vote is B > A > C.
    assert (task["gen0_best"], task["final_best"], task["gen0_vote"]) == (1.0, 0.5, 0.5)
    assert task["by_model"] == {"opus": 1.0, "gpt": 0.5, "grok": 0.0, "glm": 0.0}
    assert report["by_generation"]["1"] == {"fitness": 0.8, "correctness": 0.75, "answers": 2}
    assert level2(scored(tmp_path / "zero", [aligned()])) is None


@pytest.mark.parametrize("diffs, verdict", [
    ([0.5] * 10 + [0.0] * 40, "gain"),        # mean exactly +0.10, p = 0.001
    ([0.5] * 9 + [0.0] * 41, "no change"),    # p is small but the mean is 0.09
    ([-0.5] * 10 + [0.0] * 40, "loss"),       # mean exactly -0.10
    ([0.5] * 5, "gain"),                      # 5 up, 0 down: p = 0.031
    ([0.5] * 4, "no change"),                 # 4 up, 0 down: p = 0.0625, a large mean is not enough
    ([1.0, 1.0, 0.0, -0.5], "no change"),     # mean 0.375 but 2 up, 1 down: p = 0.5
])
def test_change_needs_both_the_size_and_the_sign_test(diffs, verdict):
    assert change_verdict(diffs)["verdict"] == verdict


def test_tasks_without_change_dilute_the_mean_but_leave_the_sign_test():
    assert change_verdict([0.5] * 5 + [0.0] * 20) | {"rules": None} == {
        "tasks": 25, "mean": 0.1, "up": 5, "down": 0, "p_up": 0.03125, "p_down": 1.0, "verdict": "gain", "rules": None}
    assert change_verdict([0.5] * 5 + [0.0] * 21)["verdict"] == "no change"  # mean 0.0962


def test_no_tasks_means_no_change():
    assert change_verdict([]) | {"rules": None} == {
        "tasks": 0, "mean": None, "up": 0, "down": 0, "p_up": None, "p_down": None, "verdict": "no change", "rules": None}


def test_level2_reports_the_change_in_the_best_answer_and_leaves_out_unscorable_tasks(tmp_path):
    worse = [answer("c005", 1, "opus", ["C", "A", "B"], 0.9)]       # the final best is half right; generation 0's was right
    run1 = write_run(tmp_path, "run1", "t1", aligned() + worse, final=["c005", "c001", "c002", "c003"])
    blank = [answer("c005", 1, "opus", ["B", "C"], 0.9)]            # leaves out A: the final best has no correctness
    run2 = write_run(tmp_path, "run2", "t2", aligned() + blank, final=["c005", "c001", "c002", "c003"])
    report = level2([score_run(run1, GOLD), score_run(run2, GOLD)])
    assert report["change"] == {"tasks": 1, "mean": -0.5, "up": 0, "down": 1, "p_up": 1.0, "p_down": 0.5,
                                "verdict": "no change", "rules": {"gain": 0.1, "alpha": 0.05}, "left_out": 1}


def test_runs_without_gold_unfinished_changed_or_not_runs_are_reported(tmp_path):
    other = score_run(write_run(tmp_path, "a", "not-in-gold", aligned()), GOLD)
    unfinished = score_run(write_run(tmp_path, "b", "t1", aligned(), finished=False), GOLD)
    changed = score_run(write_run(tmp_path, "c", "t2", aligned(), candidates=("A", "B", "D")), GOLD)
    (tmp_path / "d").mkdir()
    empty = score_run(tmp_path / "d", GOLD)
    assert [r["status"] for r in (other, unfinished, changed, empty)] == ["no_gold", "incomplete", "mismatch", "not_a_run"]
    assert not (tmp_path / "b" / "diagnostics").exists()


def test_summarize_counts_runs_and_flags_a_task_run_twice(tmp_path):
    runs = scored(tmp_path, [aligned(), aligned()]) + [score_run(write_run(tmp_path, "zz-again", "t1", aligned()), GOLD)]
    runs.append(score_run(write_run(tmp_path, "x", "not-in-gold", aligned()), GOLD))
    report = summarize(runs)
    assert report["runs"] == {"scored": 3, "no_gold": 1} and report["duplicate_tasks"] == ["t1"]
    assert report["level1"]["answers"] == 8 and report["level1"]["set_aside"] == ["zz-again"] and report["level2"] is None


def test_level1_counts_each_task_once_and_names_the_runs_set_aside(tmp_path):
    # A replay continues a generation-0 run with the same answers; counting both would double the pairs.
    first = scored(tmp_path, [aligned(), aligned(), aligned()])
    again = [score_run(write_run(tmp_path, f"zz-again{i}", f"t{i}", aligned()), GOLD) for i in (1, 2, 3)]
    report = level1(first + again)
    assert (report["tasks"], report["answers"], report["pairs"]) == (3, 12, 15)
    assert report["set_aside"] == ["zz-again1", "zz-again2", "zz-again3"]


def test_author_judge_averages_each_judges_scores_of_each_author(tmp_path):
    runs = scored(tmp_path, [aligned(), aligned((0.6, 0.6, 0.4, 0.3))])
    table = author_judge(runs)
    assert table["opus"] == {"glm": 0.7, "gpt": 0.7, "grok": 0.7}  # judged 0.8 and 0.6; never by itself
    assert set(table) == set(PANEL)


def test_the_analysis_gives_the_verdict_the_tables_and_every_task(tmp_path):
    runs = scored(tmp_path, [aligned()] * 5)
    text = format_analysis(runs)
    assert "**Verdict: signal.**" in text and "20 answers in 5 tasks" in text
    assert "| opus | 1.00 |" in text and "| Author \\ Judge | glm | gpt | grok | opus |" in text
    assert "| opus | 0.800 | 0.800 | 0.800 | — |" in text
    assert "- **t1** (truth A): glm: C ✗ 0.300; gpt: B ½ 0.600; grok: B ✗ 0.400; opus: A ✓ 0.800" in text
