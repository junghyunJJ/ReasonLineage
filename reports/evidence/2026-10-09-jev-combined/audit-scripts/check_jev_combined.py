#!/usr/bin/env python3
"""Read-only first validation of the conditional jev gate."""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reasonlineage.checks.calibration import VERSION, questions_hash
from reasonlineage.checks.combined import policy_hash
from reasonlineage.checks.combined_calibration import build_cases, summarize
from reasonlineage.checks.credentials import read_dotenv_key, shared_dotenv
from reasonlineage.checks.gate import Gate
from reasonlineage.checks.jev import JevChecker
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.run import save_json
from reasonlineage.protocol import load_protocol
from calibrate_jev import RecordingChecker


async def execute(destination, *, holdout=False):
    key = read_dotenv_key(shared_dotenv(ROOT))
    protocol = load_protocol(ROOT/'research/co-scientist-pilot/protocol-jev-combined')
    cases = build_cases(ROOT,holdout=holdout)
    destination.mkdir(parents=True,exist_ok=False)
    save_json(destination/'cases.json',cases)
    save_json(destination/'frozen-j1.json',dict(protocol.j1))
    checker = RecordingChecker(JevChecker(key,VERSION,data_sensitivity='public'))
    records = []
    started = time.monotonic()
    for case in cases:
        gate = Gate(destination/case['id'],checker,protocol,case['evidence'],'experiment')
        await gate(case['id'],0,'anonymous',case['answer'],0)
        record = read_events(destination/case['id']/'checks.jsonl')[-1]
        records.append({'id':case['id'],'status':'failed' if record.get('error') else 'completed',**record})
        save_json(destination/'records.json',records)
        if record.get('error'):
            break
    result = {**summarize(cases,records),'model':VERSION,'holdout':holdout,
              'questions_sha256':questions_hash(protocol),'policy_sha256':policy_hash(protocol.j1),
              'thresholds':dict(protocol.j1['thresholds']),
              'cases_sha256':hashlib.sha256((destination/'cases.json').read_bytes()).hexdigest(),
              'backend_calls':checker.calls,'reported_input_tokens':checker.counts[0],
              'reported_output_tokens':checker.counts[1],'reported_tokens':checker.counts[2],
              'unknown_usage_calls':checker.unknown,'elapsed_seconds':round(time.monotonic()-started,3),
              'generator_calls':0,'deepseek_calls':0,'criterion':'48 actions and 48 correction targets correct; no unresolved cases',
              'limitation':'manual structural omissions, not scientific truth validation'}
    save_json(destination/'summary.json',result)
    assert all(key.encode() not in p.read_bytes() for p in destination.rglob('*') if p.is_file())
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--holdout',action='store_true')
    args=parser.parse_args()
    try:
        result=asyncio.run(execute(args.out,holdout=args.holdout))
        raise SystemExit(0 if result['passed'] else 2)
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}),flush=True)
        raise SystemExit(2)
