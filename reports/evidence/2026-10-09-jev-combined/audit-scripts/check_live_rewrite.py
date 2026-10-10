"""Bounded controlled rewrite smoke test; never a full scientific study."""
import asyncio
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from reasonlineage.checks.calibration import validate_certificate
from reasonlineage.checks.credentials import read_dotenv_key, shared_dotenv
from reasonlineage.checks.gate import Gate
from reasonlineage.engine.calls import CallRecorder
from reasonlineage.engine.config import RunOptions, Task, build_backend, load_setup
from reasonlineage.engine.events import EventLog, read_events
from reasonlineage.pilot.budget import Budget, MeteredBackend, safe_error, public_data
from reasonlineage.pilot.checker import MeteredChecker, live_checker
from reasonlineage.pilot.run import PilotRunner, save_json
from reasonlineage.protocol import load_protocol

SOURCES = {
    'als': ('reports/evidence/2026-10-06-co-scientist-rerun/public-candidates/als-glm/status.json',
            'Discriminating strategy.'),
    'aml': ('reports/evidence/2026-10-08-aml-solo-retry/runs/aml-glm/status.json',
            'DISCRIMINATING PRECLINICAL STRATEGY.')}


class ControlledRunner(PilotRunner):
    async def _author_call(self, name, author, prompt):
        if '/write/' in name:
            self.events.emit('control.input', name=name, author=author,
                             detail='replayed historical answer with validation/falsifier tail removed; no provider call')
            save_json(self.run_dir / 'control-input.json', self.control_input)
            return copy.deepcopy(self.control_input)
        return await super()._author_call(name, author, prompt)


async def execute(destination):
    destination.mkdir(parents=True, exist_ok=False)
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    member = next(m for m in setup.panel if m.name == 'glm')
    protocol = load_protocol(ROOT / 'research/co-scientist-pilot/protocol-jev-combined')
    validate_certificate(protocol)
    shared = Budget(seconds=1200, calls=24, tokens=None)
    writer = Budget(seconds=1200, calls=4, tokens=120000, lazy=True)
    checks = Budget(seconds=1200, calls=20, tokens=None, lazy=True)
    backend = MeteredBackend(build_backend(member, setup.concurrency), writer, shared,
                             concurrency=setup.concurrency)
    checker_service = live_checker(ROOT)
    results = []
    started = time.monotonic()
    for case, (source_name, marker) in SOURCES.items():
        folder = destination / case
        folder.mkdir()
        source = ROOT / source_name
        history = json.loads(source.read_text())
        original = history['final']['answer']
        assert isinstance(original, dict) and original['answer'].count(marker) == 1
        controlled = copy.deepcopy(original)
        controlled['answer'] = original['answer'].split(marker)[0].rstrip()
        save_json(folder / 'original-answer.json', original)
        save_json(folder / 'source.json', {
            'path': source_name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'original_id': history['final']['id'], 'author': history['final']['author'],
            'removed': 'validation and falsification tail', 'cut_before': marker})
        events = EventLog(folder / 'events.jsonl')
        checker = MeteredChecker(checker_service, checks, shared, writer, folder)
        question = (ROOT / f'research/co-scientist-pilot/{case}-evidence.md').read_text()
        gate = Gate(folder, checker, protocol, question, 'experiment')
        normal = await gate('original', 0, 'glm', original, 0)
        recorder = CallRecorder(folder, events, 20261009, attempts=1, retry_backend_errors=False,
                                unusable_sanitizer=public_data)
        runner = ControlledRunner(run_dir=folder, run_id=f'{case}-controlled-rewrite',
                                  task=Task(case, question, None, 'biomedical', 'public'),
                                  members=setup.panel, backends={'glm': backend}, protocol=protocol,
                                  options=RunOptions(), events=events, recorder=recorder, gate=gate)
        runner.control_input = controlled
        result = {'case': case, 'model': member.model, 'original_requests_rewrite': normal.rewrite,
                  'scope': 'controlled omission on archived answer; no evolution/fitness/science evaluation'}
        try:
            written = await runner._write(0, 'write', 'controlled', 'glm', runner._seed_prompt(None))
            save_json(folder / 'rewritten-answer.json', written.data)
            rows = read_events(folder / 'checks.jsonl')
            result.update(status='completed', versions=written.versions, author=written.author,
                          rewrite_calls=sum('/rewrite/' in v for v in written.versions),
                          checks=[{k:r.get(k) for k in ('candidate','attempt','would_rewrite','needs_review',
                                  'focus','adequacy','proposal_probability','primary_gap','rechecked')} for r in rows])
            result['passed'] = (not normal.rewrite and len(written.versions) == 2 and
                                written.author == 'glm' and rows[-1]['attempt'] == 1 and
                                not rows[-1]['would_rewrite'] and not rows[-1].get('needs_review') and
                                not any(r.get('error') for r in rows))
        except Exception as error:
            result.update(status='failed', passed=False, reason=safe_error(error))
        results.append(result)
        save_json(folder / 'summary.json', result)
        if result['status'] == 'failed':
            break
    summary = {'passed': len(results) == 2 and all(r['passed'] for r in results),
               'cases': results, 'writer_usage': writer.snapshot(), 'checker_usage': checks.snapshot(),
               'shared_usage': shared.snapshot(), 'deepseek_calls': 0,
               'elapsed_seconds': round(time.monotonic() - started, 3)}
    save_json(destination / 'summary.json', summary)
    key = read_dotenv_key(shared_dotenv(ROOT)).encode()
    assert all(key not in p.read_bytes() for p in destination.rglob('*') if p.is_file())
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        asyncio.run(execute(ROOT / 'runs/jev-combined-live-rewrite-2026-10-09'))
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,
                          'details':'suppressed'}), flush=True)
        raise SystemExit(2)
