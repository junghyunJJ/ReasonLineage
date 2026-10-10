import asyncio
import copy
import json
import subprocess
import sys

import pytest

from reasonlineage.engine.config import load_setup
from reasonlineage.pilot import study
from reasonlineage.protocol import load_protocol
from test_pilot_run import ROOT
from test_pilot_jev_gate import UniqueBackend
from test_pilot_jev_combined import CombinedChecker


def test_control_plan_disables_checker_and_independent_evaluator_but_matches_on_inputs():
    on=study.dry_plan(ROOT,combined=True)
    off=study.dry_plan(ROOT,control=True)
    assert off['control'] and not off['jev']
    assert off['independent_model'] is None and off['limits']['max_checker_calls']==0
    assert off['limits']['total_calls']==324
    assert on['schedule']==off['schedule'] and len(off['schedule'])==8
    for key in ('models','config_sha256','evidence_sha256','code_sha256'):
        assert on[key]==off[key]
    for key in ('run_seconds','run_tokens','max_run_calls','run_calls','total_seconds','generation_seconds'):
        assert on['limits'][key]==off['limits'][key]
    first=copy.deepcopy(load_protocol(ROOT/'research/co-scientist-pilot/protocol-jev-combined').data)
    second=copy.deepcopy(load_protocol(ROOT/'research/co-scientist-pilot/protocol-jev-control').data)
    for p in (first,second):
        p.pop('version');p['j1'].pop('enforce');p['pilot'].pop('checker');p['pilot'].pop('checker_call_limit')
    assert first==second
    for name in ('seed','mutate','crossover','rewrite','author_system','judge_system','judge_candidate'):
        a=(ROOT/'research/co-scientist-pilot/protocol-jev-combined/prompts'/f'{name}.md').read_bytes()
        b=(ROOT/'research/co-scientist-pilot/protocol-jev-control/prompts'/f'{name}.md').read_bytes()
        assert a==b


def test_control_full_study_has_zero_jev_deepseek_and_matching_initial_request(tmp_path,monkeypatch):
    def forbidden(*a,**k):
        raise AssertionError('control cannot construct jev or DeepSeek')
    monkeypatch.setattr(study,'live_checker',forbidden)
    monkeypatch.setattr(study,'evaluator_member',forbidden)
    monkeypatch.setattr(study,'independent_reviews',forbidden)
    setup=load_setup(ROOT/'configs/co-scientist-rerun.json')
    off_services={m.name:UniqueBackend(m.name) for m in setup.panel}
    off=asyncio.run(study.run_study(tmp_path/'off',ROOT,control=True,setup=setup,services=off_services))
    assert len(off['runs'])==8 and all(r['status']=='completed' for r in off['runs'])
    assert off['independent_status']=='disabled_by_config' and off['independent_evaluations']==[]
    assert off['usage']['backend_calls']==216
    assert all(r['j1']['status']=='disabled' and r['diagnostics']['status']=='disabled' for r in off['runs'])
    assert not list((tmp_path/'off').rglob('checker-calls.jsonl'))
    on_services={m.name:UniqueBackend(m.name) for m in setup.panel}
    on=asyncio.run(study.run_study(tmp_path/'on',ROOT,combined=True,setup=setup,
                                  services=on_services,checker=CombinedChecker()))
    assert all(r['status']=='completed' for r in on['runs'])
    for name in off_services:
        a,b=off_services[name].requests[0],on_services[name].requests[0]
        assert (a.system,a.prompt,a.seed,a.model,a.effort,a.json_schema)==(b.system,b.prompt,b.seed,b.model,b.effort,b.json_schema)


