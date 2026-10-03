#!/usr/bin/env python3
"""Build a climate-departure gold set (weather design 3, 4).

    python scripts/build_weather.py fetch
        # the pool: ~/.cache/reasonlineage/weather/pool.json, and its index gold/weather/pool.json with the sha256
    python scripts/build_weather.py build SET --band easy|medium|hard --tasks N [--exclude-set OTHER ...]
        # tasks/SET/*.json, gold/SET/gold.json and gold/SET/generation.json (no model calls)
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.gold import weather as wx  # noqa: E402

INDEX = ROOT / "gold" / "weather" / "pool.json"
FULL = wx.CACHE / "pool.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        pool = wx.fetch_pool(args.cache)
    except wx.SourceError as exc:
        print(f"cannot read NCEI: {exc}", file=sys.stderr)
        return 1
    data = wx.pool_bytes(pool)
    args.full.parent.mkdir(parents=True, exist_ok=True)
    args.full.write_bytes(data)
    write_json(args.index, {"api": wx.API, "months": list(wx.MONTHS), "measures": list(wx.MEASURES),
                            "full_pool": str(args.full), "sha256": hashlib.sha256(data).hexdigest(),
                            "readings": pool})
    print("; ".join(f"{key} {len(values)} states" for key, values in sorted(pool.items())))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    try:
        index = read_json(args.index)
        pool = wx.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, wx.SourceError) as exc:
        print(f"cannot read the pool ({exc}); run `fetch` first", file=sys.stderr)
        return 1
    exclude = [triple for other in args.exclude_set for triple in wx.triples_of(args.gold_root / other)]
    source = {"api": index["api"], "months": index["months"], "measures": index["measures"],
              "pool_sha256": index["sha256"], "exclude_sets": args.exclude_set}
    try:
        written = wx.build(args.set, args.band, args.tasks, pool, source,
                           args.tasks_root / args.set, args.gold_root / args.set, exclude=exclude)
    except wx.SourceError as exc:
        print(f"cannot build {args.set}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_root / args.set}; "
          f"gold.json and generation.json in {args.gold_root / args.set}")
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
    fetch.add_argument("--cache", type=Path, default=wx.CACHE)
    fetch.add_argument("--full", type=Path, default=FULL)
    build = sub.add_parser("build")
    build.add_argument("set", type=set_name)
    build.add_argument("--band", required=True, choices=wx.BAND_NAMES)
    build.add_argument("--tasks", required=True, type=positive)
    build.add_argument("--exclude-set", type=set_name, action="append", default=[],
                       help="do not reuse that set's triples; repeat for several sets")
    args = parser.parse_args(argv)
    return {"fetch": cmd_fetch, "build": cmd_build}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
