"""Post-run terminal judgments only; original cutoff and all hypotheses stay intact."""
import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
DEST=ROOT/'runs/jev-controlled-2026-10-09'
sys.path.insert(0,str(ROOT/'src'))
from reasonlineage.backends.base import ModelRequest
from reasonlineage.core.fitness import median_scores,composite_fitness
from reasonlineage.diagnose.j2 import run_j2
from reasonlineage.engine.calls import CallRecorder,cache_key
from reasonlineage.engine.config import load_setup,build_backend,Task,RunOptions
from reasonlineage.engine.events import EventLog,read_events
from reasonlineage.engine.runner import gather_all
from reasonlineage.pilot.budget import Budget,MeteredBackend,public_data,safe_error
from reasonlineage.pilot.checker import MeteredChecker,live_checker
from reasonlineage.pilot.run import PilotRunner,SoloRunner,save_json
from reasonlineage.protocol import load_protocol


def terminal_plan(source):
    source=Path(source)
    status=json.loads((source/'status.json').read_text())
    if status['status']!='failed' or 'timeout' not in status.get('reason','').lower():
        raise ValueError('only a failed timeout case is eligible')
    rows=read_events(source/'events.jsonl')
    candidates={r['id']:r for r in rows if r['event']=='candidate.created'}
    if len(candidates)!=9 or len([r for r in candidates.values() if r['generation']==3])!=2:
        raise ValueError('terminal generation is incomplete; no additional generation is allowed')
    early=[r for r in rows if r['event']=='judge.scored' and r['generation']<3]
    if len(early)!=14:
        raise ValueError('earlier generation scoring is incomplete')
    selections=[r for r in rows if r['event']=='selection' and r['generation']==2]
    if len(selections)!=1:
        raise ValueError('terminal population cannot be recovered')
    header=status['header'];method=header['method']
    population=selections[0]['survivors']+[r['id'] for r in candidates.values() if r['generation']==3]
    roster=[r['name'] for r in header['models']]
    expected=[]
    for cid in population[2:]:
        judges=([name for name in roster if name!=candidates[cid]['author']]
                if method=='reasonlineage' else [method+'-r0',method+'-r1'])
        expected.extend(f'g3/judge/{cid}/{judge}' for judge in judges)
    missing=[name for name in expected if not (source/'calls'/f'{name}.json').exists()]
    if not missing or len(missing)>4:
        raise ValueError('no bounded missing terminal judgments')
    usage=status['usage']
    if usage['backend_calls']>=40 or usage['reported_tokens']>=800000:
        raise ValueError('original model allowance is exhausted')
    return {'source':str(source),'case':header['case'],'method':method,'expected':expected,
            'missing':missing,'population':population,'candidates':candidates,
            'generation_calls_allowed':0,'original_model_calls':usage['backend_calls'],
            'original_unknown_usage_calls':usage['unknown_usage_calls'],
            'source_status_sha256':hashlib.sha256((source/'status.json').read_bytes()).hexdigest()}


class ExactReplay:
    def __init__(self,source,allowed_missing=()):
        self.source=Path(source)
        self.allowed_missing=set(allowed_missing)
    def take(self,key,name):
        path=self.source/'calls'/f'{name}.json'
        if not path.exists():
            return None
        stored=json.loads(path.read_text());request=dict(stored['request']);member=request.pop('member')
        if cache_key(member,ModelRequest(**request))!=key:
            raise ValueError('cached terminal request does not match frozen inputs')
        return stored
    def requires(self,name):
        return name not in self.allowed_missing
    def mark_used(self,key,name):
        pass


class CriticOnly:
    def __init__(self,service):
        self.service=service;self.name=service.name
    async def complete(self,request):
        if 'answer' in request.json_schema.get('properties',{}):
            raise ValueError('new hypotheses are prohibited')
        return await self.service.complete(request)


