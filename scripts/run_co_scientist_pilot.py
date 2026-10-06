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
    parser.add_argument('--relaxed', action='store_true', help='Three-model rerun with advisory word range and extended local caps')
    parser.add_argument('--preflight-dir', type=Path, help='Include diagnostic usage and its original global clock')
    args = parser.parse_args()
    if args.worker:
        try:
            result = asyncio.run(_cancel_on_signals(run_study(args.out.resolve(), ROOT, relaxed=args.relaxed,
                                 preflight_directory=args.preflight_dir)))
            print('Study recorded:', args.out / 'study.json', flush=True)
            return 0 if all(s['status'] == 'completed' for s in result['runs']) else 1
        except asyncio.CancelledError:
            print('Study stopped; completed records and status were preserved.', flush=True)
            return 143
    if not args.run:
        print(json.dumps(dry_plan(ROOT, relaxed=args.relaxed), ensure_ascii=False, indent=2))
        return 0
    if args.out.exists():
        parser.error('output folder already exists; choose a fresh folder')
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--out', str(args.out.resolve())]
    if args.relaxed:
        command.append('--relaxed')
    if args.preflight_dir:
        command.extend(['--preflight-dir', str(args.preflight_dir.resolve())])
    clock_file = args.preflight_dir.resolve() / 'clock.json' if args.preflight_dir else args.out.resolve() / 'clock.json'
    return supervise(command, clock_file)


if __name__ == '__main__':
    raise SystemExit(main())
