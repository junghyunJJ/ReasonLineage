"""Finish only originally planned G3 steps; replay all earlier successful calls exactly."""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import terminal_completion as terminal
from reasonlineage.engine.calls import CallRecorder
from reasonlineage.engine.events import EventLog,read_events
from reasonlineage.engine.config import Task,RunOptions,load_setup,build_backend
from reasonlineage.pilot.budget import Budget,MeteredBackend,public_data,safe_error
from reasonlineage.pilot.run import PilotRunner,SoloRunner,save_json
from reasonlineage.pilot.checker import MeteredChecker,live_checker
from reasonlineage.checks.gate import Gate
from reasonlineage.diagnose.j2 import run_j2
from reasonlineage.protocol import load_protocol
from reasonlineage.backends.base import BackendError,ModelResponse
from reasonlineage.backends.http import HttpBackend,clean_content,last_json_object
from reasonlineage.pilot.budget import _numeric_tree

ROOT,DEST=terminal.ROOT,terminal.DEST


def observe_structured_responses(service,destination):
    """Supplement only: retain usage for rejected JSON and allow the existing format retry.

    Never accept truncated data or retain private reasoning. No request setting changes.
    Original experiment engine and original failed outcomes remain frozen.
    """
    if not isinstance(service,HttpBackend):
        return service
    original_parse=service.parse
    def parse(payload,request,duration):
        choice=(payload.get('choices') or [{}])[0]
        message=choice.get('message') or {}
        text=clean_content(message.get('content') or '')
        diagnostic={'seed':request.seed,'max_tokens':request.max_tokens,
                    'finish_reason':choice.get('finish_reason'),
                    'content_characters':len(text),'structured_object_found':last_json_object(text) is not None,
                    'usage':_numeric_tree(payload.get('usage') or {})}
        try:
            result=original_parse(payload,request,duration)
            diagnostic['status']='parsed'
        except BackendError as error:
            value=str(error).lower()
            if request.json_schema is None or not any(word in value for word in ('structured','cut off','json')):
                raise
            diagnostic['status']='rejected'
            diagnostic['error_category']='output_limit' if choice.get('finish_reason')=='length' else 'missing_structured_object'
            result=ModelResponse(service.name,request.model,'',None,duration,None,request.prompt_sha256,
                                 {'usage':payload.get('usage') or {},'finish_reason':choice.get('finish_reason'),
                                  'served_model':payload.get('model')})
        with (Path(destination)/'response-diagnostics.jsonl').open('a') as stream:
            stream.write(json.dumps(public_data(diagnostic),ensure_ascii=False)+'\n')
        return result
    service.parse=parse
    return service


def planned_step_plan(source):
    source=Path(source);status=json.loads((source/'status.json').read_text())
    if status['status']!='failed' or not any(s in status.get('reason','').lower() for s in ('structured response','timeout')):
        raise ValueError('only interrupted planned steps are eligible')
    rows=read_events(source/'events.jsonl')
    early=[r for r in rows if r['event']=='judge.scored' and r['generation']<3]
    created=[r for r in rows if r['event']=='candidate.created']
    if len(early)!=14 or len([r for r in created if r['generation']<3])!=7:
        raise ValueError('all earlier generations must already be complete')
    writers=set()
    for path in (source/'calls/g3').glob('*/*/*.json'):
        name=path.relative_to(source/'calls').as_posix()[:-5]
        if name.split('/')[1] in ('mutate','cross'):
            writers.add(name)
    failed=[r for r in rows if r['event']=='call.failed' and r['name'].startswith('g3/')
            and r['name'].split('/')[1] in ('mutate','cross')]
    writers.update(r['name'] for r in failed)
    if len(writers)!=2:
        raise ValueError('only the two originally planned terminal writers may be completed')
    missing=sorted(n for n in writers if not (source/'calls'/f'{n}.json').exists())
    if not 1<=len(missing)<=2:
        raise ValueError('use terminal judgment completion when all hypotheses exist')
    header=status['header'];method=header['method'];roster=[r['name'] for r in header['models']]
    expected=[]
    for name in sorted(writers):
        _,_,cid,author=name.split('/')
        judges=[n for n in roster if n!=author] if method=='reasonlineage' else [method+'-r0',method+'-r1']
        expected.extend(f'g3/judge/{cid}/{judge}' for judge in judges)
    missing_judgments=[n for n in expected if not (source/'calls'/f'{n}.json').exists()]
    if status['usage']['backend_calls']>=40 or status['usage']['reported_tokens']>=800000:
        raise ValueError('original call/reportable token allowance exhausted')
    return {'source':str(source),'case':header['case'],'method':method,'missing_generation':missing,
            'allowed_fresh_calls':missing+missing_judgments,'maximum_new_hypotheses':len(missing),
            'new_generations':0,'original_model_calls':status['usage']['backend_calls'],
            'original_unknown_usage_calls':status['usage']['unknown_usage_calls'],
            'retry_seed_attempt':1,'original_failures':failed}