async def execute(source,destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    marker=json.loads((DEST/'pair-status.json').read_text())
    if marker['status']=='running':
        raise ValueError('wait until the original pair finishes; do not compete with live model chains')
    started=datetime.fromisoformat(marker['started_utc']).timestamp()
    remaining=28800-(time.time()-started)
    if remaining<=60:
        raise ValueError('original overall eight-hour allowance exhausted')
    plan=terminal_plan(source);original=json.loads((source/'status.json').read_text())
    arm=source.parents[1].name
    if arm not in ('jev-on','jev-off') or not source.is_relative_to(DEST/arm/'runs'):
        raise ValueError('source must belong to this paired experiment')
    protocol_directory='protocol-jev-combined' if arm=='jev-on' else 'protocol-jev-control'
    frozen=DEST/arm/'frozen-inputs/research/co-scientist-pilot'
    protocol=load_protocol(frozen/protocol_directory)
    if protocol.hash!=original['header']['protocol_sha256']:
        raise ValueError('frozen protocol changed')
    question=(frozen/f'{plan["case"]}-evidence.md').read_text()
    setup=load_setup(ROOT/'configs/co-scientist-rerun.json')
    config_digest=hashlib.sha256((ROOT/'configs/co-scientist-rerun.json').read_bytes()).hexdigest()
    original_plan=json.loads((DEST/'pair-plan.json').read_text())
    if config_digest!=original_plan['arms'][arm]['config_sha256']:
        raise ValueError('original model configuration changed')
    code_digest=hashlib.sha256()
    for path in sorted((ROOT/'src/reasonlineage').rglob('*.py')):
        code_digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes())
    if code_digest.hexdigest()!=original_plan['arms'][arm]['code_sha256']:
        raise ValueError('original engine code changed')
    canonical=DEST/'terminal-completions'/f'{arm}-{plan["case"]}-{plan["method"]}'
    if destination!=canonical.resolve():
        raise ValueError('use the canonical one-time completion folder')
    destination.mkdir(parents=True,exist_ok=False)
    save_json(destination/'terminal-plan.json',plan)
    shutil.copytree(source/'calls',destination/'calls')
    if (source/'checks.jsonl').exists():
        shutil.copyfile(source/'checks.jsonl',destination/'checks.jsonl')
    retained=[r for r in read_events(source/'events.jsonl') if r['event'] not in ('call.completed','call.failed','run.stopped','judge.scored')
              or r['event']=='judge.scored' and r.get('generation',0)<3]
    events=EventLog(destination/'events.jsonl')
    # Preserve observations on disk without creating a resume decision cursor.
    (destination/'events.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in retained))
    events.emit('terminal_completion.started',source=str(source),new_generation_calls=0)
    seconds=min(900,remaining-60)
    models=Budget(seconds=seconds,calls=min(40-plan['original_model_calls'],2*len(plan['missing'])),
                  tokens=800000-original['usage']['reported_tokens'],lazy=True)
    checker_calls=original.get('checker_usage',{}).get('backend_calls',0)
    shared=Budget(seconds=seconds,calls=models.calls+(70-checker_calls if arm=='jev-on' else 0),tokens=None,lazy=True)
    checker_budget=Budget(seconds=seconds,calls=70-checker_calls,tokens=None,lazy=True) if arm=='jev-on' else None
    members=setup.panel if plan['method']=='reasonlineage' else tuple(m for m in setup.panel if m.name==plan['method'])
    needed={name.rsplit('/',1)[-1].split('-r')[0] for name in plan['missing']}
    backends={m.name:MeteredBackend(CriticOnly(build_backend(m,setup.concurrency)),models,shared,
                                  concurrency=setup.concurrency) for m in members if m.name in needed}
    recorder=CallRecorder(destination,events,protocol.data['pilot']['run_seed'],replay=ExactReplay(source,plan['missing']),
                          attempts=2,retry_backend_errors=False,unusable_sanitizer=public_data)
    runner_type=PilotRunner if plan['method']=='reasonlineage' else SoloRunner
    runner=runner_type(run_dir=destination,run_id='terminal-only-completion',
                       task=Task(plan['case'],question,None,'biomedical','public'),members=members,
                       backends=backends,protocol=protocol,options=RunOptions(),events=events,recorder=recorder)
    if plan['method']!='reasonlineage':
        for i in range(2):
            alias=plan['method']+f'-r{i}'
            runner.members[alias]=runner.members[plan['method']]
            runner.backends[alias]=backends[plan['method']]
    runner.answers={cid:r['answer'] for cid,r in plan['candidates'].items()}
    scores={r['candidate']:r for r in read_events(source/'events.jsonl') if r['event']=='candidate.scored'}
    outcome={'status':'partial','kind':'post_cutoff_terminal_evaluation','original_status':'failed',
             'source':str(source.relative_to(DEST)),'plan':{k:v for k,v in plan.items() if k!='candidates'},
             'generation_calls':0,'initial':original['initial'],'j1':original.get('j1',{}),
             'cumulative_token_cap_verified':original['usage']['unknown_usage_calls']==0}
    try:
        jobs=[]
        for name in plan['expected']:
            cid,judge=name.split('/')[2:]
            if judge not in runner.backends:
                runner.backends[judge]=next(iter(backends.values()))
            jobs.append((cid,judge))
        results=await gather_all(runner._judge(3,SimpleNamespace(id=cid,author=plan['candidates'][cid]['author']),
                                             judge,'') for cid,judge in jobs)
        for cid in plan['population'][2:]:
            candidate=SimpleNamespace(id=cid,author=plan['candidates'][cid]['author'])
            panels=[panel for (job_cid,_),panel in zip(jobs,results) if job_cid==cid]
            for panel in panels:
                judge=panel.judge
                events.emit('judge.scored',candidate=cid,judge=judge,author=candidate.author,generation=3,
                            judges_axis='fresh_self_critic' if plan['method']!='reasonlineage' else 'cross',
                            context='isolated',scores=dict(panel.scores),critique=list(panel.critique),
                            post_cutoff_completion=True)
            median=median_scores([p.scores for p in panels],list(runner.task.weights))
            fitness=composite_fitness(median,runner.task.weights)
            scores[cid]={'scores':median,'fitness':fitness}
            events.emit('candidate.scored',candidate=cid,judges=[p.judge for p in panels],scores=median,fitness=fitness,
                        post_cutoff_completion=True)
        winner=max(plan['population'],key=lambda cid:scores[cid]['fitness'])
        outcome['final']={'id':winner,'author':plan['candidates'][winner]['author'],
                          'fitness':scores[winner]['fitness'],'scores':scores[winner]['scores'],
                          'answer':runner.answers[winner]}
        if arm=='jev-on':
            checked=MeteredChecker(live_checker(ROOT),checker_budget,shared,models,destination)
            diagnostics=await run_j2(destination,checked,protocol,question)
            records=read_events(diagnostics)
            outcome['diagnostics']={'status':'completed' if all(not r.get('error') for r in records) else 'partial',
                                    'records':len(records)}
        else:
            outcome['diagnostics']={'status':'disabled'}
        outcome['status']='evaluation_complete'
    except Exception as error:
        outcome['reason']=safe_error(error)
    outcome['new_model_usage']=models.snapshot()
    outcome['new_checker_usage']=checker_budget.snapshot() if checker_budget else {'backend_calls':0,'reported_tokens':0,'unknown_usage_calls':0}
    outcome['new_total_usage']=shared.snapshot()
    outcome['original_model_usage']=original['usage']
    outcome['original_checker_usage']=original.get('checker_usage',{})
    outcome['original_timeout_retained']=True
    unknown=original['usage']['unknown_usage_calls']+outcome['new_model_usage']['unknown_usage_calls']
    known_tokens=original['usage']['reported_tokens']+outcome['new_model_usage']['reported_tokens']
    outcome['cumulative_unknown_model_usage_calls']=unknown
    outcome['cumulative_token_cap_verified']=unknown==0 and known_tokens<=800000
    outcome['reported_token_usage_complete']=unknown==0
    save_json(destination/'status.json',outcome)
    print(json.dumps({k:outcome.get(k) for k in ('status','kind','generation_calls','reason',
                    'new_model_usage','new_checker_usage','cumulative_token_cap_verified')},ensure_ascii=False),flush=True)
    return outcome


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=asyncio.run(execute(args.source,args.out));raise SystemExit(0 if result['status']=='evaluation_complete' else 1)
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}));raise SystemExit(2)
