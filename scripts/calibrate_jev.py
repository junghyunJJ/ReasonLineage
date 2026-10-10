#!/usr/bin/env python3
"""Fixed 0.5 J1 validation; no generator or DeepSeek calls."""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from reasonlineage.checks.calibration import VERSION, THRESHOLDS, build_cases, summarize, questions_hash
from reasonlineage.checks.credentials import read_dotenv_key, shared_dotenv
from reasonlineage.checks.gate import Gate
from reasonlineage.checks.jev import JevChecker
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import usage_counts
from reasonlineage.pilot.run import save_json
from reasonlineage.protocol import load_protocol


class RecordingChecker:
    name, pinned_version = 'jev', VERSION
    def __init__(self, service):
        self.service, self.calls, self.counts, self.unknown = service, 0, [0, 0, 0], 0

    async def ask(self, state, questions):
        self.calls += 1
        try:
            result = await self.service.ask(state, questions)
        except Exception:
            self.unknown += 1
            raise
        counts = usage_counts(result.usage or {})
        if counts is None:
            self.unknown += 1
        else:
            self.counts = [a + b for a, b in zip(self.counts, counts)]
        return result


async def execute(destination, env_path, *, protocol_directory='protocol-three-initial', holdout=False):
    key = read_dotenv_key(env_path)
    destination.mkdir(parents=True, exist_ok=False)
    protocol = load_protocol(ROOT / 'research/co-scientist-pilot' / protocol_directory)
    if dict(protocol.j1['thresholds']) != THRESHOLDS:
        raise ValueError('calibration requires the prespecified fixed thresholds')
    cases = build_cases(ROOT, holdout=holdout)
    save_json(destination / 'cases.json', cases)
    checker = RecordingChecker(JevChecker(key, VERSION, data_sensitivity='public'))
    records = []
    start = time.monotonic()
    for case in cases:
        gate = Gate(destination / case['id'], checker, protocol, case['evidence'], 'experiment')
        await gate(case['id'], 0, 'anonymous', case['answer'], 0)
        record = read_events(destination / case['id'] / 'checks.jsonl')[-1]
        row = {'id': case['id'], 'status': 'failed' if record.get('error') else 'completed', **record}
        records.append(row)
        save_json(destination / 'records.json', records)
    result = {**summarize(cases, records), 'model': VERSION, 'thresholds': THRESHOLDS, 'holdout': holdout,
              'questions_sha256': questions_hash(protocol),
              'cases_sha256': hashlib.sha256((destination / 'cases.json').read_bytes()).hexdigest(),
              'backend_calls': checker.calls, 'reported_input_tokens': checker.counts[0],
              'reported_output_tokens': checker.counts[1], 'reported_tokens': checker.counts[2],
              'unknown_usage_calls': checker.unknown, 'elapsed_seconds': round(time.monotonic() - start, 3),
              'generator_calls': 0, 'deepseek_calls': 0, 'criterion': 'all 30 labelled examples correct at fixed 0.5',
              'limitation': 'small manually labelled examples; not real-hypothesis correctness validation'}
    save_json(destination / 'summary.json', result)
    assert all(key.encode() not in p.read_bytes() for p in destination.rglob('*') if p.is_file())
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--env', type=Path)
    parser.add_argument('--protocol-directory', default='protocol-three-initial')
    parser.add_argument('--holdout', action='store_true')
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args.out, args.env or shared_dotenv(ROOT),
                                    protocol_directory=args.protocol_directory, holdout=args.holdout))
        raise SystemExit(0 if result['passed'] else 2)
    except Exception as error:
        print(json.dumps({'status': 'stopped', 'error_type': type(error).__name__,
                          'message': 'external details suppressed'}), flush=True)
        raise SystemExit(2)
