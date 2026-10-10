"""Read-only analysis of original and separately completed planned experiments."""
import copy
import csv
import hashlib
import html
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))

from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import public_data
from reasonlineage.pilot.paired import paired_plan
from reasonlineage.pilot.review import citation_audit, export_expert
from reasonlineage.pilot.run import save_json

BASE = ROOT / 'runs/jev-controlled-2026-10-09'
METHODS = ('reasonlineage', 'gpt', 'grok', 'glm')
LABELS = {'reasonlineage': '3-model multi', 'gpt': 'GPT solo', 'grok': 'Grok solo', 'glm': 'GLM Flash solo'}
FIELDS = ('backend_calls', 'reported_input_tokens', 'reported_output_tokens', 'reported_tokens', 'unknown_usage_calls')


def load(path):
    return json.loads(Path(path).read_text())


def total_usage(*items):
    return {key: sum(item.get(key, 0) for item in items) for key in FIELDS}


def read_run(arm, case, method):
    original_dir = BASE / arm / 'runs' / f'{case}-{method}'
    original = load(original_dir / 'status.json')
    supplement_dirs = [BASE / kind / f'{arm}-{case}-{method}' for kind in
                       ('terminal-completions', 'planned-step-completions', 'structured-completions')]
    supplements = [(p, load(p / 'status.json')) for p in supplement_dirs if (p / 'status.json').exists()]
    successful = [(p, s) for p, s in supplements if s['status'] in ('evaluation_complete', 'planned_steps_complete')]
    assert original['status'] == 'completed' or len(successful) == 1, (arm, case, method, supplements)
    source, result = successful[0] if successful else (original_dir, original)
    assert result.get('final') and result['j1']['status'] == ('completed' if arm == 'jev-on' else 'disabled')
    assert result['diagnostics']['status'] == ('completed' if arm == 'jev-on' else 'disabled')
    events = read_events(source / 'events.jsonl')
    born = {r['id']: r for r in events if r['event'] == 'candidate.created'}
    scored = {r['candidate']: r for r in events if r['event'] == 'candidate.scored'}
    judged = [r for r in events if r['event'] == 'judge.scored']
    assert len(born) == len(scored) == 9 and len(judged) == 18
    assert all(sum(r['candidate'] == cid for r in judged) == 2 for cid in born)
    selections = {r['generation']: r for r in events if r['event'] == 'selection'}
    assert set(selections) == {0, 1, 2}
    stages = []
    for generation in range(4):
        new = [cid for cid, r in born.items() if r['generation'] == generation]
        population = new if generation == 0 else selections[generation - 1]['survivors'] + new
        assert len(new) == (3 if generation == 0 else 2)
        assert len(population) == (3 if generation == 0 else 4)
        top = max(population, key=lambda cid: scored[cid]['fitness'])
        stages.append({'generation': generation, 'population': population, 'new': new, 'best': top,
                       'fitness': scored[top]['fitness'], 'selection': selections.get(generation)})
    assert abs(stages[-1]['fitness'] - result['final']['fitness']) < 1e-12
    assert result['final']['id'] in stages[-1]['population']
    j1 = read_events(original_dir / 'checks.jsonl') if arm == 'jev-on' else []
    j2 = read_events(source / 'diagnostics/j2.jsonl') if arm == 'jev-on' else []
    if arm == 'jev-on':
        assert len(j1) == 9 and len(j2) == 27 and not any(r.get('error') for r in j1 + j2)
    nodes = []
    evidence = (BASE / arm / f'frozen-inputs/research/co-scientist-pilot/{case}-evidence.md').read_text()
    for cid, created in sorted(born.items()):
        nodes.append({'id': cid, 'author': created['author'], 'operator': created['operator'],
                      'generation': created['generation'], 'parents': created['parents'],
                      'versions': created['versions'], 'answer': created['answer'],
                      'fitness': scored[cid]['fitness'], 'scores': scored[cid]['scores'],
                      'judgments': [r for r in judged if r['candidate'] == cid],
                      'j1': [r for r in j1 if r['candidate'] == cid],
                      'j2': [r for r in j2 if r['candidate'] == cid or str(r['candidate']).startswith(cid + '/')],
                      'citation_audit': citation_audit(created['answer']['answer'], created['answer']['ranking'][0].get('pmids', []), evidence)})
    model_usage = total_usage(original['usage'], *(s['new_model_usage'] for _, s in supplements))
    checker_usage = total_usage(original.get('checker_usage', {}), *(s.get('new_checker_usage', {}) for _, s in supplements))
    return {'arm': arm, 'case': case, 'method': method, 'label': LABELS[method],
            'original_status': original['status'], 'original_reason': original.get('reason'),
            'completion_status': result['status'], 'used_supplement': bool(successful),
            'original_directory': str(original_dir.relative_to(BASE)), 'result_directory': str(source.relative_to(BASE)),
            'supplements': [{'directory': str(p.relative_to(BASE)), 'status': s['status'], 'kind': s['kind'],
                            'model_usage': s['new_model_usage'], 'checker_usage': s.get('new_checker_usage', {}),
                            'reason': s.get('reason')} for p, s in supplements],
            'initial': original['initial'], 'final': result['final'],
            'gain': result['final']['fitness'] - original['initial']['fitness'],
            'model_usage': model_usage, 'checker_usage': checker_usage,
            'original_seconds': original['usage']['elapsed_seconds'],
            'supplement_seconds': sum(s['new_model_usage']['elapsed_seconds'] for _, s in supplements),
            'cumulative_token_cap_verified': model_usage['unknown_usage_calls'] == 0 and model_usage['reported_tokens'] <= 800000,
            'j1_records': len(j1), 'j1_would_rewrite': sum(bool(r.get('would_rewrite')) for r in j1),
            'j1_actual_rewrites': sum(any('/rewrite/' in v for v in n['versions']) for n in nodes),
            'j1_needs_review': sum(bool(r.get('needs_review')) for r in j1),
            'j2_records': len(j2), 'stages': stages, 'candidates': nodes}


