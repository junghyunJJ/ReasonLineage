import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'runs/jev-controlled-2026-10-09/jev-off/runs/als-glm'


def module():
    path=HERE/'planned_step_completion.py'
    assert path.exists(),'planned step completion not implemented'
    spec=importlib.util.spec_from_file_location('planned_step_completion',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def test_only_one_originally_planned_terminal_hypothesis_and_its_final_judgments_are_allowed():
    plan=module().planned_step_plan(SOURCE)
    assert plan['missing_generation']==['g3/mutate/c009/glm']
    assert plan['allowed_fresh_calls']==['g3/mutate/c009/glm','g3/judge/c008/glm-r0',
        'g3/judge/c008/glm-r1','g3/judge/c009/glm-r0','g3/judge/c009/glm-r1']
    assert plan['maximum_new_hypotheses']==1 and plan['new_generations']==0
    assert plan['original_model_calls']==23 and plan['original_unknown_usage_calls']==1
    assert plan['retry_seed_attempt']==1


def test_full_cache_replay_completes_only_original_missing_g3_steps(tmp_path,monkeypatch):
    import asyncio,json,shutil
    from datetime import datetime,timezone
    from reasonlineage.backends.base import ModelResponse
    from reasonlineage.engine.calls import derive_seed
    mod=module();dest=tmp_path/'pair';source=dest/'jev-off/runs/als-glm'
    shutil.copytree(SOURCE,source)
    shutil.copytree(ROOT/'runs/jev-controlled-2026-10-09/jev-off/frozen-inputs',dest/'jev-off/frozen-inputs')
    shutil.copyfile(ROOT/'runs/jev-controlled-2026-10-09/pair-plan.json',dest/'pair-plan.json')
    (dest/'pair-status.json').write_text(json.dumps({'status':'partial','started_utc':datetime.now(timezone.utc).isoformat()}))
    monkeypatch.setattr(mod,'DEST',dest)
    requests=[]
    class Service:
        name='fake'
        async def complete(self,request):
            requests.append(request)
            if 'answer' in request.json_schema['properties']:
                data={'answer':'A supported premise and explicitly speculative mechanism, controlled test and falsifying observation. '*40,
                      'ranking':[{'item':'Completed planned hypothesis','promisingness':.7,'confidence':.6,'pmids':[]}]}
            else:
                data={k:.9 for k in request.json_schema['properties'] if k!='critique'}
                data['critique']=['A public critique '+str(request.seed)]
            return ModelResponse('fake',request.model,json.dumps(data),data,.01,None,request.prompt_sha256,
                                 {'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}})
    monkeypatch.setattr(mod,'build_backend',lambda *a:Service())
    out=dest/'planned-step-completions/jev-off-als-glm'
    result=asyncio.run(mod.execute(source,out))
    assert result['status']=='planned_steps_complete'
    assert result['completed_planned_hypotheses']==1 and result['new_generations']==0
    assert len(requests)==5
    writers=[r for r in requests if 'answer' in r.json_schema['properties']]
    assert len(writers)==1
    assert writers[0].seed==derive_seed(20261006,'g3/mutate/c009/glm',1)
    assert result['new_model_usage']['backend_calls']==5
    assert not result['cumulative_token_cap_verified']
    assert json.loads((source/'status.json').read_text())['status']=='failed'
    events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    assert len([r for r in events if r['event']=='candidate.created'])==9
    assert len([r for r in events if r['event']=='judge.scored'])==18
