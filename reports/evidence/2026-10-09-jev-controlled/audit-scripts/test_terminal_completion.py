import importlib.util
import json
from pathlib import Path

import pytest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'runs/jev-controlled-2026-10-09/jev-on/runs/als-gpt'


def module():
    path=HERE/'terminal_completion.py'
    assert path.exists(),'terminal-only completion policy not implemented'
    spec=importlib.util.spec_from_file_location('terminal_completion',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_saved_case_allows_only_two_missing_terminal_judgments_and_no_generation():
    plan=module().terminal_plan(SOURCE)
    assert plan['missing']==['g3/judge/c009/gpt-r0','g3/judge/c009/gpt-r1']
    assert plan['generation_calls_allowed']==0
    assert len(plan['population'])==4 and len(plan['candidates'])==9
    assert plan['original_model_calls']==27 and plan['original_unknown_usage_calls']==2


def test_incomplete_terminal_generation_is_rejected(tmp_path):
    folder=tmp_path/'incomplete';folder.mkdir()
    for name in ('status.json','header.json'):
        (folder/name).write_bytes((SOURCE/name).read_bytes())
    rows=[json.loads(s) for s in (SOURCE/'events.jsonl').read_text().splitlines()]
    (folder/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows
                      if not (r['event']=='candidate.created' and r['id']=='c009'))+'\n')
    with pytest.raises(ValueError,match='generation'):
        module().terminal_plan(folder)


def test_completed_case_is_never_selected_for_extra_scoring():
    with pytest.raises(ValueError,match='timeout'):
        module().terminal_plan(SOURCE.with_name('als-glm'))


def test_replay_uses_exact_call_name_and_rejects_changed_requests():
    from reasonlineage.backends.base import ModelRequest
    from reasonlineage.engine.calls import cache_key
    name='g3/judge/c008/gpt-r0'
    stored=json.loads((SOURCE/'calls'/f'{name}.json').read_text())
    request=dict(stored['request']);member=request.pop('member')
    replay=module().ExactReplay(SOURCE,['g3/judge/c009/gpt-r0'])
    key=cache_key(member,ModelRequest(**request))
    assert replay.take(key,name)==stored
    assert replay.take(key,'g3/judge/c009/gpt-r0') is None
    request['prompt']+=' altered'
    with pytest.raises(ValueError,match='does not match'):
        replay.take(cache_key(member,ModelRequest(**request)),name)
    assert replay.requires(name) and not replay.requires('g3/judge/c009/gpt-r0')


def test_live_backend_forbids_new_hypotheses_even_if_called_accidentally():
    import asyncio
    from types import SimpleNamespace
    class Never:
        name='test'
        async def complete(self,request):
            raise AssertionError('must not reach provider')
    with pytest.raises(ValueError,match='prohibited'):
        asyncio.run(module().CriticOnly(Never()).complete(SimpleNamespace(json_schema={'properties':{'answer':{}}})))


@pytest.mark.parametrize('fail_new',[False,True])
def test_full_completion_path_preserves_observations_and_unknown_usage(tmp_path,monkeypatch,fail_new):
    import asyncio,shutil
    from datetime import datetime,timezone
    from reasonlineage.backends.base import ModelResponse,BackendError
    from reasonlineage.checks.base import CheckAnswer,CheckResult
    from reasonlineage.checks.calibration import VERSION
    mod=module();dest=tmp_path/'pair';source=dest/'jev-on/runs/als-gpt'
    shutil.copytree(SOURCE,source)
    status=json.loads((source/'status.json').read_text())
    status['usage']['unknown_usage_calls']=0
    (source/'status.json').write_text(json.dumps(status))
    shutil.copytree(ROOT/'runs/jev-controlled-2026-10-09/jev-on/frozen-inputs',dest/'jev-on/frozen-inputs')
    shutil.copyfile(ROOT/'runs/jev-controlled-2026-10-09/pair-plan.json',dest/'pair-plan.json')
    (dest/'pair-status.json').write_text(json.dumps({'status':'partial','started_utc':datetime.now(timezone.utc).isoformat()}))
    monkeypatch.setattr(mod,'DEST',dest)
    requests=[]
    class Service:
        name='fake'
        async def complete(self,request):
            requests.append(request)
            assert 'answer' not in request.json_schema['properties']
            if fail_new:
                raise BackendError('backend timeout')
            # Use exact schema dimensions rather than assume their names.
            data={k:.9 for k in request.json_schema['properties'] if k!='critique'}
            data['critique']=['A public scientific critique '+str(request.seed)]
            return ModelResponse('fake',request.model,json.dumps(data),data,.01,None,request.prompt_sha256,
                                 {'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}})
    class Checker:
        name,pinned_version='jev',VERSION
        async def ask(self,state,questions):
            result={q.name:CheckAnswer(q.kind,{'0':1.0} if q.kind=='score' else {q.choices[0][0]:1.0}) for q in questions}
            return CheckResult(VERSION,result,{'input_tokens':10,'output_tokens':10})
    monkeypatch.setattr(mod,'build_backend',lambda *a:Service())
    monkeypatch.setattr(mod,'live_checker',lambda *a:Checker())
    out=dest/'terminal-completions/jev-on-als-gpt'
    result=asyncio.run(mod.execute(source,out))
    assert result['generation_calls']==0 and result['original_timeout_retained']
    assert json.loads((source/'status.json').read_text())['status']=='failed'
    if fail_new:
        assert 1<=len(requests)<=2
        assert result['status']=='partial'
        assert result['new_model_usage']['unknown_usage_calls']>0
        assert not result['cumulative_token_cap_verified']
    else:
        assert len(requests)==2
        assert result['status']=='evaluation_complete'
        assert result['diagnostics']['records']==27
        assert result['new_model_usage']['backend_calls']==2
        assert result['cumulative_token_cap_verified']
