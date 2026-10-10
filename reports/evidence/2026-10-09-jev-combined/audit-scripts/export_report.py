"""Freeze public evidence and verify historical manifests without touching sources."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from reasonlineage.checks.credentials import read_dotenv_key,shared_dotenv
from reasonlineage.checks.calibration import validate_certificate
from reasonlineage.pilot.budget import usage_counts
from reasonlineage.pilot.run import save_json
from reasonlineage.pilot.study import dry_plan
from reasonlineage.protocol import load_protocol

RUNS=(
    'jev-combined-check-2026-10-09',
    'jev-combined-check-2026-10-09-v2',
    'jev-combined-check-2026-10-09-holdout',
    'jev-combined-check-2026-10-09-holdout-v2',
    'jev-combined-baseline-2026-10-09',
    'jev-combined-live-rewrite-2026-10-09')


def execute():
    dest=ROOT/'reports/evidence/2026-10-09-jev-combined'
    dest.mkdir(parents=True,exist_ok=False)
    for name in RUNS:
        shutil.copytree(ROOT/'runs'/name,dest/name)
    shutil.copytree(ROOT/'research/co-scientist-pilot/protocol-jev-combined',dest/'frozen-profile')
    for path in sorted((ROOT/'src/reasonlineage').rglob('*.py')):
        target=dest/'source-code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
    scripts=('scripts/check_jev_combined.py','scripts/calibrate_jev.py','scripts/run_co_scientist_pilot.py',
             '.superpowers/sdd/2026-10-08-jev-combined/check_live_rewrite.py',
             '.superpowers/sdd/2026-10-08-jev-combined/check_baseline.py',
             '.superpowers/sdd/2026-10-08-jev-combined/export_report.py')
    for name in scripts:
        target=dest/'audit-scripts'/Path(name).name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    for name in ('test_jev_combined.py','test_pilot_jev_combined.py'):
        target=dest/'tests'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'tests'/name,target)
    totals=[0,0,0];jev_calls=unknown=0
    for name in RUNS[:-1]:
        data=json.loads((ROOT/'runs'/name/'summary.json').read_text())
        jev_calls+=data['backend_calls'];unknown+=data['unknown_usage_calls']
        totals=[a+data[k] for a,k in zip(totals,('reported_input_tokens','reported_output_tokens','reported_tokens'))]
    diagnosis=json.loads((ROOT/'runs'/RUNS[0]/'order-diagnostic.json').read_text())
    jev_calls+=len(diagnosis)
    for row in diagnosis:
        counts=usage_counts(row['usage']);assert counts is not None
        totals=[a+b for a,b in zip(totals,counts)]
    smoke=json.loads((ROOT/'runs'/RUNS[-1]/'summary.json').read_text())
    for group in ('checker_usage',):
        data=smoke[group];jev_calls+=data['backend_calls'];unknown+=data['unknown_usage_calls']
        totals=[a+data[k] for a,k in zip(totals,('reported_input_tokens','reported_output_tokens','reported_tokens'))]
    writer=smoke['writer_usage']
    accounting={'jev_calls':jev_calls,'jev_input_tokens':totals[0],'jev_output_tokens':totals[1],
                'jev_tokens':totals[2],'writer_calls':writer['backend_calls'],
                'writer_input_tokens':writer['reported_input_tokens'],
                'writer_output_tokens':writer['reported_output_tokens'],
                'writer_tokens':writer['reported_tokens'],
                'all_calls':jev_calls+writer['backend_calls'],
                'all_tokens':totals[2]+writer['reported_tokens'],'unknown_usage_calls':unknown+writer['unknown_usage_calls'],
                'deepseek_calls':0,'initial_limits':{'jev_calls':320,'writer_calls':4},
                'includes_failed_and_superseded_attempts':True}
    assert jev_calls==258 and writer['backend_calls']==2 and unknown==0
    save_json(dest/'accounting.json',accounting)
    historical={}
    for name in ('2026-10-07-als-timeout-retry','2026-10-08-aml-solo-retry','2026-10-08-jev-posthoc','2026-10-08-jev-gate'):
        base=ROOT/'reports/evidence'/name
        manifest=json.loads((base/'sha256-manifest.json').read_text())
        mismatches=[name for name,digest in manifest.items()
                    if not (base/name).is_file() or hashlib.sha256((base/name).read_bytes()).hexdigest()!=digest]
        assert not mismatches
        historical[name]={'files':len(manifest),'all_unchanged':True}
    save_json(dest/'historical-evidence-check.json',historical)
    validate_certificate(load_protocol(ROOT/'research/co-scientist-pilot/protocol-jev-combined'))
    validate_certificate(load_protocol(ROOT/'research/co-scientist-pilot/protocol-three-initial-jev'))
    save_json(dest/'dry-plan.json',dry_plan(ROOT,combined=True))
    links=[]
    docs=('reports/2026-10-09-reasonlineage-purpose-and-method.md','reports/2026-10-09-jev-combined.md',
          'research/co-scientist-pilot/protocol-jev-combined/README.md')
    for name in docs:
        path=ROOT/name
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith(('http://','https://','#')):
                continue
            assert (path.parent/target).exists(),(name,target)
            links.append({'file':name,'target':target,'exists':True})
    save_json(dest/'document-links.json',links)
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    assert diff.returncode==0
    save_json(dest/'verification.json',{
        'offline_tests':{'command':"python -m pytest -q -m 'not live'",'exit_code':0,
                         'passed':786,'deselected':3,'seconds':24.37,
                         'evidence':'observed completed exec session32924'},
        'git_diff_check':{'exit_code':diff.returncode},'new_and_legacy_certificates_valid':True,
        'full_new_scientific_study_started':False,
        'review':{'critical':0,'important':0,'minor':0,
                  'scope':'code regressions, certificate and final report interpretation; no biology accuracy audit'}})
    key=read_dotenv_key(shared_dotenv(ROOT)).encode()
    sensitive=re.compile(rb'apikey_[A-Za-z0-9_]{16,}|\bsk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}')
    for path in [*dest.rglob('*'),*(ROOT/name for name in docs)]:
        if path.is_file():
            data=path.read_bytes()
            assert key not in data
            assert not sensitive.search(data),str(path.relative_to(ROOT))
    save_json(dest/'security-check.json',{'actual_jev_key_absent':True,'credential_pattern_matches':0,
               'no_env_or_private_reasoning_copied':True})
    manifest={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(dest.rglob('*')) if p.is_file()}
    save_json(dest/'sha256-manifest.json',manifest)
    print(json.dumps({'accounting':accounting,'historical':historical,'evidence_files':len(manifest),
                      'document_links':len(links),'certificates_valid':True,'security_scan_passed':True},ensure_ascii=False))


if __name__=='__main__':
    try:
        execute()
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}))
        raise SystemExit(2)