def expert_material(runs):
    statuses = []
    for r in runs:
        header = load(BASE / r['original_directory'] / 'status.json')['header']
        header = {**header, 'method': r['arm'] + '/' + r['method']}
        statuses.append({'status': 'completed', 'header': header, 'initial': r['initial'], 'final': r['final']})
    folder = BASE / 'completed-review-materials'
    assert not folder.exists()
    evidence = {case: (BASE / f'jev-on/frozen-inputs/research/co-scientist-pilot/{case}-evidence.md').read_text() for case in ('als', 'aml')}
    packet = export_expert(folder, statuses, evidence)
    mapping = load(folder / 'analyst/mapping.json')
    lookup = {(p['case'], p['method'], p['stage']): p['id'] for p in mapping['proposals']}
    pairs = []
    def add(case, first, second, kind):
        a, b = lookup.get((case, *first)), lookup.get((case, *second))
        pairs.append({'case': case, 'kind': kind, 'first_ref': first, 'second_ref': second,
                      'first': a, 'second': b, 'status': 'same_text' if a == b and a else 'ready' if a and b else 'excluded'})
    for case in ('als', 'aml'):
        for method in METHODS:
            add(case, ('jev-on/' + method, 'final'), ('jev-off/' + method, 'final'), 'on_off_final')
        for arm in ('jev-on', 'jev-off'):
            for method in METHODS:
                add(case, (arm + '/' + method, 'initial'), (arm + '/' + method, 'final'), 'initial_final')
            for method in METHODS[1:]:
                add(case, (arm + '/reasonlineage', 'final'), (arm + '/' + method, 'final'), 'multi_solo_final')
    mapping['planned_comparisons'] = pairs
    save_json(folder / 'analyst/mapping.json', mapping)
    return {'status': 'pending', 'stage_references': len(mapping['proposals']), 'unique_proposals': len(packet['proposals']),
            'excluded': mapping['excluded'], 'planned_comparisons': len(pairs),
            'comparison_status': dict(Counter(p['status'] for p in pairs)), 'directory': str(folder.relative_to(BASE))}


