"""Assemble the completed pilot's local report and expert-only archive."""
import csv
import hashlib
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

root = Path.cwd()
run = root / 'runs/co-scientist-pilot-2026-10-05'
study = json.loads((run / 'study.json').read_text())
out = root / 'reports/evidence/2026-10-05-co-scientist-pilot'
out.mkdir(parents=True, exist_ok=False)
assert len(study['runs']) == 10
assert study['usage']['backend_calls'] <= 404
safe_raw = {'usage', 'provider_usage', 'served_model', 'finish_reason'}
records = list(run.rglob('calls/**/*.json'))
for path in records:
    response = json.loads(path.read_text())['response']
    assert set(response.get('raw', {})) <= safe_raw, path
for case, digest in study['frozen_plan']['evidence_sha256'].items():
    frozen = run / f'frozen-inputs/research/co-scientist-pilot/{case}-evidence.md'
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
for name in ('study.json', 'generation-only-study.json', 'frozen-plan.json', 'citation-audit.json',
             'literature-verification.md', 'nup62-sequence-check.json'):
    if (run / name).exists():
        shutil.copy2(run / name, out / name)
shutil.copytree(run / 'review-materials', out / 'review-materials')
shutil.copytree(run / 'reference-materials', out / 'reference-materials')
shutil.copy2(run / 'reference-independent/status.json', out / 'reference-independent-status.json')
if (run / 'independent/status.json').exists():
    shutil.copy2(run / 'independent/status.json', out / 'independent-status.json')
expert_zip = out / 'expert-only.zip'
with zipfile.ZipFile(expert_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((out / 'reference-materials/expert').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(out / 'reference-materials/expert'))

rows = []
public = out / 'public-candidates'
for directory in sorted((run / 'runs').iterdir()):
    events_path = directory / 'events.jsonl'
    if not events_path.exists():
        continue
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    registered = {e['id'] for e in events if e['event'] == 'candidate.created'}
    scored = {e['candidate']: e for e in events if e['event'] == 'candidate.scored'}
    for event in events:
        if event['event'] != 'candidate.created':
            continue
        cid = event['id']
        folder = public / directory.name
        folder.mkdir(parents=True, exist_ok=True)
        critiques = [e for e in events if e['event'] == 'judge.scored' and e['candidate'] == cid]
        text = '# ' + cid + '\n\n' + event['answer']['answer'] + '\n\n## Public critiques\n'
        for critique in critiques:
            text += '\n' + critique['judge'] + '\n' + '\n'.join('- ' + c for c in critique['critique']) + '\n'
        (folder / f'{cid}.md').write_text(text)
        rows.append({'run': directory.name, 'id': cid, 'generation': event['generation'],
                     'author': event['author'], 'operator': event['operator'],
                     'parents': ','.join(event['parents']), 'fitness': scored.get(cid, {}).get('fitness', ''),
                     'title': event['answer']['ranking'][0]['item']})
    for path in sorted(directory.glob('calls/g*/*/*/*.json')):
        parts = path.relative_to(directory / 'calls').parts
        if parts[1] not in ('write', 'mutate', 'cross') or parts[2] in registered:
            continue
        data = json.loads(path.read_text())['response']['data']
        if not isinstance(data, dict) or not isinstance(data.get('answer'), str):
            continue
        folder = public / directory.name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{parts[2]}-unregistered.md').write_text('# Unregistered public response\n\n'
             'Not registered as a candidate because output validation or the writing batch failed.\n\n' + data['answer'] + '\n')
