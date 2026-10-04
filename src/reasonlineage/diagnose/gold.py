"""Scoring every answer of a run against a gold file, and the level-1 and level-2 summaries (gold design 5.4, 6).

This reads finished run folders and the gold file; the engine never imports it.
"""

import json
from collections import Counter, defaultdict
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..engine.config import task_from_dict
from ..engine.events import read_events

# Level-1 rules, fixed before any run (gold design 6.2). Do not change them after seeing results.
CEILING = 0.8
MIN_PAIRS = 10
SIGNAL = 0.7
# Level-2 rule, fixed before the level-2 run (weather level-2 design 5.1). Do not change it after seeing results.
GAIN = 0.10
ALPHA = 0.05
_EPS = 1e-9


def correctness(ranking: Sequence[str], truth: Mapping[str, Sequence[str]]) -> float | None:
    """Share of (approved, failed) pairs in which the approved drug is ranked higher (gold design 6.1).
    None when the ranking leaves out a gold drug."""
    position = {item: i for i, item in enumerate(ranking)}
    if any(drug not in position for drug in (*truth["approved"], *truth["failed"])):
        return None
    pairs = [(a, f) for a in truth["approved"] for f in truth["failed"]]
    return sum(position[a] < position[f] for a, f in pairs) / len(pairs)


def score_run(run_dir: str | Path, gold: Mapping[str, Any]) -> dict[str, Any]:
    """Every answer of one finished run with its fitness, judge scores, and correctness.

    Writes diagnostics/gold.jsonl for a scored run. The status says why a run was not scored:
    not_a_run, no_gold, mismatch (the task's candidates differ from the gold drugs), incomplete.
    """
    run_dir = Path(run_dir)
    if not (run_dir / "header.json").is_file():
        return {"run": run_dir.name, "task": None, "status": "not_a_run"}
    task = task_from_dict(json.loads((run_dir / "header.json").read_text(encoding="utf-8"))["task"])
    truth = gold["tasks"].get(task.id)
    if truth is None:
        return {"run": run_dir.name, "task": task.id, "status": "no_gold"}
    if set(task.candidates or ()) != {*truth["approved"], *truth["failed"]}:
        return {"run": run_dir.name, "task": task.id, "status": "mismatch"}
    if not (run_dir / "result.json").is_file():
        return {"run": run_dir.name, "task": task.id, "status": "incomplete"}
    answers: dict[str, dict[str, Any]] = {}
    for event in read_events(run_dir / "events.jsonl"):
        if event["event"] == "candidate.created":
            ranking = [entry["item"] for entry in event["answer"]["ranking"]]
            answers[event["id"]] = {"id": event["id"], "generation": event["generation"], "operator": event["operator"],
                                    "author": event["author"], "ranking": ranking, "correctness": correctness(ranking, truth),
                                    "fitness": None, "judges": {}}
        elif event["event"] == "candidate.scored":
            answers[event["candidate"]]["fitness"] = event["fitness"]
        elif event["event"] == "judge.scored":
            weighted = sum(task.weights[dim] * value for dim, value in event["scores"].items())
            answers[event["candidate"]]["judges"][event["judge"]] = round(weighted, 4)
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    out = run_dir / "diagnostics" / "gold.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in answers.values()), encoding="utf-8")
    return {"run": run_dir.name, "task": task.id, "status": "scored", "answers": list(answers.values()),
            "final": [member["id"] for member in result["population"]], "candidates": list(task.candidates), "truth": truth}


def _concordance(groups: Sequence[Sequence[Mapping[str, Any]]], value: Callable[[Mapping[str, Any]], float | None]):
    """(agreement, pairs, concordant, discordant) over same-group answer pairs with different correctness.
    A pair where `value` is missing for either answer is left out; equal values count as half agreement."""
    agree, pairs, concordant, discordant = 0.0, 0, 0, 0
    for group in groups:
        for x, y in combinations(group, 2):
            if x["correctness"] == y["correctness"]:
                continue
            high, low = (x, y) if x["correctness"] > y["correctness"] else (y, x)
            v_high, v_low = value(high), value(low)
            if v_high is None or v_low is None:
                continue
            pairs += 1
            if v_high > v_low:
                agree, concordant = agree + 1, concordant + 1
            elif v_high < v_low:
                discordant += 1
            else:
                agree += 0.5
    return agree, pairs, concordant, discordant


