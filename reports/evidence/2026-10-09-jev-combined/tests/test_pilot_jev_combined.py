import asyncio
import json
import subprocess
import sys

from reasonlineage.checks.base import CheckAnswer, CheckResult
from reasonlineage.checks.calibration import VERSION
from reasonlineage.engine.config import load_setup
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.run import run_case
from reasonlineage.protocol import load_protocol
from test_pilot_run import ROOT
from test_pilot_jev_gate import UniqueBackend


class CombinedChecker:
    name, pinned_version = 'jev', VERSION
    def __init__(self, first_gap=False):
        self.calls=[]
        self.first_gap=first_gap
    async def ask(self,state,questions):
        self.calls.append((state,questions))
        bad=self.first_gap and len(self.calls)==1
        answers={}
        for q in questions:
            if q.kind=='noul':
                answers[q.name]=CheckAnswer('noul',{'yes':.99,'no':.01})
            elif q.kind=='choice':
                chosen=('validation' if bad else 'none') if q.name=='primary_gap' else 'minor'
                answers[q.name]=CheckAnswer('choice',{k:float(k==chosen) for k,_ in q.choices})
            else:
                level='1' if q.name=='validation_quality' and bad else '3' if q.name.endswith('_quality') else '0'
                answers[q.name]=CheckAnswer('score',{level:1.0})
        return CheckResult(VERSION,answers,{'input_tokens':10,'output_tokens':10})


def test_validated_combined_profile_is_accepted_without_changing_legacy_certificate():
    from reasonlineage.checks.calibration import validate_certificate
    validate_certificate(load_protocol(ROOT/'research/co-scientist-pilot/protocol-jev-combined'))
    validate_certificate(load_protocol(ROOT/'research/co-scientist-pilot/protocol-three-initial-jev'))


def test_combined_gap_rewrites_one_author_and_keeps_population_and_panel_rules(tmp_path):
    setup=load_setup(ROOT/'configs/co-scientist-rerun.json')
    services={m.name:UniqueBackend(m.name) for m in setup.panel}
    checker=CombinedChecker(first_gap=True)
    result=asyncio.run(run_case(tmp_path/'run','als','reasonlineage',setup,services,
                    Budget(seconds=100,calls=1000,tokens=None),root=ROOT,
                    protocol_directory='protocol-jev-combined',checker=checker))
    assert result['status']=='completed' and result['usage']['backend_calls']==28
    events=read_events(tmp_path/'run/events.jsonl')
    rewrites=[e for e in events if e['event']=='call.completed' and '/rewrite/' in e['name']]
    assert len(rewrites)==1 and rewrites[0]['name'].endswith('/gpt')
    checks=read_events(tmp_path/'run/checks.jsonl')
    assert checks[0]['focus']==['validation']
    assert len(checker.calls)==37
    assert all(e['judge']!=e['author'] for e in events if e['event']=='judge.scored')
    assert result['header']['evolution']['initial_candidates']==3
    assert result['header']['evolution']['survivor_count']==2


def test_combined_command_and_study_select_new_policy_and_never_build_deepseek(tmp_path,monkeypatch):
    from reasonlineage.pilot import study
    run=subprocess.run([sys.executable,str(ROOT/'scripts/run_co_scientist_pilot.py'),
                        '--jev-combined','--out',str(tmp_path/'not-started')],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    plan=json.loads(run.stdout)
    assert plan['protocol_directory']=='protocol-jev-combined'
    assert plan['independent_model'] is None and plan['limits']['max_checker_calls']==70
    assert not (tmp_path/'not-started').exists()
    def forbidden(*a,**k):
        raise AssertionError('DeepSeek must remain disabled')
    monkeypatch.setattr(study,'evaluator_member',forbidden)
    setup=load_setup(ROOT/'configs/co-scientist-rerun.json')
    services={m.name:UniqueBackend(m.name) for m in setup.panel}
    result=asyncio.run(study.run_study(tmp_path/'study',ROOT,setup=setup,services=services,
                                      combined=True,checker=CombinedChecker()))
    assert all(r['status']=='completed' for r in result['runs'])
    assert result['independent_evaluations']==[]
    assert result['frozen_plan']['protocol_directory']=='protocol-jev-combined'
    assert all(r['header']['protocol_version']=='co-scientist-jev-combined-0.7' for r in result['runs'])
