"""One ALS retry; dry-run by default, --run checks connectivity before model dispatch."""
import argparse
import asyncio
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from reasonlineage.cli import _cancel_on_signals
from reasonlineage.engine.config import build_backend, load_setup
from reasonlineage.pilot.budget import safe_error
from reasonlineage.pilot.review import comparable, export_expert
from reasonlineage.pilot.run import run_case, save_json
from reasonlineage.pilot.study import StudyBudget, evaluator_member, independent_reviews, supervise
from reasonlineage.protocol import load_protocol

BASELINES = ROOT / 'reports/evidence/2026-10-06-co-scientist-rerun/public-candidates'
NATIVE_CODEX = Path('/common/jungj2/codex/packages/app-server-daemon/releases/0.160.0-x86_64-unknown-linux-musl/bin/codex')


def load_inputs():
    setup = load_setup(ROOT / 'configs/co-scientist-rerun.json')
    assert {m.name for m in setup.panel} == {'gpt', 'grok', 'glm'}
    evidence = (ROOT / 'research/co-scientist-pilot/als-evidence.md').read_bytes()
    digest = hashlib.sha256(evidence).hexdigest()
    controls = [json.loads((BASELINES / f'als-{m.name}/status.json').read_text()) for m in setup.panel]
    for control, member in zip(controls, setup.panel):
        assert control['status'] == 'completed' and control['header']['case'] == 'als'
        assert control['header']['method'] == member.name and control['header']['evidence_sha256'] == digest
        assert control['header']['models'][0]['model'] == member.model
    protocol = load_protocol(ROOT / 'research/co-scientist-pilot/protocol-relaxed')
    assert protocol.version == 'co-scientist-rerun-0.4'
    assert protocol.timeout('write') == protocol.timeout('judge') == 2700
    plan = {'scope': 'ALS/reasonlineage only; retain three existing ALS solos',
            'profile': protocol.version, 'protocol_sha256': protocol.hash, 'evidence_sha256': digest,
            'models': [{'name': m.name, 'model': m.model, 'effort': m.effort} for m in setup.panel],
            'generation_seconds': 2700, 'total_seconds': 3600, 'generation_tokens': 800000,
            'nominal_generation_calls': 30, 'max_generation_calls': 40, 'max_review_calls': 2,
            'max_total_calls': 42, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'code_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                          text=True, check=True).stdout.strip(),
            'control_profiles': {s['header']['method']: s['header']['protocol_version'] for s in controls},
            'clock_policy': 'Fresh clock for this newly authorized retry; old results and clocks remain unchanged.'}
    return setup, evidence.decode(), controls, plan


def probe_endpoints():
    def probe(host):
        try:
            with urllib.request.urlopen('https://' + host + '/', timeout=8) as response:
                return {'host': host, 'reachable': True, 'http_status': response.status}
        except urllib.error.HTTPError as error:
            return {'host': host, 'reachable': True, 'http_status': error.code}
        except Exception as error:
            return {'host': host, 'reachable': False, 'error_class': type(error).__name__,
                    'reason': str(getattr(error, 'reason', error))[:160]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(probe, ('chatgpt.com', 'api.x.ai', 'ollama.com')))


