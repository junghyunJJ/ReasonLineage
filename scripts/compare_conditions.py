#!/usr/bin/env python3
"""Compare one judging condition with recuse + isolated on the same generation-0 answers (weather level-3 design 3, 4).

    python scripts/compare_conditions.py CONDITION_DIR --baseline DIR [DIR ...] --gold GOLD [--out FILE]
    e.g. python scripts/compare_conditions.py runs/gold-weather-l3-self \
             --baseline runs/gold-weather-v1 runs/gold-weather-v2 --gold gold/weather-l2/gold.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.diagnose.gold import CONDITION_ALPHA, compare_conditions, score_run  # noqa: E402


def scored_runs(folder: str, gold) -> list:
    """`score_run` of every run folder inside `folder`; stops when none of them is a scored run."""
    runs = [score_run(d, gold) for d in sorted(Path(folder).glob("*/"))]
    if not any(run["status"] == "scored" for run in runs):
        sys.exit(f"no scored runs in {folder}")
    return runs


def _p(value) -> str:
    return "n/a" if value is None else f"{value:.3g}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("condition", help="folder with the condition's run folders")
    parser.add_argument("--baseline", nargs="+", required=True, help="folders with the recuse + isolated run folders")
    parser.add_argument("--gold", required=True, help="gold file")
    parser.add_argument("--out", help="also write the comparison to this JSON file")
    args = parser.parse_args(argv)
    gold = json.loads(Path(args.gold).read_text(encoding="utf-8"))
    condition = scored_runs(args.condition, gold)
    baseline = [run for folder in args.baseline for run in scored_runs(folder, gold)]
    out = compare_conditions(condition, baseline, CONDITION_ALPHA)
    mean = "n/a" if out["mean"] is None else f"{out['mean']:+.3f}"
    print(f"{args.condition} against {', '.join(args.baseline)}: {out['tasks']} paired task(s)")
    print(f"Generation-0 best, mean correctness: condition {out['mean_condition']}, baseline {out['mean_baseline']}")
    print(f"d = condition - baseline: mean {mean}, better in {out['up']} / worse in {out['down']}, "
          f"sign test p = {_p(out['p_up'])} (better) / {_p(out['p_down'])} (worse)")
    if out["unpaired"]:
        print(f"unpaired, not compared: {', '.join(out['unpaired'])}")
    if out["left_out"]:
        print(f"{out['left_out']} task(s) left out because a best answer left out a gold item")
    print(f"Verdict (alpha {out['rules']['alpha']}): {out['verdict']}")
    if args.out:
        Path(args.out).write_text(json.dumps({"condition": args.condition, "baseline": args.baseline, **out},
                                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
