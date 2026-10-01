#!/usr/bin/env python3
"""Build the repoDB dev gold set (gold design 4).

    python scripts/build_repodb_dev.py candidates   # gold/repodb-dev/candidates.json and trials.json
    (Claude writes gold/repodb-dev/curation.json by the rules in gold design 4.5)
    python scripts/build_repodb_dev.py build        # tasks/repodb-dev/*.json and gold/repodb-dev/gold.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.gold import build, repodb, trials  # noqa: E402


def cmd_candidates(args: argparse.Namespace) -> int:
    rows = repodb.load_rows(cache=args.cache)
    base = repodb.candidates(rows, min_failed=1)
    extra = {}
    for entry in base:
        print(f"searching ClinicalTrials.gov: {entry['indication']}", flush=True)
        try:
            extra[entry["ind_id"]] = repodb.searched_failures(rows, entry["ind_id"], trials.search(entry["indication"]))
        except trials.SearchError as exc:
            print(f"{exc}; run the candidates step again", file=sys.stderr)
            return 1
    pool = repodb.candidates(rows, extra=extra)
    args.gold_dir.mkdir(parents=True, exist_ok=True)
    (args.gold_dir / "candidates.json").write_text(json.dumps(pool, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    records = trials.fetch_trials([f["nct"] for c in pool for f in c["failed"]], args.gold_dir / "trials.json")
    missing = sorted(nct for nct, record in records.items() if "error" in record)
    searched = sum(f["source"] == "ctgov" for c in pool for f in c["failed"])
    print(f"{len(base)} indications searched; {len(pool)} candidate indications ({searched} failed pairs from the search), "
          f"{len(records)} trial records"
          + (f"; not fetched: {', '.join(missing)}" if missing else ""))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    pool = json.loads((args.gold_dir / "candidates.json").read_text(encoding="utf-8"))
    curation = json.loads((args.gold_dir / "curation.json").read_text(encoding="utf-8"))
    try:
        written = build.build(curation, pool, args.tasks_dir, args.gold_dir / "gold.json")
    except build.CurationError as exc:
        print(f"curation.json breaks the rules: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_dir}; gold file {args.gold_dir / 'gold.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["candidates", "build"])
    parser.add_argument("--cache", type=Path, default=repodb.CACHE, help="where the repoDB file is kept (outside the repo)")
    parser.add_argument("--gold-dir", type=Path, default=ROOT / "gold" / "repodb-dev")
    parser.add_argument("--tasks-dir", type=Path, default=ROOT / "tasks" / "repodb-dev")
    args = parser.parse_args(argv)
    return {"candidates": cmd_candidates, "build": cmd_build}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