def write_tables(runs, comparisons):
    with (BASE / 'completed-comparison.csv').open('w', newline='') as stream:
        fields = ('case', 'method', 'on_initial', 'on_final', 'on_gain', 'off_initial', 'off_final', 'off_gain',
                  'on_minus_off', 'on_original_status', 'off_original_status', 'on_supplement', 'off_supplement')
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for r in comparisons:
            writer.writerow({key: r[key] for key in fields})
    with (BASE / 'candidate-scores.csv').open('w', newline='') as stream:
        fields = ('arm', 'case', 'method', 'candidate', 'generation', 'author', 'operator', 'parents', 'fitness',
                  'evidenceCoverage', 'specificity', 'novelty', 'actionability', 'final_selected', 'title')
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for r in runs:
            for node in r['candidates']:
                writer.writerow({'arm': r['arm'], 'case': r['case'], 'method': r['method'], 'candidate': node['id'],
                                 **{key: node[key] for key in ('generation', 'author', 'operator', 'fitness')},
                                 'parents': ','.join(node['parents']), **node['scores'],
                                 'final_selected': node['id'] == r['final']['id'], 'title': node['answer']['ranking'][0]['item']})
    with (BASE / 'generation-scores.csv').open('w', newline='') as stream:
        fields = ('arm', 'case', 'method', 'generation', 'population', 'new', 'best', 'fitness', 'survivors')
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for r in runs:
            for stage in r['stages']:
                writer.writerow({'arm': r['arm'], 'case': r['case'], 'method': r['method'],
                                 **{key: stage[key] for key in ('generation', 'best', 'fitness')},
                                 'population': ','.join(stage['population']), 'new': ','.join(stage['new']),
                                 'survivors': ','.join((stage['selection'] or {}).get('survivors', []))})


