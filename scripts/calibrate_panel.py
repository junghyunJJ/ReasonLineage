"""Author x judge calibration: every roster judge scores every candidate (its own included) in isolated calls.

    python scripts/calibrate_panel.py --candidates runs/calibration/candidates-XXXX.json --repeats 2 \
        opus=claude:claude-opus-5-5:xhigh sonnet=claude:claude-sonnet-5-5:xhigh \
        gpt=codex:gpt-6.1-sol:xhigh grok=grok:grok-4.7:xhigh

Outputs runs/calibration/panel-<timestamp>/raw.jsonl and summary.json. The summary reports
leniency, self- and family preference (raw and after per-judge z-scoring), within-judge
noise, strong-vs-weak discrimination, and how much recusal moves each author's candidates.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasonlineage.backends import BackendError, ModelRequest  # noqa: E402
from reasonlineage.backends.roster import make_backend, parse_entry  # noqa: E402
from reasonlineage.calibration import (  # noqa: E402
    cell_means,
    discrimination,
    preference_analysis,
    within_judge_noise,
    zscore_by_judge,
)
from reasonlineage.core import CATEGORY_PRESETS, composite_fitness  # noqa: E402
from reasonlineage.prompts import candidate_prompt, score_schema, strict_evaluator_system  # noqa: E402

PRESET = CATEGORY_PRESETS["biomedical"]
DIMS = list(PRESET.weights)


async def score_all(question, candidates, entries, repeats):
    system, schema = strict_evaluator_system(DIMS, PRESET.evaluator_emphasis), score_schema(DIMS)
    backends = {e.name: make_backend(e) for e in entries}

    async def one(entry, cand, repeat):
        request = ModelRequest(system=system, prompt=candidate_prompt(question, cand["text"]),
                               model=entry.model, effort=entry.effort, json_schema=schema, timeout_s=900)
        record = {"judge": entry.name, "candidate": cand["id"], "author": cand["author"], "level": cand["level"], "repeat": repeat}
        try:
            r = await backends[entry.name].complete(request)
        except BackendError as exc:
            return {**record, "error": str(exc)}
        scores = {d: r.data[d] for d in DIMS}
        return {**record, "scores": scores, "fitness": composite_fitness(scores, PRESET.weights),
                "critique": r.data["critique"], "duration_s": round(r.duration_s, 1)}

    jobs = [one(e, c, r) for r in range(repeats) for c in candidates for e in entries]
    return await asyncio.gather(*jobs)


def rounded(mapping, digits=3):
    return {k: (round(v, digits) if isinstance(v, float) else v) for k, v in mapping.items()}


def analyze(records, candidates, entries):
    ok = [r for r in records if "fitness" in r]
    cells = cell_means(ok)
    author = {c["id"]: c["author"] for c in candidates}
    family = {e.name: e.family for e in entries}
    judges = [e.name for e in entries]

    raw = preference_analysis(cells, author, family)
    z, scale = zscore_by_judge(cells)
    zres = preference_analysis(z, author, family)
    pairs = [(f"{a}-strong", f"{a}-weak") for a in judges if f"{a}-strong" in author and f"{a}-weak" in author]

    # Recusal effect on an author's own candidates: panel without the author minus panel with it.
    recusal = {}
    for a in judges:
        own = [c for c, who in author.items() if who == a]
        diffs = [
            statistics.mean(cells[c, j] for j in judges if j != a) - statistics.mean(cells[c, j] for j in judges)
            for c in own if all((c, j) in cells for j in judges)
        ]
        recusal[a] = round(statistics.mean(diffs), 3) if diffs else None

    matrix = {
        f"{a}->{j}": round(statistics.mean(cells[c, j] for c, who in author.items() if who == a and (c, j) in cells), 3)
        for a in judges for j in judges
    }
    return {
        "calls": len(records),
        "errors": [r for r in records if "error" in r],
        "author_to_judge_mean": matrix,
        "cell_mean": {f"{c}|{j}": round(v, 3) for (c, j), v in sorted(cells.items())},
        "within_judge_noise_sd": rounded(within_judge_noise(ok)),
        "leniency": rounded(raw["leniency"]),
        "self_preference": rounded(raw["self_preference"]),
        "family_preference": rounded(raw["family_preference"]),
        "foreign_residual_sd": round(raw["foreign_residual_sd"], 3),
        "zscored": {
            "note": "effects in fitness units (z effect x mean judge SD)",
            "self_preference": {j: (round(v * scale, 3) if v is not None else None) for j, v in zres["self_preference"].items()},
            "family_preference": {j: (round(v * scale, 3) if v is not None else None) for j, v in zres["family_preference"].items()},
            "foreign_residual_sd": round(zres["foreign_residual_sd"] * scale, 3),
        },
        "discrimination": {j: rounded(v) for j, v in discrimination(cells, pairs).items()},
        "recusal_shift_on_own_candidates": recusal,
        "mean_call_s": {j: round(statistics.mean(r["duration_s"] for r in ok if r["judge"] == j), 1) for j in judges},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("roster", nargs="+", help="name=backend:model[:effort]")
    args = parser.parse_args()

    data = json.loads(Path(args.candidates).read_text())
    candidates = [c for c in data["candidates"] if "error" not in c]
    entries = [parse_entry(s) for s in args.roster]

    started = time.monotonic()
    records = asyncio.run(score_all(data["question"], candidates, entries, args.repeats))
    out = Path("runs/calibration") / f"panel-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "raw.jsonl").open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {"candidates_file": args.candidates, "roster": args.roster, "repeats": args.repeats,
               "wall_s": round(time.monotonic() - started, 1), **analyze(records, candidates, entries)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "cell_mean"}, indent=2, ensure_ascii=False))
    print(f"saved {out}")
