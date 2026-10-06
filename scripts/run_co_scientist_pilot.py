#!/usr/bin/env python3
"""Dry-run by default; --run starts the approved bounded live pilot."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from reasonlineage.cli import _cancel_on_signals
from reasonlineage.pilot.study import dry_plan, run_study, supervise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'runs/co-scientist-pilot-2026-10-05')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            result = asyncio.run(_cancel_on_signals(run_study(args.out.resolve(), ROOT)))
            print('Study recorded:', args.out / 'study.json', flush=True)
            return 0 if all(s['status'] == 'completed' for s in result['runs']) else 1
        except asyncio.CancelledError:
            print('Study stopped; completed records and status were preserved.', flush=True)
            return 143
    if not args.run:
        print(json.dumps(dry_plan(ROOT), ensure_ascii=False, indent=2))
        return 0
    if args.out.exists():
        parser.error('output folder already exists; choose a fresh folder')
    return supervise([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--out', str(args.out.resolve())],
                     args.out.resolve() / 'clock.json')


if __name__ == '__main__':
    raise SystemExit(main())