async def execute(source,destination,*,repair=False):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    marker=json.loads((DEST/'pair-status.json').read_text())
    if marker['status']=='running':
        raise ValueError('original pair must finish before step completion')
    remaining=28800-(time.time()-datetime.fromisoformat(marker['started_utc']).timestamp())
    if remaining<=60:
        raise ValueError('overall eight-hour allowance exhausted')
    plan=planned_step_plan(source);original=json.loads((source/'status.json').read_text())
    arm=source.parents[1].name
    if arm not in ('jev-on','jev-off') or not source.is_relative_to(DEST/arm/'runs'):
        raise ValueError('source must be from this experiment')
    prior=None;prior_usage={};prior_failures=[]
    if repair:
        if arm!='jev-off' or plan['case']!='als' or plan['method']!='glm':
            raise ValueError('diagnostic repair is limited to the failed OFF ALS GLM slot')
        prior=DEST/'planned-step-completions/jev-off-als-glm'
        prior_status=json.loads((prior/'status.json').read_text())
        if prior_status['status']!='partial' or prior_status.get('reason')!='invalid or truncated structured response':
            raise ValueError('only the preserved structured response failure is eligible')
        prior_plan=json.loads((prior/'completion-plan.json').read_text())
        if prior_plan['allowed_fresh_calls']!=plan['allowed_fresh_calls']:
            raise ValueError('previous completion allowlist differs')
        prior_usage=prior_status['new_model_usage']
        prior_failures=[r for r in read_events(prior/'events.jsonl') if r['event']=='call.failed' and not r.get('historical')]
        if len(prior_failures)!=1 or prior_failures[0]['attempt']!=1:
            raise ValueError('expected exactly one preserved failed supplemental attempt')
        plan['retry_seed_attempt']=2
        plan['supplemental_exception']='preserve JSON failure usage and apply existing at-most-one format retry'
        plan['maximum_additional_writer_attempts']=2
    canonical=DEST/('structured-completions' if repair else 'planned-step-completions')/f'{arm}-{plan["case"]}-{plan["method"]}'
    if destination!=canonical.resolve():
        raise ValueError('use the canonical one-time folder')
    paired=json.loads((DEST/'pair-plan.json').read_text())
    config=ROOT/'configs/co-scientist-rerun.json'
    if hashlib.sha256(config.read_bytes()).hexdigest()!=paired['arms'][arm]['config_sha256']:
        raise ValueError('model configuration changed')
    code=hashlib.sha256()
    for p in sorted((ROOT/'src/reasonlineage').rglob('*.py')):
        code.update(p.relative_to(ROOT).as_posix().encode()+b'\0'+p.read_bytes())
    if code.hexdigest()!=paired['arms'][arm]['code_sha256']:
        raise ValueError('original engine code changed')
    frozen=DEST/arm/'frozen-inputs/research/co-scientist-pilot'
    directory='protocol-jev-combined' if arm=='jev-on' else 'protocol-jev-control'
    protocol=load_protocol(frozen/directory)
    if protocol.hash!=original['header']['protocol_sha256']:
        raise ValueError('frozen protocol changed')
    question=(frozen/f'{plan["case"]}-evidence.md').read_text()
    setup=load_setup(config)
    destination.mkdir(parents=True,exist_ok=False);save_json(destination/'completion-plan.json',plan)
    events=EventLog(destination/'events.jsonl')
    for record in plan['original_failures']+prior_failures:
        # Carry failure counts only: continue the original retry seed, never repeat attempt 0.
        events.append_call('call.failed',**{k:v for k,v in record.items() if k not in ('event','ts','historical')},
                           historical=True)
    seconds=min(900,remaining-60)
    models=Budget(seconds=seconds,calls=40-plan['original_model_calls']-prior_usage.get('backend_calls',0),
                  tokens=800000-original['usage']['reported_tokens']-prior_usage.get('reported_tokens',0),lazy=True)
    old_checker=original.get('checker_usage',{}).get('backend_calls',0)
    checker_budget=Budget(seconds=seconds,calls=70-old_checker,tokens=None,lazy=True) if arm=='jev-on' else None
    shared=Budget(seconds=seconds,calls=models.calls+(checker_budget.calls if checker_budget else 0),tokens=None,lazy=True)
    members=setup.panel if plan['method']=='reasonlineage' else tuple(m for m in setup.panel if m.name==plan['method'])
    services={m.name:MeteredBackend(observe_structured_responses(build_backend(m,setup.concurrency),destination) if repair else build_backend(m,setup.concurrency),models,shared,
                                  concurrency=setup.concurrency) for m in members}
    recorder=CallRecorder(destination,events,protocol.data['pilot']['run_seed'],
                          replay=terminal.ExactReplay(source,plan['allowed_fresh_calls']),attempts=2,
                          retry_backend_errors=False,unusable_sanitizer=public_data)
    checked=MeteredChecker(live_checker(ROOT),checker_budget,shared,models,destination) if checker_budget else None
    runner_type=PilotRunner if plan['method']=='reasonlineage' else SoloRunner
    runner=runner_type(run_dir=destination,run_id='finish-original-planned-steps',
                      task=Task(plan['case'],question,None,'biomedical','public'),members=members,
                      backends=services,protocol=protocol,options=RunOptions(),events=events,recorder=recorder,
                      gate=Gate(destination,checked,protocol,question,'experiment',sources=[source]) if checked else None)
    outcome={'status':'partial','kind':'post_failure_planned_step_completion','source':str(source.relative_to(DEST)),
             'original_status':'failed','initial':original['initial'],'new_generations':0,
             'original_failure_retained':True}
    if repair:
        outcome.update(kind='post_failure_structured_response_completion',previous_completion=str(prior.relative_to(DEST)),
                       previous_completion_usage=prior_usage,previous_failure_retained=True,
                       request_settings_changed=False,decoder_exception=plan['supplemental_exception'])
    try:
        result=await runner.run();outcome['final']=result['best']
        if checked:
            diagnostics=await run_j2(destination,checked,protocol,question)
            rows=read_events(diagnostics)
            outcome['diagnostics']={'status':'completed' if all(not r.get('error') for r in rows) else 'partial','records':len(rows)}
            checks=read_events(destination/'checks.jsonl')
            outcome['j1']={'status':'partial' if any(r.get('error') or r.get('needs_review') for r in checks) else 'completed'}
        else:
            outcome['j1']={'status':'disabled'};outcome['diagnostics']={'status':'disabled'}
        outcome['status']='planned_steps_complete'
    except Exception as error:
        outcome['reason']=safe_error(error)
    rows=read_events(destination/'events.jsonl')
    fresh=[r for r in rows if r['event']=='call.completed' and not r.get('replayed')]
    if any(r['name'] not in plan['allowed_fresh_calls'] for r in fresh):
        raise ValueError('unplanned fresh call detected')
    outcome['completed_planned_hypotheses']=sum(r['name'] in plan['missing_generation'] for r in fresh)
    outcome['new_model_usage']=models.snapshot();outcome['new_checker_usage']=checker_budget.snapshot() if checker_budget else {'backend_calls':0,'reported_tokens':0,'unknown_usage_calls':0}
    outcome['new_total_usage']=shared.snapshot();outcome['original_model_usage']=original['usage'];outcome['original_checker_usage']=original.get('checker_usage',{})
    unknown=original['usage']['unknown_usage_calls']+prior_usage.get('unknown_usage_calls',0)+models.unknown
    outcome['cumulative_unknown_model_usage_calls']=unknown
    outcome['cumulative_token_cap_verified']=unknown==0 and original['usage']['reported_tokens']+prior_usage.get('reported_tokens',0)+models.reported_tokens<=800000
    save_json(destination/'status.json',outcome)
    print(json.dumps({k:outcome.get(k) for k in ('status','kind','completed_planned_hypotheses','new_generations',
                    'reason','new_model_usage','new_checker_usage','cumulative_token_cap_verified')},ensure_ascii=False),flush=True)
    return outcome


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--structured-repair',action='store_true');args=p.parse_args()
    try:
        result=asyncio.run(execute(args.source,args.out,repair=args.structured_repair));raise SystemExit(0 if result['status']=='planned_steps_complete' else 1)
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}));raise SystemExit(2)
