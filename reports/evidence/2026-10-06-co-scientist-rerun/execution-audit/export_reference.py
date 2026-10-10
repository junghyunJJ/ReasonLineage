import hashlib
import json
import random
import secrets
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from reasonlineage.pilot.review import _IDENTITY, _DISCLOSURE, RATINGS

run = root / 'runs/co-scientist-rerun-2026-10-06-r2'
out = root / 'reports/evidence/2026-10-06-co-scientist-rerun'
study = json.loads((run / 'study.json').read_text())
proposals, mapping, seen, excluded = [], [], {}, []


def add(case, method, stage, answer, source):
    text, ranking = answer.get('answer', '').strip(), answer.get('ranking', [])
    if not text or not isinstance(ranking, list) or len(ranking) != 1:
        return
    title = ranking[0]['item']
    if _IDENTITY.search(text + '\n' + title) or _DISCLOSURE.search(text + '\n' + title):
        excluded.append({'case': case, 'method': method, 'stage': stage})
        return
    digest = hashlib.sha256(' '.join(text.split()).encode()).hexdigest()
    key = case, digest
    if key not in seen:
        pid = 'R' + secrets.token_hex(5)
        seen[key] = pid
        proposals.append({'id': pid, 'case': case, 'title': title, 'text': text})
    mapping.append({'id': seen[key], 'case': case, 'method': method, 'stage': stage,
                    'source': source, 'content_sha256': digest})


for status in study['runs']:
    if status['status'] == 'completed':
        continue
    case, method = status['header']['case'], status['header']['method']
    folder = run / 'runs' / f'{case}-{method}'
    authored = []
    for path in sorted((folder / 'calls').rglob('*.json')):
        data = json.loads(path.read_text())['response']['data']
        if isinstance(data, dict) and isinstance(data.get('answer'), str) and len(data.get('ranking', [])) == 1:
            authored.append((int(path.relative_to(folder / 'calls').parts[0][1:]), path, data))
    if not authored:
        continue
    if status.get('initial'):
        add(case, method, 'initial', status['initial']['answer'], f'runs/{folder.name}/status.json#initial')
    else:
        generation, path, data = authored[0]
        add(case, method, 'first_valid_unscored', data, path.relative_to(run).as_posix())
    latest = max(g for g, p, d in authored)
    for generation, path, data in authored:
        if generation == latest:
            add(case, method, f'latest_public_generation_{generation}', data, path.relative_to(run).as_posix())

random.SystemRandom().shuffle(proposals)
with zipfile.ZipFile(out / 'expert-reference-only.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('README.md', 'Finish the main expert-only.zip blind ratings before opening this reference packet. '
                     'These are public hypotheses from incomplete runs, for exploratory reference assessment only. '
                     'Rate grounding, causal rigor, specificity, testability and feasibility from 1 to 5 against the '
                     'common evidence. Describe novelty, scientific reasons and possible unblinding. '
                     'No final-method superiority claim follows from these partial outputs.\n')
    archive.writestr('packet.json', json.dumps({'proposals': proposals, 'pairs': []}, ensure_ascii=False, indent=2))
    archive.writestr('ratings.json', json.dumps({'ratings': [
        {'id': p['id'], **dict.fromkeys(RATINGS), 'novelty_note': '', 'reason': '', 'possible_unblinding': ''}
        for p in proposals]}, ensure_ascii=False, indent=2))
    for proposal in proposals:
        archive.writestr(proposal['id'] + '.md', '# ' + proposal['id'] + '\n\n' + proposal['text'] + '\n')
    for case in ('als', 'aml'):
        archive.write(run / 'frozen-inputs/research/co-scientist-pilot' / f'{case}-evidence.md', f'{case}-evidence.md')
(out / 'analyst/reference-mapping.json').write_text(json.dumps(
    {'proposals': mapping, 'excluded': excluded}, ensure_ascii=False, indent=2) + '\n')
print({'reference_unique_proposals': len(proposals), 'reference_links': len(mapping),
       'excluded': len(excluded), 'new_model_calls': 0})
