#!/usr/bin/env python3
"""Build a gold v0 set from CT Open (gold v0 design 4).

    python scripts/build_ctopen.py candidates SET   # gold/ctopen-SET/candidates.json, trials.json and review_sheet.md
    (Claude reads only review_sheet.md, which hides the answers, and writes gold/ctopen-SET/review.json by the
     rules in gold v0 design 4.3)
    python scripts/build_ctopen.py build SET        # tasks/ctopen-SET/*.json, gold.json and items/*.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.gold import ctopen, repodb, trials  # noqa: E402


def cmd_candidates(args: argparse.Namespace) -> int:
    try:
        entries = ctopen.load_set(args.set, cache=args.cache)
        rows = repodb.load_rows(cache=args.repodb_cache)
        found = ctopen.candidates(entries, ctopen.SETS[args.set]["after"], repodb.drug_namer(rows))
    except (ctopen.SourceError, repodb.SourceError) as exc:
        print(f"cannot read the sources: {exc}", file=sys.stderr)
        return 1
    args.gold_dir.mkdir(parents=True, exist_ok=True)
    records = trials.fetch_trials([c["nct"] for c in found], args.gold_dir / "trials.json")
    found = ctopen.attach(found, records)
    (args.gold_dir / "candidates.json").write_text(json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (args.gold_dir / "review_sheet.md").write_text(ctopen.review_sheet(found), encoding="utf-8")
    met = sum(c["label"] == "MET" for c in found)
    missing = sorted(c["nct"] for c in found if "fetch_error" in c)
    print(f"{len(found)} candidate trials ({met} MET, {len(found) - met} NOT MET)"
          + (f"; no ClinicalTrials.gov record: {', '.join(missing)}" if missing else ""))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    found = json.loads((args.gold_dir / "candidates.json").read_text(encoding="utf-8"))
    review = json.loads((args.gold_dir / "review.json").read_text(encoding="utf-8"))
    try:
        written = ctopen.build(found, review, args.set, args.tasks_dir, args.gold_dir / "gold.json", args.gold_dir / "items")
    except ctopen.ReviewError as exc:
        print(f"review.json breaks the rules: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_dir}; gold file {args.gold_dir / 'gold.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["candidates", "build"])
    parser.add_argument("set", choices=sorted(ctopen.SETS), help="a pinned CT Open set (gold v0 design 4.1)")
    parser.add_argument("--cache", type=Path, default=ctopen.CACHE, help="where CT Open files are kept (outside the repo)")
    parser.add_argument("--repodb-cache", type=Path, default=repodb.CACHE, help="where the repoDB file is kept")
    parser.add_argument("--gold-dir", type=Path, help="default: gold/ctopen-SET")
    parser.add_argument("--tasks-dir", type=Path, help="default: tasks/ctopen-SET")
    args = parser.parse_args(argv)
    args.gold_dir = args.gold_dir or ROOT / "gold" / f"ctopen-{args.set}"
    args.tasks_dir = args.tasks_dir or ROOT / "tasks" / f"ctopen-{args.set}"
    return {"candidates": cmd_candidates, "build": cmd_build}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
