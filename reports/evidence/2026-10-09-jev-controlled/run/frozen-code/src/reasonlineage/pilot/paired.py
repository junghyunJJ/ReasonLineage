"""One bounded on/off comparison; no additional evaluators or retry controller."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..engine.events import read_events
from ..protocol import load_protocol
from .run import save_json
from .study import dry_plan
from .review import export_expert

METHODS=('reasonlineage','gpt','grok','glm')


def paired_plan(root):
    root=Path(root)
    on,off=dry_plan(root,combined=True),dry_plan(root,control=True)
    for key in ('schedule','models','config_sha256','evidence_sha256','code_sha256'):
        if on[key]!=off[key]:
            raise ValueError('paired inputs do not match: '+key)
    first=copy.deepcopy(load_protocol(root/'research/co-scientist-pilot'/on['protocol_directory']).data)
    second=copy.deepcopy(load_protocol(root/'research/co-scientist-pilot'/off['protocol_directory']).data)
    for spec in (first,second):
        spec.pop('version');spec['j1'].pop('enforce')
        spec['pilot'].pop('checker');spec['pilot'].pop('checker_call_limit')
    if first!=second:
        raise ValueError('paired protocols differ beyond checker activation')
    def prompts(plan):
        folder=root/'research/co-scientist-pilot'/plan['protocol_directory']/'prompts'
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.md')}
    if prompts(on)!=prompts(off):
        raise ValueError('paired prompts do not match')
    if on['independent_model'] is not None or off['independent_model'] is not None:
        raise ValueError('paired runs must not use DeepSeek')
    return {'arms':{'jev-on':on,'jev-off':off},'slots':16,'replicates_per_condition':1,
            'entry_script_sha256':{name:hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest()
                                   for name in ('run_co_scientist_pilot.py','run_jev_controlled_pilot.py')},
            'arm_order':['jev-on','jev-off'],'limits':{'total_seconds':28800,
             'total_calls':on['limits']['total_calls']+off['limits']['total_calls']},
            'shared_prompt_sha256':prompts(on),
            'interpretation':'Exploratory single-run comparison; identical requested seeds do not guarantee deterministic outputs.'}


def compare_studies(on,off):
    def index(study):
        return {(r['header']['case'],r['header']['method']):r for r in study.get('runs',[])}
    indexed=index(on),index(off)
    rows=[]
    for case in ('als','aml'):
        for method in METHODS:
            arms=[]
            for source in indexed:
                result=source.get((case,method),{'status':'unstarted'})
                initial=result.get('initial',{}).get('fitness')
                final=result.get('final',{}).get('fitness')
                arms.append({'status':result['status'],'initial_fitness':initial,'final_fitness':final,
                             'evolution_gain':final-initial if initial is not None and final is not None else None,
                             'j1':result.get('j1',{}),'diagnostics':result.get('diagnostics',{}),
                             'model_usage':result.get('usage',{}),'checker_usage':result.get('checker_usage',{}),
                             'reason':result.get('reason')})
            a,b=arms
            both=a['status']==b['status']=='completed' and a['final_fitness'] is not None and b['final_fitness'] is not None
            verified=(both and a['j1'].get('status')=='completed' and a['diagnostics'].get('status')=='completed'
                      and b['j1'].get('status')=='disabled' and b['diagnostics'].get('status')=='disabled')
            rows.append({'case':case,'method':method,'on':a,'off':b,'both_generated':both,
                         'fully_verified':verified,
                         'final_fitness_on_minus_off':a['final_fitness']-b['final_fitness'] if both else None})
    return rows


def _read_study(folder):
    path=folder/'study.json'
    if path.exists():
        return json.loads(path.read_text())
    if not folder.exists():
        return {}
    recovered=[]
    for run in sorted((folder/'runs').glob('*')):
        if not run.is_dir():
            continue
        durable=run/'status.json'
        if durable.exists():
            recovered.append(json.loads(durable.read_text()))
            continue
        case,_,method=run.name.partition('-')
        if case in ('als','aml') and method in METHODS:
            header=run/'header.json'
            recovered.append({'header':json.loads(header.read_text()) if header.exists() else {'case':case,'method':method},
                              'status':'cutoff','reason':'supervised interruption; terminal slot status unavailable'})
    return {'runs':recovered,'aggregate_missing':True,
            'usage':{'status':'unavailable','reason':'aggregate missing; durable per-slot records preserved'},
            'study_error':'study aggregate missing after interruption'}


def _write_report(path,summary):
    def number(value):
        return '—' if value is None else f'{value:.4f}'
    text=['# jev on/off ALS·AML 전체 비교','',
          '조건별 한 번의 탐색적 실행이다. jev가 없는 군에서도 DeepSeek를 사용하지 않는다. ',
          '동일한 질문·모델·프롬프트·seed·진화조건을 사용하되, 공급자 응답의 결정성은 보장하지 않는다. ',
          '순차 실행 순서와 추가 검사/수정 비용도 차이의 해석에 고려해야 한다.','',
          f"전체 생성 완료: {summary['generation_completed']}/16. J1/J2까지 확인된 비교 쌍: {summary['verified_pairs']}/8.",'',
          '| 과제 | 구성 | jev on 상태 | off 상태 | on 최종 | off 최종 | on−off | 검사까지 확인 |',
          '|---|---|---|---|---:|---:|---:|---|']
    for row in summary['comparisons']:
        text.append(f"| {row['case'].upper()} | {row['method']} | {row['on']['status']} | {row['off']['status']} | "
                    f"{number(row['on']['final_fitness'])} | {number(row['off']['final_fitness'])} | "
                    f"{number(row['final_fitness_on_minus_off'])} | {'예' if row['fully_verified'] else '아니오'} |")
    text.extend(['','점수는 실행 내부 비판 모델의 fitness이며 과학적 사실성·실험 성공률을 뜻하지 않는다.',
                 '문헌 주장 확인과 전문가의 내용 평가는 별도이며 아직 완료되지 않았다.','',
                 '## 실제 사용량','', '| 조건 | 총 호출 | 보고 토큰 | 사용량 미확인 호출 |',
                 '|---|---:|---:|---:|'])
    for arm,value in summary['usage'].items():
        text.append(f"| {arm} | {value.get('backend_calls','—')} | {value.get('reported_tokens','—')} | {value.get('unknown_usage_calls','—')} |")
    text.extend(['',f"기록 폴더: `{summary['directory']}`. 각 슬롯의 `events.jsonl`, `calls/`, `status.json`에 전체 진화·공개 프롬프트·응답을 저장했다.",
                 'jev on에는 `checks.jsonl`, `checker-calls.jsonl`, `diagnostics/`가 추가된다. off는 checker를 호출하지 않는다.',
                 '실패·부분검사·미시작도 그대로 포함하며 정상완료로 바꾸지 않는다. 기존 실험 결과는 보존한다.',''])
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(text),encoding='utf-8')


def run_pair(destination,root,*,launch=None):
    destination,root=Path(destination).resolve(),Path(root).resolve()
    plan=paired_plan(root)
    destination.mkdir(parents=True,exist_ok=False)
    save_json(destination/'pair-plan.json',plan)
    for p in sorted((root/'src/reasonlineage').rglob('*.py')):
        target=destination/'frozen-code'/p.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    for name in ('run_co_scientist_pilot.py','run_jev_controlled_pilot.py'):
        target=destination/'frozen-code/scripts'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/'scripts'/name,target)
    launched=launch or subprocess.run
    status={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),'arms':{}}
    for arm in plan['arm_order']:
        current=paired_plan(root)
        if current!=plan:
            status.update(status='stopped',reason='inputs or code changed after freezing')
            save_json(destination/'pair-status.json',status)
            break
        status['active_arm']=arm
        status['arms'][arm]={'status':'running'}
        save_json(destination/'pair-status.json',status)
        flag='--jev-combined' if arm=='jev-on' else '--jev-control'
        command=[sys.executable,'-B',str(root/'scripts/run_co_scientist_pilot.py'),flag,'--run','--out',str(destination/arm)]
        print('Starting paired arm: '+arm,flush=True)
        with (destination/f'{arm}.log').open('w',encoding='utf-8') as log:
            result=launched(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        study=_read_study(destination/arm)
        status['arms'][arm]={'status':'recorded' if study else 'failed','exit_code':result.returncode,
                            'generated':sum(r['status']=='completed' for r in study.get('runs',[])),
                            'study_error':study.get('study_error')}
        save_json(destination/'pair-status.json',status)
        print(f"Recorded {arm}: exit {result.returncode}, {status['arms'][arm]['generated']}/8 generated",flush=True)
    on,off=(_read_study(destination/arm) for arm in ('jev-on','jev-off'))
    comparisons=compare_studies(on,off)
    summary={'directory':str(destination.relative_to(root)) if destination.is_relative_to(root) else str(destination),
             'comparisons':comparisons,'generation_completed':sum(r['status']=='completed' for s in (on,off) for r in s.get('runs',[])),
             'verified_pairs':sum(r['fully_verified'] for r in comparisons),
             'usage':{'jev-on':on.get('usage',{}),'jev-off':off.get('usage',{})},
             'complete':all(r['fully_verified'] for r in comparisons),'single_replicate':True,
             'deepseek_calls':0,'expert_status':'pending','arm_order':plan['arm_order']}
    for row in comparisons:
        for label,arm in (('on','jev-on'),('off','jev-off')):
            events=read_events(destination/arm/'runs'/f"{row['case']}-{row['method']}"/'events.jsonl')
            row[label]['rewrites']=sum(e.get('event')=='call.completed' and '/rewrite/' in e.get('name','') for e in events)
    save_json(destination/'comparison.json',summary)
    status.update(status='completed' if summary['complete'] else 'partial',active_arm=None,
                  finished_utc=datetime.now(timezone.utc).isoformat(),generation_completed=summary['generation_completed'],
                  verified_pairs=summary['verified_pairs'])
    save_json(destination/'pair-status.json',status)
    statuses=[]
    for arm,study in (('jev-on',on),('jev-off',off)):
        for result in study.get('runs',[]):
            item=copy.deepcopy(result);item['header']['method']=arm+'/'+item['header']['method'];statuses.append(item)
    evidence={}
    for case in ('als','aml'):
        paths=[destination/arm/f'frozen-inputs/research/co-scientist-pilot/{case}-evidence.md'
               for arm in ('jev-on','jev-off')]
        paths.append(root/f'research/co-scientist-pilot/{case}-evidence.md')
        evidence[case]=next(path for path in paths if path.exists()).read_text()
    export_expert(destination/'paired-review-materials',statuses,evidence)
    _write_report(destination/'report.md',summary)
    print(f"Pair recorded: {summary['generation_completed']}/16 generated; {summary['verified_pairs']}/8 fully verified pairs",flush=True)
    return summary
