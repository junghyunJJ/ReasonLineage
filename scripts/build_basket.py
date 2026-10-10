#!/usr/bin/env python3
"""Build a shopping-basket gold set (basket design 3, 4).

    python scripts/build_basket.py SET --band easy|medium|hard --tasks N
    # tasks/SET/*.json, gold/SET/gold.json and gold/SET/generation.json
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

BANDS = ("easy", "medium", "hard")  # basket.BANDS; listed here so a wrong argument fails before the import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("set", help="set name, e.g. basket-calib-easy or basket-v1")
    parser.add_argument("--band", required=True, choices=BANDS, help="the difficulty band")
    parser.add_argument("--tasks", required=True, type=int, help="number of tasks")
    parser.add_argument("--tasks-dir", type=Path, help="default: tasks/SET")
    parser.add_argument("--gold-dir", type=Path, help="default: gold/SET")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.set):
        parser.error("the set name takes lowercase letters, digits and single hyphens, e.g. basket-v1")
    if args.tasks < 1:
        parser.error("--tasks must be at least 1")
    from reasonlineage.gold import basket
    tasks_dir = args.tasks_dir or ROOT / "tasks" / args.set
    gold_dir = args.gold_dir or ROOT / "gold" / args.set
    try:
        written = basket.build(args.set, args.band, args.tasks, tasks_dir, gold_dir)
    except basket.BasketError as exc:
        print(f"cannot build {args.set}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {tasks_dir}; gold.json and generation.json in {gold_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