def write_viewer(summary):
    data = json.dumps(public_data(summary), ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReasonLineage ALS·AML 전체 진화 기록</title>
<style>body{font:15px/1.6 system-ui,sans-serif;background:#f4f6f8;color:#182536;margin:24px}h1{font-size:26px}select,button{font:inherit;padding:8px;border:1px solid #a8b4c2;border-radius:6px;background:white}#controls{display:flex;gap:12px;flex-wrap:wrap}.notice,.summary{background:white;padding:16px;border-radius:10px;margin:14px 0}.stages{display:grid;grid-template-columns:repeat(4,minmax(260px,1fr));gap:16px;overflow-x:auto}.stage{background:#e8eef4;padding:12px;border-radius:10px}.card{background:white;border:1px solid #d1dbe5;border-radius:8px;padding:12px;margin:10px 0}.winner{border:3px solid #067a60}.score{font-size:23px;font-weight:750;color:#067a60}.meta{color:#566579;font-size:13px}pre{font:13px/1.6 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere}details{margin:10px 0}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #ddd;text-align:left;padding:5px}a{color:#086aa0}.legend{margin-top:8px}svg{width:100%;max-width:900px;height:65px}footer{margin:25px 0}</style>
<h1>ALS·AML: jev ON / OFF 전체 진화 과정</h1>
<div class="notice">16개 결과 확보. 원래 제한 내 완료 13개, 별도 보완 완료 3개. 점수는 내부 비판 모델의 fitness이며 과학적 사실성 점수가 아닙니다. jev 재작성은 0회입니다. 각 카드에서 원문·평가·jev 기록을 펼칠 수 있습니다.</div>
<div id="controls"><select id="case"><option value="als">ALS</option><option value="aml">AML</option></select><select id="method"><option value="reasonlineage">다중 모델 GPT + Grok + GLM Flash</option><option value="gpt">GPT 단독</option><option value="grok">Grok 단독</option><option value="glm">GLM Flash 단독</option></select><select id="arm"><option value="jev-on">jev ON</option><option value="jev-off">jev OFF</option></select></div>
<div id="summary" class="summary"></div><div id="stages" class="stages"></div>
<footer>살아남은 가설은 이전 점수를 유지합니다. 카드의 부모 ID는 변이·교차의 계보입니다. G3는 최종 4개 중 최상위 가설을 반환합니다. 공개 답변과 비판만 제공하며 비공개 추론은 포함하지 않습니다. 전문가 평가는 아직 수행되지 않았습니다.</footer>
<script>const DATA=__DATA__;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>Number(v).toFixed(4);
const detail=(label,text)=>`<details><summary>${esc(label)}</summary><pre>${esc(text)}</pre></details>`;
function render(){const r=DATA.runs.find(r=>r.case===document.getElementById('case').value&&r.method===document.getElementById('method').value&&r.arm===document.getElementById('arm').value);
 document.getElementById('summary').innerHTML=`<b>${esc(r.case.toUpperCase())} / ${esc(r.label)} / ${esc(r.arm)}</b><br>초기 1위 ${num(r.initial.fitness)} → 최종 ${num(r.final.fitness)} (변화 ${r.gain>=0?'+':''}${num(r.gain)}) · 최종 ${esc(r.final.id)} (${esc(r.final.author)})<br>원본: ${esc(r.original_status)} · 보완: ${r.used_supplement?'별도 완료':'없음'} · 가설 9개 / 비판 18개 / 모델 호출 ${r.model_usage.backend_calls} / jev 호출 ${r.checker_usage.backend_calls}<br>미확인 사용량 ${r.model_usage.unknown_usage_calls}회 · J1 ${r.j1_records}개 · jev 재작성 ${r.j1_actual_rewrites}회`;
 document.getElementById('stages').innerHTML=r.stages.map(s=>`<section class="stage"><h2>G${s.generation}</h2><p>신규 ${s.new.length} · 후보 ${s.population.length}<br>최상위 ${esc(s.best)} / <b>${num(s.fitness)}</b></p>${s.selection?`<p>다음 생존: ${esc(s.selection.survivors.join(', '))}${s.selection.tie_break_swap?'<br>작성자 다양성 타이브레이크 적용':''}</p>`:'<p>최종 선택</p>'}${s.population.map(id=>{const n=r.candidates.find(n=>n.id===id);return `<article class="card ${id===r.final.id&&s.generation===3?'winner':''}"><b>${esc(id)} · ${esc(n.author)}</b><div class="score">${num(n.fitness)}</div><div class="meta">${s.new.includes(id)?'신규':'생존 유지'} · ${esc(n.operator)} · 부모 ${esc(n.parents.join(', ')||'없음')}</div><p>${esc(n.answer.ranking[0].item)}</p>${detail('가설 원문',n.answer.answer)}${detail('4개 평가 축',JSON.stringify(n.scores,null,2))}${n.judgments.map(j=>detail('비판 / '+j.judge,JSON.stringify({scores:j.scores,critique:j.critique},null,2))).join('')}${n.j1.length?detail('jev J1 판정',JSON.stringify(n.j1.map(j=>({answers:j.answers,weak:j.weak,would_rewrite:j.would_rewrite,needs_review:j.needs_review})),null,2)):''}${n.j2.length?detail('jev J2 진단',JSON.stringify(n.j2,null,2)):''}</article>`}).join('')}</section>`).join('');}
for(const id of ['case','method','arm'])document.getElementById(id).addEventListener('change',render);render();</script></html>'''
    (BASE / 'evolution-viewer.html').write_text(page.replace('__DATA__', data))


def write_plots(runs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    indexed = {(r['case'], r['method'], r['arm']): r for r in runs}
    fig, axes = plt.subplots(4, 2, figsize=(13, 15), sharex=True, sharey=True)
    for row, method in enumerate(METHODS):
        for col, case in enumerate(('als', 'aml')):
            ax = axes[row, col]
            for arm, color, shift in (('jev-on', '#c76717', 7), ('jev-off', '#226bb0', -15)):
                r = indexed[case, method, arm]; values = [s['fitness'] for s in r['stages']]
                label = arm.upper() + (' *' if r['used_supplement'] else '')
                ax.plot(range(4), values, marker='o', color=color, label=label, linewidth=2)
                for x, value in enumerate(values):
                    ax.annotate(f'{value:.4f}', (x, value), xytext=(0, shift), textcoords='offset points',
                                ha='center', color=color, fontsize=9)
            ax.set_title(case.upper() + ' / ' + LABELS[method], loc='left', fontsize=12)
            ax.set_ylim(.69, .91); ax.set_xlim(-.25, 3.25); ax.grid(alpha=.2); ax.legend(loc='lower left', fontsize=9)
            ax.set_xticks(range(4), ['G0', 'G1', 'G2', 'G3']); ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
            ax.set_ylabel('Internal critic fitness (zoomed axis)')
    fig.suptitle('ALS / AML: best candidate in each actual generation population', fontsize=16)
    fig.text(.05, .017, '* Supplemental completion after original failure; original statuses retained. One replicate; different initial outputs.\n'
             'No jev-triggered rewriting (0 / 72). Scores do not establish scientific validity or causal benefit. Y-axis zoom: 0.69–0.91.', fontsize=10)
    fig.tight_layout(rect=(0, .055, 1, .96))
    folder = ROOT / 'reports/figures'; folder.mkdir(exist_ok=True)
    for extension in ('svg', 'png'):
        fig.savefig(folder / f'2026-10-09-jev-controlled-evolution.{extension}', dpi=180)
    plt.close(fig)


def write_report(summary):
    runs = summary['runs']; accounting = summary['usage']; expert = summary['expert_review']
    lines = ['# ALS·AML 전체 재실행: jev ON/OFF 비교', '',
             '2026-10-09. **계획된 16개 조건의 최종 결과를 모두 확보했다.** 원래 실행 제한 안에서 13개가 완료됐고, '
             '실패한 3개는 별도 폴더에서 누락된 마지막 단계만 보완했다. 원본 실패 상태와 로그는 그대로 보존했다.', '',
             '이번 실험에서 **jev J1의 실제 재작성은 0회/72개 가설**이었다. 따라서 아래 점수 차이는 jev가 구조 결함을 수정한 효과를 입증하지 않는다. '
             '질문과 요청 seed는 같았지만 두 조건의 초기 답변부터 달랐다.', '',
             '## 실험 구성', '',
             'ALS·AML × 다중 모델·GPT 단독·Grok 단독·GLM Flash 단독 × jev ON/OFF = 16개. '
             'Opus·DeepSeek·Laya 호출은 없다. 조건별 한 번의 실행이며, ON 다음 OFF 순서였다. '
             '동일한 질문·문헌 패킷·프롬프트·모델 설정·요청 seed·진화 규칙을 사용했고 입력과 코드 SHA를 보존했다.', '',
             '각 실행은 초기 G0 가설 3개와 G1·G2·G3의 새 가설 각 2개, 총 9개를 만든다. 생존자는 가설 2개이며 모델 2개를 영구 선택하는 뜻은 아니다. '
             '다중 모델은 생존 2개에 변이 1개·교차 1개를 더한다. 단독 구성은 변이 2개를 더한다. '
             '새 가설마다 다중 구성은 작성자를 제외한 2모델, 단독 구성은 별도 호출의 자기 비판 2회로 채점한다. '
             '생존 가설은 기존 평가를 유지한다. G3의 실제 후보 4개 중 가장 높은 fitness를 반환한다.', '',
             '내부 fitness는 evidenceCoverage·specificity·novelty·actionability의 두 평가를 축별 중앙값으로 합친 가중 점수다. '
             '모델이나 평가 구성 사이에 공통 외부 채점 척도로 보정하지 않았으므로 다중·단독의 절대 점수만으로 우열을 판단하지 않는다.', '',
             '## 결과', '', '별표(*)는 원본 실패 뒤 마지막 단계만 별도 완료한 결과다. Δ는 최종−초기 1위이며, ON−OFF는 최종 값 차이다.', '',
             '| 과제 | 구성 | ON 초기→최종 | ON Δ | OFF 초기→최종 | OFF Δ | ON−OFF |',
             '|---|---|---:|---:|---:|---:|---:|']
    for c in summary['comparisons']:
        lines.append(f"| {c['case'].upper()} | {LABELS[c['method']]} | {c['on_initial']:.4f}→{c['on_final']:.4f}{'*' if c['on_supplement'] else ''} | {c['on_gain']:+.4f} | "
                     f"{c['off_initial']:.4f}→{c['off_final']:.4f}{'*' if c['off_supplement'] else ''} | {c['off_gain']:+.4f} | {c['on_minus_off']:+.4f} |")
    lines += ['', '다중 구성은 ALS에서 ON 0.0410, OFF 0.0095, AML에서 ON 0.0195, OFF 0.0095 상승했다. '
              'AML Grok ON과 GPT OFF는 초기 1위가 최종에도 그대로 선택돼 상승이 없었다. '
              'ON−OFF 차이가 양수인 경우와 음수인 경우가 함께 있으며, 동일한 시작 가설을 공유한 실험은 아니다. '
              '한 번의 실행·순차 조건 순서·공급자 응답 변동·일부 후속 보완이 있으므로 jev의 인과효과나 통계적 유의성을 주장하지 않는다.', '',
              '![세대별 점수](figures/2026-10-09-jev-controlled-evolution.png)', '',
              '그림은 각 세대의 실제 후보 집단에서 가장 높은 점수를 표시한다. 전체 과거 가설의 누적 최고값을 그린 것이 아니다. '
              '점수 변화를 읽기 위해 세로축을 0.69–0.91로 확대했으며, 원래 fitness 범위는 0–1이다.', '',
              '## 실패와 보완', '',
              '| 조건 | 원본 실패 | 보완 작업 |', '|---|---|---|',
              '| ON / ALS / GPT | 45분 상한: 마지막 가설의 평가 2회 누락 | 기존 9개 가설을 유지하고 평가 2회·jev J2 27회만 추가 |',
              '| ON / AML / Grok | 45분 상한: 마지막 평가 1회 누락 | 기존 9개 가설을 유지하고 평가 1회·jev J2 27회만 추가 |',
              '| OFF / ALS / GLM | G3 c009 구조화 응답 오류 | 성공한 기존 22개 호출을 정확히 재사용하고, 원래 예정된 c009 1개와 평가 4회만 보완 |', '',
              'GLM은 첫 보완(seed attempt 1)도 같은 응답 오류로 실패했다. 그 기록을 보존하고, HTTP 응답의 종료 사유·수치 사용량만 관찰하는 별도 보완 경로를 추가했다. '
              '형식 오류는 후보로 채택하지 않고 기존 형식 재시도 대상이 되도록 처리했다. '
              '실제 추가 writer attempt 2는 같은 모델·프롬프트·max_tokens 32768·effort로 정상 JSON을 반환했다. '
              '원래 두 실패의 응답 본문·종료 사유는 남아 있지 않아 길이 초과인지 JSON 미출력인지 단정할 수 없다. '
              '생성 조건을 바꾸거나 앞선 성공 답변을 새로 뽑지 않았고, 새 세대나 예정 외 가설도 추가하지 않았다.', '',
              '원본 ON/OFF 실행에는 코드 동결을 적용했다. 보완 코드는 별도 audit script에만 추가했으며 원본 엔진·설정·프로토콜은 바꾸지 않았다. '
              '보완은 원본 종료 후 진행했고 단계별 최대 15분, 누적 모델 40회/jev 70회, 최초 시작부터 전체 8시간 한도 안에서 수행했다. '
              '다만 실패 호출의 실제 토큰 사용량이 미확인이라 해당 세 실행의 원래 800k 토큰 상한 충족 여부를 정확히 검증할 수 없다.', '',
              '## jev 관측', '',
              f"ON J1 {summary['j1_records']}개, J2 {summary['j2_records']}개. 재작성 {summary['j1_actual_rewrites']}회, "
              f"미해결 판단 {summary['j1_needs_review']}개. 모든 ON 가설이 J1 구조 관문을 통과했다. '",
              'J1은 가설 존재 Noul, 우선 결함 Choice, 기전·근거 구분·검증 전략·반증 관찰 Score를 연결해 재작성 여부를 결정한다. '
              '임계값 0.5는 충분할 확률 P(2)+P(3)에 적용한다. jev 값은 가설의 사실성이나 실험 성공 확률이 아니다.', '',
              'J2는 수사적 강조와 비판 심각도를 진단해 기록했다. 정답 임상 결과 목록이 없어 outcome_mention은 건너뛰었다. '
              'J2는 생존 선택·fitness·재작성에 사용하지 않았다. OFF에는 jev 검사·진단 호출이 없다.', '',
              '실서비스에서 정상 구조의 실제 가설을 통과시키는 경로는 확인했다. 실제 가설의 결함을 고쳐 성능이 오르는지는 이번 실험에서 관측하지 못했다. '
              '이전 인위적 결함·수정 경로 검증은 [별도 보고서](2026-10-09-jev-combined.md)에 있다.', '',
              '## 실제 호출과 사용량', '', '| 구분 | 모델 호출 | jev 호출 | 보고된 토큰 합계 | 사용량 미확인 호출 |',
              '|---|---:|---:|---:|---:|']
    for arm in ('jev-on', 'jev-off'):
        m, j = accounting[arm]['model'], accounting[arm]['checker']
        lines.append(f"| {arm} (실패·보완 포함) | {m['backend_calls']} | {j['backend_calls']} | {m['reported_tokens'] + j['reported_tokens']:,} | {m['unknown_usage_calls'] + j['unknown_usage_calls']} |")
    lines += ['', f"총 {accounting['all']['backend_calls']}회, 보고된 토큰 {accounting['all']['reported_tokens']:,}개, "
              f"사용량 미확인 {accounting['all']['unknown_usage_calls']}회. 저장 답변의 재생은 새 호출·새 토큰으로 중복 합산하지 않았다. '",
              '토큰은 공급자 보고값이며 캐시·추론을 포함하는 사용량이다. 미확인 호출을 0토큰으로 간주하지 않았고, 정확한 비용이나 동등 연산량 비교를 주장하지 않는다.', '',
              '## 내용 검증과 전문가 평가', '',
              f"익명 전문가 자료는 {expert['stage_references']}개 초기/최종 참조, 중복 제거 후 {expert['unique_proposals']}개 답변으로 준비했다. "
              f"익명화 제외 {len(expert['excluded'])}개. 공개 패킷에 모델·ON/OFF·세대·fitness·비교 관계를 표시하지 않는다. '",
              '전문가는 공통 근거 패킷을 보고 grounding·causal rigor·specificity·testability·feasibility를 1–5로 평가하고 과제별 전체 순서를 작성할 수 있다. '
              '분석용 매핑은 별도 폴더에 있다. **실제 전문가 평가, 개별 인용 주장 확인, 약물 승인·노출 검증은 아직 수행되지 않았다.**', '',
              'Google co-scientist와의 후속 비교는 내부 점수 대신 최종 기전, 근거와 추측의 구분, 반증 가능한 예측, 검증 전략을 대상으로 해야 한다. '
              '현재 산출물은 그 내용 비교를 위한 입력이며 실험적 발견의 재현을 보여 준 자료는 아니다.', '',
              '## 전체 기록 보기', '',
              '- [한눈에 보는 진화 뷰어](../runs/jev-controlled-2026-10-09/evolution-viewer.html): 과제·구성·ON/OFF 선택, 모든 가설 원문·부모·점수·비판·jev 판정.',
              '- [144개 가설 점수 CSV](../runs/jev-controlled-2026-10-09/candidate-scores.csv), [64개 세대 점수 CSV](../runs/jev-controlled-2026-10-09/generation-scores.csv).',
              '- [보완을 구분한 전체 결과 JSON](../runs/jev-controlled-2026-10-09/completed-summary.json), [원본 비교](../runs/jev-controlled-2026-10-09/report.md).',
              '- [전문가용 패킷](../runs/jev-controlled-2026-10-09/completed-review-materials/expert/README.md): analyst 폴더를 함께 전달하지 않는다.',
              '- [목적·방법 문서](2026-10-09-reasonlineage-purpose-and-method.md).', '',
              '기존 증거 1,210개 파일의 SHA를 대조하고 공개 결과의 키·비공개 추론 포함 여부를 확인한다. '
              '검증 결과와 동결 입력·원본·보완 로그는 reports/evidence/2026-10-09-jev-controlled에 보존한다.', '']
    (ROOT / 'reports/2026-10-09-jev-controlled.md').write_text('\n'.join(lines).replace(". '\n", '.\n'))


def main():
    assert paired_plan(ROOT) == load(BASE / 'pair-plan.json'), 'original input / engine changed'
    runs = [read_run(arm, case, method) for arm in ('jev-on', 'jev-off') for case in ('als', 'aml') for method in METHODS]
    comparisons = []
    for case in ('als', 'aml'):
        for method in METHODS:
            a, b = (next(r for r in runs if (r['case'], r['method'], r['arm']) == (case, method, arm)) for arm in ('jev-on', 'jev-off'))
            comparisons.append({'case': case, 'method': method, 'on_initial': a['initial']['fitness'], 'on_final': a['final']['fitness'],
                                'on_gain': a['gain'], 'off_initial': b['initial']['fitness'], 'off_final': b['final']['fitness'],
                                'off_gain': b['gain'], 'on_minus_off': a['final']['fitness'] - b['final']['fitness'],
                                'on_original_status': a['original_status'], 'off_original_status': b['original_status'],
                                'on_supplement': a['used_supplement'], 'off_supplement': b['used_supplement']})
    accounting = {arm: {'model': total_usage(*(r['model_usage'] for r in runs if r['arm'] == arm)),
                        'checker': total_usage(*(r['checker_usage'] for r in runs if r['arm'] == arm))} for arm in ('jev-on', 'jev-off')}
    accounting['all'] = total_usage(*(v[k] for v in accounting.values() for k in ('model', 'checker')))
    summary = {'status': 'all_planned_results_obtained_with_supplements', 'compiled_utc': datetime.now(timezone.utc).isoformat(),
               'original_completed': sum(r['original_status'] == 'completed' for r in runs), 'supplement_completed': sum(r['used_supplement'] for r in runs),
               'planned_runs': 16, 'unique_hypotheses': sum(len(r['candidates']) for r in runs), 'judgments': sum(len(n['judgments']) for r in runs for n in r['candidates']),
               'j1_records': sum(r['j1_records'] for r in runs), 'j2_records': sum(r['j2_records'] for r in runs),
               'j1_actual_rewrites': sum(r['j1_actual_rewrites'] for r in runs), 'j1_needs_review': sum(r['j1_needs_review'] for r in runs),
               'single_replicate': True, 'deepseek_calls': 0, 'opus_calls': 0, 'laya_calls': 0,
               'usage': accounting, 'comparisons': comparisons, 'runs': runs}
    assert summary['unique_hypotheses'] == 144 and summary['judgments'] == 288
    summary['expert_review'] = expert_material(runs)
    save_json(BASE / 'completed-summary.json', public_data(summary))
    write_tables(runs, comparisons); write_viewer(summary); write_plots(runs); write_report(summary)
    print(json.dumps({k: summary[k] for k in ('status', 'original_completed', 'supplement_completed', 'unique_hypotheses', 'judgments', 'j1_records', 'j2_records', 'j1_actual_rewrites', 'usage', 'expert_review')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
