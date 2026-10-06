import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from reasonlineage.protocol import load_protocol

run = root / 'runs/co-scientist-rerun-2026-10-06-r2'
out = root / 'reports/evidence/2026-10-06-co-scientist-rerun'
study = json.loads((run / 'study.json').read_text())
prior = json.loads((run / 'prior-attempt/study.json').read_text())
independent = json.loads((run / 'independent/status.json').read_text())
keys = ('backend_calls', 'reported_input_tokens', 'reported_output_tokens', 'reported_tokens', 'unknown_usage_calls')
for key in keys:
    assert study['usage'][key] == prior['usage'][key] + independent['usage'][key] + sum(
        s['usage'][key] for s in study['runs'])
assert all(e['status'] == 'completed' for e in independent['evaluations'])
assert len(independent['evaluations']) == 4
assert sum(s['status'] == 'completed' for s in study['runs']) == 4
assert study['usage']['elapsed_seconds'] < 14400
assert study['usage']['backend_calls'] <= study['usage']['call_limit'] <= 404
assert json.loads((run / 'clock.json').read_text()) == json.loads((run / 'prior-attempt/clock.json').read_text())
for p in (root / 'runs/co-scientist-rerun-2026-10-06').rglob('*'):
    if p.is_file():
        assert p.read_bytes() == (run / 'prior-attempt' / p.relative_to(root / 'runs/co-scientist-rerun-2026-10-06')).read_bytes()

plan = study['frozen_plan']
source = subprocess.run(['git', 'archive', plan['code_commit'], 'src/reasonlineage'],
                        cwd=root, capture_output=True, check=True).stdout
digest = hashlib.sha256()
with tarfile.open(fileobj=io.BytesIO(source)) as archive:
    for member in sorted(archive.getmembers(), key=lambda m: m.name):
        if member.isfile() and member.name.endswith('.py'):
            digest.update(member.name.encode() + b'\0' + archive.extractfile(member).read())
assert digest.hexdigest() == plan['code_sha256']
frozen = run / 'frozen-inputs/research/co-scientist-pilot'
assert load_protocol(frozen / 'protocol-relaxed').hash == plan['protocol_sha256']
for case, expected in plan['evidence_sha256'].items():
    assert hashlib.sha256((frozen / f'{case}-evidence.md').read_bytes()).hexdigest() == expected

private = {'reasoning', 'reasoning_content', 'chain_of_thought', 'analysis', 'authorization', 'api_key'}
def flags(value):
    if isinstance(value, dict):
        return sum(str(k).lower() in private for k in value) + sum(flags(v) for v in value.values())
    if isinstance(value, list):
        return sum(flags(v) for v in value)
    return 0

responses = list(run.glob('**/calls/**/*.json')) + list(run.glob('**/unusable/**/*.json'))
for path in responses:
    record = json.loads(path.read_text())
    assert flags(record) == 0, path
    try:
        decoded = json.loads(record.get('response', {}).get('text', ''))
    except (ValueError, TypeError):
        continue
    assert flags(decoded) == 0, path

expert_counts = {}
for filename in ('expert-only.zip', 'expert-reference-only.zip'):
    with zipfile.ZipFile(out / filename) as archive:
        names = archive.namelist()
        assert not any('analyst' in n or 'mapping' in n or 'independent' in n for n in names)
        packet = json.loads(archive.read('packet.json'))
        assert packet['pairs'] == []
        ids = {p['id'] for p in packet['proposals']}
        ratings = json.loads(archive.read('ratings.json'))['ratings']
        assert {r['id'] for r in ratings} == ids
        assert all(r[k] is None for r in ratings for k in ('grounding', 'causal_rigor', 'specificity', 'testability', 'feasibility'))
        assert all(p['id'] + '.md' in names for p in packet['proposals'])
        expert_counts[filename] = len(ids)
assert expert_counts == {'expert-only.zip': 7, 'expert-reference-only.zip': 11}
with (out / 'evolution.csv').open() as file:
    rows = list(csv.DictReader(file))
events = [json.loads(line) for p in (run / 'runs').glob('*/events.jsonl') for line in p.read_text().splitlines() if line.strip()]
assert len(rows) == sum(e['event'] == 'candidate.created' for e in events) == 64
assert not any(c['comparable_usage'] for c in study['comparisons'])

archive_dir = root / '.archives/2026-10-06-co-scientist-rerun'
archive_dir.mkdir(parents=True, exist_ok=False)
raw_archive = archive_dir / 'raw-records.tar.gz'
inventory = {}
sources = (run, root / 'runs/co-scientist-opus-diagnostic-2026-10-06')
with tarfile.open(raw_archive, 'w:gz') as archive:
    for directory in sources:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                name = directory.name + '/' + path.relative_to(directory).as_posix()
                inventory[name] = hashlib.sha256(path.read_bytes()).hexdigest()
                archive.add(path, arcname=name, recursive=False)
with tarfile.open(raw_archive) as archive:
    files = [m for m in archive.getmembers() if m.isfile()]
    assert len(files) == len(inventory)
    assert all(hashlib.sha256(archive.extractfile(m).read()).hexdigest() == inventory[m.name] for m in files)
(out / 'raw-records.inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
verification = {'frozen_code_commit': plan['code_commit'], 'frozen_source_sha256': digest.hexdigest(),
                'frozen_source_and_inputs_match': True, 'prior_attempt_bytes_preserved': True,
                'original_clock_preserved': True, 'usage_reconciled_exactly_once': True,
                'model_admissions': study['usage']['backend_calls'], 'reported_tokens': study['usage']['reported_tokens'],
                'unknown_usage_calls': study['usage']['unknown_usage_calls'], 'confirmed_missing_executable_calls': 4,
                'completed_runs': 4, 'completed_independent_reviews': 4,
                'registered_candidates': len(rows), 'response_records_private_field_checked': len(responses),
                'private_field_flags': 0, 'expert_unique_proposals': expert_counts,
                'comparable_primary_pairs': 0, 'expert_status': 'pending',
                'raw_archive': str(raw_archive), 'raw_archive_files': len(inventory),
                'raw_archive_sha256': hashlib.sha256(raw_archive.read_bytes()).hexdigest(),
                'next_profile': '0.4', 'next_profile_live_tested': False,
                'next_profile_offline_tests': '738 passed, 3 live deselected'}
(out / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(verification, ensure_ascii=False))