def sign_test(concordant: int, discordant: int) -> float | None:
    """One-sided exact binomial p-value for at least `concordant` agreements out of the untied pairs."""
    n = concordant + discordant
    if n == 0:
        return None
    return sum(comb(n, k) for k in range(concordant, n + 1)) / 2 ** n


def _counted(runs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The run each task counts with: its earliest run folder by name (gold design 6.2)."""
    kept: dict[str, Mapping[str, Any]] = {}
    for run in sorted(runs, key=lambda r: r["run"]):
        kept.setdefault(run["task"], run)
    return list(kept.values())


def level1(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Does generation-0 fitness follow correctness? The verdict follows gold design 6.2 in order.

    Each task counts once (gold design 6.2: its four generation-0 answers). When a task has several runs,
    for example a replay that continues it, the earliest run folder by name counts; the rest are set aside.
    """
    counted = _counted(runs)
    set_aside = sorted(run["run"] for run in runs if run not in counted)
    runs = counted
    groups = [[a for a in run["answers"] if a["generation"] == 0 and a["correctness"] is not None] for run in runs]
    answers = [a for group in groups for a in group]
    unscorable = sum(1 for run in runs for a in run["answers"] if a["generation"] == 0 and a["correctness"] is None)
    share = sum(a["correctness"] == 1 for a in answers) / len(answers) if answers else 0.0
    agree, pairs, concordant, discordant = _concordance(groups, lambda a: a["fitness"])
    rate = agree / pairs if pairs else None
    if answers and share >= CEILING - _EPS:
        verdict = "hold: ceiling"
    elif pairs < MIN_PAIRS:
        verdict = "hold: too few pairs"
    elif rate >= SIGNAL - _EPS:
        verdict = "signal"
    else:
        verdict = "no signal"
    by_judge = {}
    for judge in sorted({j for a in answers for j in a["judges"]}):
        j_agree, j_pairs, _, _ = _concordance(groups, lambda a, j=judge: a["judges"].get(j))
        by_judge[judge] = {"pairs": j_pairs, "concordance": j_agree / j_pairs if j_pairs else None}
    authors: dict[str, list[float]] = defaultdict(list)
    for a in answers:
        authors[a["author"]].append(a["correctness"])
    return {"tasks": len(runs), "answers": len(answers), "unscorable": unscorable, "share_correct": share,
            "pairs": pairs, "concordance": rate, "verdict": verdict, "sign_test_p": sign_test(concordant, discordant),
            "by_judge": by_judge, "by_model": {m: sum(v) / len(v) for m, v in authors.items()},
            "set_aside": set_aside, "rules": {"ceiling": CEILING, "min_pairs": MIN_PAIRS, "signal": SIGNAL}}


def borda(rankings: Sequence[Sequence[str]], candidates: Sequence[str]) -> list[str]:
    """One combined ranking: n-1 points for 1st down to 0 for last; ties keep the candidates' order."""
    points = {c: 0 for c in candidates}
    for ranking in rankings:
        for i, item in enumerate(ranking):
            if item in points:
                points[item] += len(ranking) - 1 - i
    return sorted(candidates, key=lambda c: -points[c])


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def level2(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Does evolution raise correctness? Comparisons only (gold design 6.3); None when no run evolved."""
    evolved = [run for run in runs if any(a["generation"] >= 1 for a in run["answers"])]
    if not evolved:
        return None
    per_task, generations = [], defaultdict(lambda: {"fitness": [], "correctness": []})
    for run in evolved:
        by_id = {a["id"]: a for a in run["answers"]}
        first = [a for a in run["answers"] if a["generation"] == 0]
        best_first = max(first, key=lambda a: a["fitness"])  # ties go to the earlier answer
        best_final = max((by_id[i] for i in run["final"]), key=lambda a: a["fitness"])
        vote = borda([a["ranking"] for a in first], run["candidates"])
        per_task.append({"task": run["task"], "gen0_best": best_first["correctness"], "final_best": best_final["correctness"],
                         "gen0_vote": correctness(vote, run["truth"]), "by_model": {a["author"]: a["correctness"] for a in first}})
        for a in run["answers"]:
            if a["correctness"] is not None:
                generations[a["generation"]]["fitness"].append(a["fitness"])
                generations[a["generation"]]["correctness"].append(a["correctness"])
    means = {key: _mean([t[key] for t in per_task if t[key] is not None]) for key in ("gen0_best", "final_best", "gen0_vote")}
    diffs = [t["final_best"] - t["gen0_best"] for t in per_task if t["final_best"] is not None and t["gen0_best"] is not None]
    return {"tasks": len(evolved), "per_task": per_task, "mean": means,
            "by_generation": {str(g): {"fitness": _mean(v["fitness"]), "correctness": _mean(v["correctness"]),
                                       "answers": len(v["fitness"])} for g, v in sorted(generations.items())},
            "change": change_verdict(diffs) | {"left_out": len(per_task) - len(diffs)}}


def change_verdict(diffs: Sequence[float]) -> dict[str, Any]:
    """Did evolution change the best answer's correctness? d = final best minus generation-0 best, one per task.

    Gain or loss needs both a mean change of at least GAIN and a one-sided sign test below ALPHA (weather level-2
    design 5.1); tasks where d is 0 leave the sign test.
    """
    up = sum(d > _EPS for d in diffs)
    down = sum(d < -_EPS for d in diffs)
    mean = _mean(list(diffs))
    p_up, p_down = sign_test(up, down), sign_test(down, up)
    if mean is not None and mean >= GAIN - _EPS and p_up is not None and p_up < ALPHA:
        verdict = "gain"
    elif mean is not None and mean <= -GAIN + _EPS and p_down is not None and p_down < ALPHA:
        verdict = "loss"
    else:
        verdict = "no change"
    return {"tasks": len(diffs), "mean": mean, "up": up, "down": down, "p_up": p_up, "p_down": p_down,
            "verdict": verdict, "rules": {"gain": GAIN, "alpha": ALPHA}}


def summarize(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [run for run in runs if run["status"] == "scored"]
    tasks = Counter(run["task"] for run in scored)
    return {"runs": dict(Counter(run["status"] for run in runs)),
            "duplicate_tasks": sorted(t for t, n in tasks.items() if n > 1),
            "level1": level1(scored) if scored else None, "level2": level2(scored)}


def format_report(report: Mapping[str, Any]) -> str:
    """The summary as a few readable lines."""
    lines = ["Runs: " + ", ".join(f"{n} {status}" for status, n in sorted(report["runs"].items()))]
    if report["duplicate_tasks"]:
        lines.append("warning: tasks with more than one run: " + ", ".join(report["duplicate_tasks"]))
    one = report["level1"]
    if one:
        rate = "n/a" if one["concordance"] is None else f"{one['concordance']:.2f}"
        lines.append(f"Level 1 (generation 0): {one['answers']} answers, {one['share_correct']:.0%} fully correct, "
                     f"{one['pairs']} pairs with different correctness, concordance {rate} -> {one['verdict']}")
        if one["set_aside"]:
            lines.append("  one run per task counts; set aside: " + ", ".join(one["set_aside"]))
        if one["unscorable"]:
            lines.append(f"  {one['unscorable']} answer(s) left out a gold drug and were not scored")
        if one["sign_test_p"] is not None:
            lines.append(f"  sign test p = {one['sign_test_p']:.3g}")
        lines.append("  by judge: " + ", ".join(f"{j} {v['concordance']:.2f} ({v['pairs']} pairs)"
                                             for j, v in one["by_judge"].items() if v["concordance"] is not None))
        lines.append("  correctness by model: " + ", ".join(f"{m} {v:.2f}" for m, v in one["by_model"].items()))
    two = report["level2"]
    if two:
        mean = two["mean"]
        lines.append(f"Level 2 ({two['tasks']} evolved runs): mean correctness gen-0 best {mean['gen0_best']}, "
                     f"final best {mean['final_best']}, gen-0 vote {mean['gen0_vote']}")
        lines.append("  by generation: " + ", ".join(f"{g}: fitness {v['fitness']} correctness {v['correctness']}"
                                                  for g, v in two["by_generation"].items()))
        lines.append(f"  change in the best answer (final - generation 0): {_change_summary(two['change'])} "
                     f"-> {two['change']['verdict']}")
    return "\n".join(lines)


def _p(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3g}"


def _change_summary(change: Mapping[str, Any]) -> str:
    mean = "n/a" if change["mean"] is None else f"{change['mean']:+.3f}"
    left = f"; {change['left_out']} task(s) left out because an answer left out a gold item" if change["left_out"] else ""
    return (f"mean {mean} over {change['tasks']} task(s), {change['up']} up / {change['down']} down, "
            f"sign test p = {_p(change['p_up'])} (up) / {_p(change['p_down'])} (down){left}")


def author_judge(runs: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """The mean weighted score each judge gave each author's generation-0 answers, over the runs level 1 counts."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for run in _counted(runs):
        for answer in run["answers"]:
            if answer["generation"] == 0:
                for judge, score in answer["judges"].items():
                    cells[(answer["author"], judge)].append(score)
    table: dict[str, dict[str, float]] = defaultdict(dict)
    for (author, judge), values in sorted(cells.items()):
        table[author][judge] = sum(values) / len(values)
    return dict(table)


_MARK = {1.0: "✓", 0.5: "½", 0.0: "✗"}


def format_analysis(runs: Sequence[Mapping[str, Any]]) -> str:
    """Level 1 as a Markdown report: the verdict, correctness by author, concordance by judge, the judge-by-author
    score table and every task's generation-0 answers. `runs` are scored runs (`score_run`)."""
    one = level1(runs)
    rate = "n/a" if one["concordance"] is None else f"{one['concordance']:.2f}"
    p = "" if one["sign_test_p"] is None else f", sign test p = {one['sign_test_p']:.3g}"
    rules = one["rules"]
    lines = ["# Level 1 analysis", "",
             f"**Verdict: {one['verdict']}.** {one['answers']} answers in {one['tasks']} tasks: "
             f"{one['share_correct']:.0%} fully correct, {one['pairs']} pairs with different correctness, "
             f"concordance {rate}{p}.",
             f"Rules fixed before the run: ceiling {rules['ceiling']:.0%}, at least {rules['min_pairs']} pairs, "
             f"signal at concordance {rules['signal']:.2f}.", "",
             "## Correctness by author", "", "| Author | Mean correctness |", "|---|---|"]
    lines += [f"| {m} | {v:.2f} |" for m, v in one["by_model"].items()]
    lines += ["", "## Concordance by judge", "", "| Judge | Pairs | Concordance |", "|---|---|---|"]
    lines += [f"| {j} | {v['pairs']} | {'n/a' if v['concordance'] is None else format(v['concordance'], '.2f')} |"
              for j, v in one["by_judge"].items()]
    table = author_judge(runs)
    judges = sorted({j for row in table.values() for j in row})
    lines += ["", "## Mean judge score by author", "",
              "Rows: the answer's author. Columns: the judge. Generation 0, weighted rubric score; "
              "\"—\" where the judge did not score that author (recusal).", "",
              "| Author \\ Judge | " + " | ".join(judges) + " |", "|---|" + "---|" * len(judges)]
    lines += [f"| {a} | " + " | ".join(f"{row[j]:.3f}" if j in row else "—" for j in judges) + " |"
              for a, row in table.items()]
    two = level2(runs)
    if two:
        change, mean = two["change"], two["mean"]
        rules = change["rules"]
        lines += ["", "## Level 2 (evolution)", "",
                  f"**Verdict: {change['verdict']}.** Change in the best answer (final - generation 0): "
                  f"{_change_summary(change)}.",
                  f"Rule fixed before the run: gain or loss needs a mean change of at least {rules['gain']:.2f} and a "
                  f"one-sided sign test p below {rules['alpha']:.2f}.",
                  f"Mean correctness: generation-0 best {mean['gen0_best']}, final best {mean['final_best']}, "
                  f"generation-0 vote {mean['gen0_vote']}.", "",
                  "| Generation | Answers | Mean fitness | Mean correctness |", "|---|---|---|---|"]
        lines += [f"| {g} | {v['answers']} | {v['fitness']} | {v['correctness']} |" for g, v in two["by_generation"].items()]
    lines += ["", "## Tasks", "", "Each cell: the author's top pick, its correctness (✓ 1, ½ 0.5, ✗ 0) and the "
              "answer's fitness.", ""]
    for run in sorted(_counted(runs), key=lambda r: r["task"]):
        cells = [f"{a['author']}: {a['ranking'][0] if a['ranking'] else '-'} "
                 f"{_MARK.get(a['correctness'], '?')} {a['fitness'] if a['fitness'] is None else format(a['fitness'], '.3f')}"
                 for a in sorted(run["answers"], key=lambda a: a["author"]) if a["generation"] == 0]
        lines.append(f"- **{run['task']}** (truth {', '.join(run['truth']['approved'])}): " + "; ".join(cells))
    return "\n".join(lines) + "\n"
