"""Live smoke test for ClaudeCLIBackend: isolated judge calls through the local subscription.

Runs the same Strict Evaluator request `--repeats` times concurrently and reports
latency, parallel speedup, and how much the scores move between identical calls
(the judge noise floor, to compare with the 0.02 tie margin).

    python scripts/smoke_claude_cli.py --model claude-haiku-4-5-20251001 --repeats 3
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

from reasonlineage.backends import ClaudeCLIBackend, ModelRequest  # noqa: E402
from reasonlineage.core import CATEGORY_PRESETS, composite_fitness, judge_spread  # noqa: E402
from reasonlineage.prompts import score_schema, strict_evaluator_system  # noqa: E402

PRESET = CATEGORY_PRESETS["biomedical"]
DIMS = list(PRESET.weights)

SYSTEM = strict_evaluator_system(DIMS, PRESET.evaluator_emphasis)
SCHEMA = score_schema(DIMS)

CANDIDATE = """Question: Which of these approved drugs is most promising to repurpose for idiopathic pulmonary fibrosis (IPF)?
Candidates: metformin, imatinib, sildenafil.

Answer:
1. Metformin: activates AMPK, which reverses established lung fibrosis in bleomycin mouse models by restoring myofibroblast apoptosis.
2. Sildenafil: PDE5 inhibition may improve gas exchange in IPF patients with pulmonary hypertension.
3. Imatinib: inhibits PDGFR signaling, but a randomized trial in IPF showed no benefit.

Validation plan: test metformin in precision-cut lung slices from IPF explants, measuring COL1A1 and ACTA2 expression."""


async def main(model: str, repeats: int, concurrency: int, effort: str | None) -> dict:
    backend = ClaudeCLIBackend(max_concurrency=concurrency)
    req = ModelRequest(system=SYSTEM, prompt=CANDIDATE, model=model, effort=effort, json_schema=SCHEMA, timeout_s=480)

    started = time.monotonic()
    responses = await asyncio.gather(*(backend.complete(req) for _ in range(repeats)))
    wall = time.monotonic() - started

    scores = [{dim: r.data[dim] for dim in DIMS} for r in responses]
    fitness = [composite_fitness(s, PRESET.weights) for s in scores]
    durations = [r.duration_s for r in responses]
    return {
        "model": model,
        "effort": effort,
        "repeats": repeats,
        "concurrency": concurrency,
        "wall_s": round(wall, 1),
        "call_s": [round(d, 1) for d in durations],
        "parallel_speedup": round(sum(durations) / wall, 2),
        "cost_usd_each": [r.cost_usd for r in responses],
        "input_tokens_each": [r.raw.get("usage", {}).get("input_tokens") for r in responses],
        "models_used": sorted({m for r in responses for m in r.raw.get("modelUsage", {})}),
        "fitness": [round(f, 3) for f in fitness],
        "fitness_mean": round(statistics.mean(fitness), 3),
        "fitness_sd": round(statistics.stdev(fitness), 3) if repeats > 1 else 0.0,
        "fitness_range": round(max(fitness) - min(fitness), 3),
        "per_dimension_sd": {d: round(statistics.stdev([s[d] for s in scores]), 3) if repeats > 1 else 0.0 for d in DIMS},
        "per_dimension_spread": {d: round(v, 3) for d, v in judge_spread(scores, DIMS).items()},
        "first_critique": responses[0].data["critique"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--effort", default=None, help="low, medium, high, xhigh, max")
    args = parser.parse_args()

    summary = asyncio.run(main(args.model, args.repeats, args.concurrency, args.effort))
    out = Path("runs/smoke") / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"saved {out}")
