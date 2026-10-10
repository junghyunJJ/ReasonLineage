#!/usr/bin/env python3
"""Dry by default; --run executes the approved 16-slot jev on/off experiment."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reasonlineage.pilot.paired import paired_plan,run_pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'runs/jev-controlled-2026-10-09')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if not args.run:
        print(json.dumps(paired_plan(ROOT),ensure_ascii=False,indent=2))
        return 0
    if args.out.exists():
        parser.error('output folder already exists; choose a fresh folder')
    try:
        result=run_pair(args.out,ROOT)
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}),flush=True)
        return 2
    return 0 if result['complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
