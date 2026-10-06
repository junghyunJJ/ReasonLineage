"""Archive the bounded experiment's public evidence after study.json exists."""
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
run = root / sys.argv[1]
out = root / 'reports/evidence/2026-10-06-co-scientist-rerun'
out.mkdir(parents=True, exist_ok=False)
study = json.loads((run / 'study.json').read_text())
for name in ('study.json', 'frozen-plan.json', 'clock.json', 'citation-audit.json', 'generation-status.json'):
    if (run / name).exists():
        shutil.copy2(run / name, out / name)
shutil.copytree(run / 'frozen-inputs', out / 'frozen-inputs')
shutil.copytree(run / 'review-materials/analyst', out / 'analyst')
if (run / 'independent/status.json').exists():
    shutil.copy2(run / 'independent/status.json', out / 'independent.json')
with zipfile.ZipFile(out / 'expert-only.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted((run / 'review-materials/expert').rglob('*')):
        if p.is_file():
            z.write(p, p.relative_to(run / 'review-materials/expert'))

public = out / 'public-candidates'
public.mkdir()
rows = []
index = ['# 공개 가설과 비판', '', '완료·중단 여부는 study.json에 있습니다. 중간 답변은 최종 완료 답이 아닙니다.', '']
for status in study['runs']:
    case, method = status['header']['case'], status['header']['method']
    folder = run / 'runs' / f'{case}-{method}'
    if not folder.exists():
        continue
    events = [json.loads(s) for s in (folder / 'events.jsonl').read_text().splitlines() if s.strip()]
    scores = {e['candidate']: e for e in events if e['event'] == 'candidate.scored'}
    candidates = {e['id']: e for e in events if e['event'] == 'candidate.created'}
    target = public / folder.name
    target.mkdir()
    shutil.copy2(folder / 'events.jsonl', target / 'events.jsonl')
    for cid, e in candidates.items():
        a = e['answer']
        score = scores.get(cid, {})
        rows.append({'case': case, 'method': method, 'id': cid, 'author': e['author'],
                     'generation': e['generation'], 'operator': e['operator'],
                     'parents': ','.join(e['parents']), 'fitness': score.get('fitness', ''),
                     'words': len(a['answer'].split()), 'title': a['ranking'][0]['item']})
    doc = [f'# {case.upper()} / {method}', '', f"실행 상태: {status['status']}", '']
    for p in sorted((folder / 'calls').rglob('*.json')):
        record = json.loads(p.read_text())
        data = record['response']['data']
        name = p.relative_to(folder / 'calls').with_suffix('').as_posix()
        doc.extend([f'## {name}', ''])
        if isinstance(data, dict) and isinstance(data.get('answer'), str):
            doc.extend([data['answer'], ''])
        elif isinstance(data, dict) and 'critique' in data:
            metrics = {k: v for k, v in data.items() if k != 'critique'}
            doc.extend([json.dumps(metrics, ensure_ascii=False), ''])
            points = data['critique'] if isinstance(data['critique'], list) else [data['critique']]
            doc.extend(['- ' + str(point) for point in points] + [''])
        else:
            doc.extend(['```json', json.dumps(data, ensure_ascii=False, indent=2), '```', ''])
    (target / 'answers-and-critiques.md').write_text('\n'.join(doc), encoding='utf-8')
    shutil.copy2(folder / 'status.json', target / 'status.json')
    index.append(f"- [{case.upper()} / {method}: {status['status']}]({folder.name}/answers-and-critiques.md)")
(public / 'README.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
fields = ['case', 'method', 'id', 'author', 'generation', 'operator', 'parents', 'fitness', 'words', 'title']
with (out / 'evolution.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

mapping = json.loads((out / 'analyst/mapping.json').read_text())['proposals']
dimensions = ('grounding', 'causal_rigor', 'specificity', 'testability', 'feasibility')
ratings = {}
for e in study['independent_evaluations']:
    for rating in e.get('ratings', []):
        ratings.setdefault(rating['id'], []).append(rating)
llm = []
for m in mapping:
    values = ratings.get(m['id'], [])
    if values:
        llm.append({**m, 'order_count': len(values),
                    **{key: sum(v[key] for v in values) / len(values) for key in dimensions},
                    'mean_dimensions': sum(v[k] for v in values for k in dimensions) / (len(values) * len(dimensions)),
                    'reasons': [v['reason'] for v in values]})
(out / 'independent-summary.json').write_text(json.dumps(llm, ensure_ascii=False, indent=2) + '\n')
hashes = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(out.rglob('*')) if p.is_file()}
(out / 'source-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
print(json.dumps({'output': str(out), 'registered_candidates': len(rows),
                  'completed_runs': sum(s['status'] == 'completed' for s in study['runs']),
                  'expert_proposals': len(mapping), 'usage': study['usage']}, ensure_ascii=False))