with (out / 'evolution.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=['run', 'id', 'generation', 'author', 'operator', 'parents', 'fitness', 'title'], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)

completed = sum(s['status'] == 'completed' for s in study['runs'])
lines = ['# Co-Scientist pilot 결과', '',
         f'완료된 실행은 {completed}/10개다. 따라서 ReasonLineage의 우위를 판단할 수 없다. 사용자 승인에 따라 초기·중간 참고 가설 14개를 별도로 평가했고, 독립 LLM 평가 4회가 완료됐다. 전문가의 참고 평가는 대기 중이다. 실패·상한 중단은 가설 품질 점수로 바꾸지 않았다.', '',
         f"코드 고정: `{study['frozen_plan']['code_commit']}`. 오프라인 검증: 686 passed, 3 live deselected. GLM: `glm-5.3-flash`, 독립 평가: `deepseek-v4.1-flash`.", '',
         '| 과제 | 방법 | 상태 | 요청 시도 | 보고 토큰 | 사용량 미확인 호출 | 초기 내부 점수 | 최종 내부 점수 |',
         '|---|---|---|---:|---:|---:|---:|---:|']
for status in study['runs']:
    usage = status.get('usage', {})
    label = status['status']
    if label == 'failed' and usage.get('remaining_seconds') == 0:
        label = '시간 상한 중단'
    elif label == 'failed' and usage.get('reported_tokens', 0) >= (usage.get('token_limit') or float('inf')):
        label = '토큰 상한 중단'
    initial = status.get('initial', {}).get('fitness')
    final = status.get('final', {}).get('fitness')
    initial_s = '—' if initial is None else f'{initial:.3f}'
    final_s = '—' if final is None else f'{final:.3f}'
    header = status['header']
    lines.append(f"| {header['case'].upper()} | {header['method']} | {label} | {usage.get('backend_calls', 0)} | {usage.get('reported_tokens', 0):,} | {usage.get('unknown_usage_calls', 0)} | {initial_s} | {final_s} |")
lines.extend(['', '표의 점수는 내부 선택용 fitness다. 독립 LLM 평가나 전문가 판정과 같지 않다. 보고 토큰이 0인 실패 호출의 실제 소비량은 미확인이다.', '',
              f"전체 요청 시도 {study['usage']['backend_calls']}회, 보고 토큰 {study['usage']['reported_tokens']:,}, 사용량 미확인 {study['usage']['unknown_usage_calls']}회. 실제 청구 비용은 확인 불가다.", '',
              '## 실패 및 중단 사유', ''])
for status in study['runs']:
    if status['status'] != 'completed':
        lines.append(f"- {status['header']['case'].upper()} / {status['header']['method']}: {status.get('reason', status['status'])}")
lines.extend(['', '## 독립 평가와 사용량 비교', '',
              '독립 평가의 순서 정방향·역방향은 순서 편향 점검이며, 독립 표본 수를 늘리지 않는다.', ''])
for review in study['independent_evaluations']:
    lines.append(f"- {review['case'].upper()} / {review['order']}: {review['status']}")
lines.extend(['', '최종 완료 답이 없어 원래 최종 비교용 LLM 평가는 시작하지 않았다. 대신 승인받은 참고 가설 자료에 평가 예산 4회를 사용했다. 초기 내부 1위(없으면 ID순 첫 유효 초안)와 가장 최근 수정 세대의 공개 응답 전부를 포함했다. 길이 조건을 넘긴 수정본도 참고용으로 보존했으며, 정식 완료 답으로 바꾸지 않았다.', ''])
for review in study['reference_evaluations']:
    lines.append(f"- 참고 평가 {review['case'].upper()} / {review['order']}: {review['status']}")
lines.extend(['', 'ALS 참고 가설의 독립 근거성 평점은 2–3/5, AML은 3–4/5였다. 순서에 따라 일부 평점이 달라졌으며 두 순서 결과를 독립 표본으로 세지 않는다. 높은 구체성·검증 가능성 점수는 생물학적 사실의 확인을 뜻하지 않는다. Grok 수정본이 가정한 NUP62 Ser59/84/178/221은 사람 표준 서열의 L/G/N/L과 맞지 않았다. 모델 평가도 이 위치를 근거 없는 가정으로 지적했지만, 표준 서열 불일치까지 확인하지는 못했다.', ''])
matched = sum(c['comparable_usage'] for c in study['comparisons'])
lines.extend(['', f'계획한 8개 다중 모델–단독 모델 비교 중 사용량 비교 기준을 충족한 것은 {matched}개다. 완료 여부, 누락 없는 사용량, 총토큰 비율 0.9–1.1을 함께 요구한다. 실제 FLOPs를 측정하지 않았다.', '',
              '## 자료', '',
              '- [전문가용 익명 참고 평가 ZIP](evidence/2026-10-05-co-scientist-pilot/expert-only.zip): 이 ZIP만 전문가에게 먼저 전달한다. 방법·단계 대응표와 자동 평가·문헌 검증 결론은 포함하지 않는다.',
              '- [전체 상태·요약](evidence/2026-10-05-co-scientist-pilot/study.json)',
              '- [공개 계보 CSV](evidence/2026-10-05-co-scientist-pilot/evolution.csv)',
              '- [공개 가설과 비판](evidence/2026-10-05-co-scientist-pilot/public-candidates/)',
              '- [문헌 검증](evidence/2026-10-05-co-scientist-pilot/literature-verification.md)', '',
              '전문가에게는 익명 평점과 과제별 전체 선호순위를 받는다. 비교쌍 연결 구조가 다중 모델 답을 드러내므로, 계획한 비교는 분석 측에서 순위로부터 도출한다. 직접 쌍별 선호 질문과 평가 맥락이 다르며 첫 실제 호출 전에 수정·고정했다.', '',
              '사용량 누락은 이후 토큰 예산이 있는 호출을 중단시킨다. 모든 필수 응답이 이미 완료된 경우 유효한 답은 보존하되 사용량 비교에서 제외한다. 문헌 확인은 주장 검증의 범위를 명시하며 실제 생물학적 효과·신규 발견을 입증하지 않는다.'])
(root / 'reports/2026-10-05-co-scientist-pilot.md').write_text('\n'.join(lines) + '\n')

archive_root = root / '.archives/2026-10-05-co-scientist-pilot'
archive_root.mkdir(parents=True, exist_ok=False)
archive_path = archive_root / 'raw-records.tar.gz'
with tarfile.open(archive_path, 'w:gz') as archive:
    archive.add(run, arcname=run.name)
receipt = {'archive': str(archive_path.relative_to(root)), 'bytes': archive_path.stat().st_size,
           'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
           'public_call_records': len(records), 'public_candidates': len(rows),
           'expert_zip_sha256': hashlib.sha256(expert_zip.read_bytes()).hexdigest(),
           'validation': 'ten statuses, <=404 admitted attempts, public-only raw fields, matching frozen evidence hashes'}
save = lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
save(out / 'delivery-receipt.json', receipt)
print(json.dumps(receipt, ensure_ascii=False))