async def run_retry(destination, *, services=None, evaluator=None, probe=probe_endpoints):
    destination = Path(destination)
    setup, evidence, controls, plan = load_inputs()
    destination.mkdir(parents=True, exist_ok=False)
    plan['execution_mode'] = 'offline-injected' if services is not None else 'live'
    save_json(destination / 'frozen-plan.json', plan)
    connections = probe()
    save_json(destination / 'preflight.json', connections)
    if not connections or not all(c['reachable'] for c in connections):
        result = {'status': 'blocked_environment', 'phase': 'preflight',
                  'reason': 'Required model endpoint connectivity failed before model dispatch.',
                  'usage': {'backend_calls': 0, 'reported_tokens': 0, 'unknown_usage_calls': 0},
                  'generation': {'status': 'unstarted'}, 'frozen_plan': plan}
        save_json(destination / 'retry.json', result)
        return result
    frozen = destination / 'frozen-inputs'
    packet_root = frozen / 'research/co-scientist-pilot'
    packet_root.mkdir(parents=True)
    (packet_root / 'als-evidence.md').write_text(evidence)
    shutil.copytree(ROOT / 'research/co-scientist-pilot/protocol-relaxed', packet_root / 'protocol-relaxed')
    copied = destination / 'baseline-copies'
    copied.mkdir()
    for status in controls:
        save_json(copied / f"als-{status['header']['method']}.json", status)
    shared = StudyBudget(destination, seconds=2700, calls=42, tokens=None, lazy=True)
    generation = {'status': 'unstarted'}
    evaluations = [{'case': 'als', 'order': order, 'status': 'unstarted'} for order in ('forward', 'reverse')]
    error, cancelled = None, False
    try:
        if services is None:
            services = {m.name: build_backend(m, setup.concurrency) for m in setup.panel}
            if not NATIVE_CODEX.is_file():
                raise FileNotFoundError('Expected Codex 0.160.0 native executable is unavailable')
            services['gpt'].binary = str(NATIVE_CODEX)
        print('Starting ALS / reasonlineage, profile0.4, 45-minute generation cap', flush=True)
        try:
            generation = await asyncio.wait_for(run_case(destination / 'runs/als-reasonlineage', 'als',
                'reasonlineage', setup, services, shared, root=frozen, seconds=2700, tokens=800000,
                protocol_directory='protocol-relaxed'), 2700)
        except asyncio.TimeoutError:
            generation = json.loads((destination / 'runs/als-reasonlineage/status.json').read_text())
        shared.seconds = 3600
        statuses = [{'header': {'case': 'als', 'method': 'reasonlineage'}, **generation}, *controls]
        packet = export_expert(destination / 'review-materials', statuses, {'als': evidence})
        if generation['status'] == 'completed':
            evaluator = evaluator if evaluator is not None else build_backend(evaluator_member(setup), 1)
            reviewed = await independent_reviews(destination / 'independent', packet, {'als': evidence}, evaluator, shared)
            evaluations = [e for e in reviewed if e['case'] == 'als']
    except asyncio.CancelledError:
        cancelled = True
    except Exception as exc:
        error = safe_error(exc)
    finally:
        durable = destination / 'runs/als-reasonlineage/status.json'
        if durable.exists():
            generation = json.loads(durable.read_text())
        review_status = destination / 'independent/status.json'
        if review_status.exists():
            evaluations = [e for e in json.loads(review_status.read_text())['evaluations'] if e['case'] == 'als']
        comparisons = [{'solo': s['header']['method'], **comparable(generation, s)} for s in controls]
        result = {'status': 'completed' if generation['status'] == 'completed' and all(
                      e['status'] == 'completed' for e in evaluations) else 'incomplete',
                  'generation': generation, 'independent_evaluations': evaluations, 'comparisons': comparisons,
                  'expert_status': 'pending', 'usage': shared.snapshot(), 'error': error,
                  'cancelled': cancelled, 'frozen_plan': plan}
        save_json(destination / 'retry.json', result)
    if cancelled:
        raise asyncio.CancelledError
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if not args.run and not args.worker:
        print(json.dumps(load_inputs()[3], ensure_ascii=False, indent=2))
        return 0
    output = args.out
    if output is None:
        base = ROOT / 'runs/co-scientist-als-timeout-retry-2026-10-06'
        output, counter = base, 1
        while output.exists():
            counter += 1
            output = base.with_name(base.name + f'-v{counter}')
    if output.exists():
        parser.error('output already exists; choose a fresh directory')
    if args.worker:
        try:
            result = asyncio.run(_cancel_on_signals(run_retry(output.resolve())))
            print('Retry status:', result['status'], '; record:', output / 'retry.json', flush=True)
            return 0 if result['status'] == 'completed' else 2
        except asyncio.CancelledError:
            return 143
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--out', str(output.resolve())]
    return supervise(command, output.resolve() / 'clock.json', max_seconds=3600)


if __name__ == '__main__':
    raise SystemExit(main())
