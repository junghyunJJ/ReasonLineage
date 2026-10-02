#!/usr/bin/env python3
"""Build a bioRxiv result-prediction gold set (bioRxiv design 3, 4).

    python scripts/build_biorxiv.py fetch
        # the pool: ~/.cache/reasonlineage/biorxiv/pool.json, and its index gold/biorxiv/pool.json with the sha256
    python scripts/build_biorxiv.py candidates SET --per-category N [--exclude-set OTHER]
        # DeepSeek splits, rewrites and checks papers: gold/SET/candidates.json and gold/SET/review_sheet.md
    (the user reads review_sheet.md and writes gold/SET/review.json)
    python scripts/build_biorxiv.py build SET
        # tasks/SET/*.json and gold/SET/gold.json, from the saved candidates and review (no model calls)
"""

import argparse
import asyncio
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.engine.config import build_backend, load_setup  # noqa: E402
from reasonlineage.gold import biorxiv as bx  # noqa: E402

INDEX = ROOT / "gold" / "biorxiv" / "pool.json"
FULL = bx.CACHE / "pool.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        pool = bx.build_pool(args.cache)
    except bx.SourceError as exc:
        print(f"cannot read bioRxiv: {exc}", file=sys.stderr)
        return 1
    data = bx.pool_bytes(pool)
    args.full.parent.mkdir(parents=True, exist_ok=True)
    args.full.write_bytes(data)
    counts = collections.Counter(p["category"] for p in pool)
    write_json(args.index, {"api": bx.API, "window": [bx.START, bx.END], "categories": list(bx.CATEGORIES),
                            "full_pool": str(args.full), "sha256": hashlib.sha256(data).hexdigest(),
                            "counts": {c: counts[c] for c in bx.CATEGORIES},
                            "papers": [[p["doi"], p["category"], p["date"]] for p in pool]})
    print(f"{len(pool)} papers: " + ", ".join(f"{c} {counts[c]}" for c in bx.CATEGORIES))
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    gold_dir = args.gold_root / args.set
    try:
        index = read_json(args.index)
        pool = bx.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, bx.SourceError) as exc:
        print(f"cannot read the pool ({exc}); run `fetch` first", file=sys.stderr)
        return 1
    previous = read_json(gold_dir / "candidates.json")["papers"] if (gold_dir / "candidates.json").exists() else []
    exclude: set[str] = set()
    if args.exclude_set:
        exclude |= {e["doi"] for e in read_json(args.gold_root / args.exclude_set / "candidates.json")["papers"]}
    if (gold_dir / "review.json").exists():
        exclude |= {d["doi"] for d in read_json(gold_dir / "review.json").get("drop", [])}
    member = load_setup(args.config).local_checkers["deepseek"]
    try:
        found = asyncio.run(bx.candidates(args.set, pool, args.per_category, build_backend(member, 6), member,
                                          exclude=exclude, previous=previous))
    except bx.SourceError as exc:
        print(f"cannot fill {args.set}: {exc}", file=sys.stderr)
        return 1
    source = {"api": bx.API, "window": [bx.START, bx.END], "pool_sha256": index["sha256"], "writer": member.model,
              "set": args.set, "per_category": args.per_category, "exclude_set": args.exclude_set}
    write_json(gold_dir / "candidates.json", {"source": source, "papers": found})
    dropped = {d["doi"] for d in read_json(gold_dir / "review.json").get("drop", [])} if (gold_dir / "review.json").exists() else set()
    sample = bx.review_sample(found, dropped)
    (gold_dir / "review_sheet.md").write_text(bx.review_sheet(found, sample), encoding="utf-8")
    kept = sum(e["status"] == "kept" for e in found)
    print(f"{kept} kept, {len(found) - kept} dropped; review these: {', '.join(sample)}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    gold_dir = args.gold_root / args.set
    try:
        saved = read_json(gold_dir / "candidates.json")
        review = read_json(gold_dir / "review.json")
    except OSError as exc:
        print(f"cannot read the saved candidates or review ({exc}); run `candidates` and write review.json first",
              file=sys.stderr)
        return 1
    try:
        written = bx.build(args.set, saved["papers"], review, saved["source"]["per_category"], saved["source"],
                           args.tasks_root / args.set, gold_dir / "gold.json")
    except bx.ReviewError as exc:
        print(f"review.json breaks the rules: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_root / args.set}")
    return 0


def set_name(text: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", text):
        raise argparse.ArgumentTypeError("the set name takes lowercase letters, digits and single hyphens")
    return text


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--gold-root", type=Path, default=ROOT / "gold")
    parser.add_argument("--tasks-root", type=Path, default=ROOT / "tasks")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--cache", type=Path, default=bx.CACHE)
    fetch.add_argument("--full", type=Path, default=FULL)
    cand = sub.add_parser("candidates")
    cand.add_argument("set", type=set_name)
    cand.add_argument("--per-category", type=positive, required=True)
    cand.add_argument("--exclude-set", type=set_name)
    cand.add_argument("--config", type=Path, default=ROOT / "configs" / "main.json")
    build = sub.add_parser("build")
    build.add_argument("set", type=set_name)
    args = parser.parse_args(argv)
    return {"fetch": cmd_fetch, "candidates": cmd_candidates, "build": cmd_build}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