def test_control_cli_is_dry_by_default_and_rejects_on_off_mix(tmp_path):
    out=tmp_path/'never-created'
    command=[sys.executable,str(ROOT/'scripts/run_co_scientist_pilot.py')]
    result=subprocess.run(command+['--jev-control','--out',str(out)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['control'] and not out.exists()
    assert subprocess.run(command+['--jev-control','--jev-combined'],capture_output=True).returncode!=0


@pytest.mark.parametrize('flag',('jev','combined'))
def test_control_and_on_modes_are_mutually_exclusive(flag):
    with pytest.raises(ValueError,match='mutually exclusive'):
        study.dry_plan(ROOT,control=True,**{flag:True})


def test_paired_plan_has_sixteen_slots_and_dry_command_makes_no_folder(tmp_path):
    from reasonlineage.pilot.paired import paired_plan
    plan=paired_plan(ROOT)
    assert plan['slots']==16 and plan['limits']['total_calls']==1208
    assert plan['limits']['total_seconds']==28800
    out=tmp_path/'not-created'
    result=subprocess.run([sys.executable,str(ROOT/'scripts/run_jev_controlled_pilot.py'),
                           '--out',str(out)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['slots']==16 and not out.exists()


def test_pair_plan_also_binds_the_actual_entry_scripts():
    import hashlib
    from reasonlineage.pilot.paired import paired_plan
    plan=paired_plan(ROOT)
    for name in ('run_co_scientist_pilot.py','run_jev_controlled_pilot.py'):
        assert plan['entry_script_sha256'][name]==hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()


def test_interrupted_arm_recovers_durable_slot_status_without_inventing_total_usage(tmp_path):
    from reasonlineage.pilot.paired import _read_study
    folder=tmp_path/'arm'
    finished=folder/'runs/als-gpt';finished.mkdir(parents=True)
    status={'header':{'case':'als','method':'gpt'},'status':'completed',
            'initial':{'fitness':.7},'final':{'fitness':.8}}
    (finished/'status.json').write_text(json.dumps(status))
    active=folder/'runs/aml-gpt';active.mkdir()
    (active/'events.jsonl').write_text(json.dumps({'event':'run.started'})+'\n')
    result=_read_study(folder)
    assert result['aggregate_missing']
    assert status in result['runs']
    assert next(r for r in result['runs'] if r['header']['case']=='aml')['status']=='cutoff'
    assert result['usage']['status']=='unavailable'


def test_pair_comparison_preserves_missing_and_partial_and_never_implies_completion():
    from reasonlineage.pilot.paired import compare_studies
    base={'header':{'case':'als','method':'gpt'},'status':'completed',
          'initial':{'fitness':.7},'final':{'fitness':.8},
          'usage':{'backend_calls':27,'reported_tokens':100,'unknown_usage_calls':0},
          'j1':{'status':'completed'},'diagnostics':{'status':'completed'}}
    off={**base,'final':{'fitness':.75},'j1':{'status':'disabled'},'diagnostics':{'status':'disabled'}}
    on={**base,'j1':{'status':'partial'}}
    rows=compare_studies({'runs':[on]},{'runs':[off]})
    assert len(rows)==8
    row=next(r for r in rows if r['case']=='als' and r['method']=='gpt')
    assert row['both_generated'] and not row['fully_verified']
    assert row['final_fitness_on_minus_off']==pytest.approx(.05)
    missing=next(r for r in rows if r['case']=='aml' and r['method']=='gpt')
    assert not missing['both_generated'] and missing['final_fitness_on_minus_off'] is None
    assert missing['on']['status']=='unstarted'


def test_pair_supervisor_launches_both_modes_and_keeps_report_inside_its_new_output(tmp_path,monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from reasonlineage.pilot import paired
    root=tmp_path/'source'
    for name in ('src/reasonlineage/example.py','scripts/run_co_scientist_pilot.py',
                 'scripts/run_jev_controlled_pilot.py','research/co-scientist-pilot/als-evidence.md',
                 'research/co-scientist-pilot/aml-evidence.md'):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('frozen public fixture')
    plan={'arm_order':['jev-on','jev-off']}
    monkeypatch.setattr(paired,'paired_plan',lambda root:plan)
    launches=[]
    def launch(command,**kwargs):
        launches.append(command)
        folder=Path(command[-1]);folder.mkdir()
        enabled='--jev-combined' in command
        answer={'answer':'An explicit mechanism is a testable hypothetical proposal.',
                'ranking':[{'item':'Candidate','promisingness':.7,'confidence':.6,'pmids':[]}]}
        runs=[{'header':{'case':case,'method':method},'status':'completed',
               'initial':{'id':'c1','fitness':.7,'answer':answer},
               'final':{'id':'c2','fitness':.8,'answer':answer},
               'j1':{'status':'completed' if enabled else 'disabled'},
               'diagnostics':{'status':'completed' if enabled else 'disabled'}}
              for case in ('als','aml') for method in paired.METHODS]
        (folder/'study.json').write_text(json.dumps({'runs':runs,'usage':{'backend_calls':216}}))
        return SimpleNamespace(returncode=0)
    out=tmp_path/'out'
    result=paired.run_pair(out,root,launch=launch)
    assert result['generation_completed']==16 and result['verified_pairs']==8 and result['complete']
    assert '--jev-combined' in launches[0] and '--jev-control' in launches[1]
    assert (out/'report.md').is_file()
    assert not (root/'reports').exists()
    assert json.loads((out/'pair-status.json').read_text())['status']=='completed'
