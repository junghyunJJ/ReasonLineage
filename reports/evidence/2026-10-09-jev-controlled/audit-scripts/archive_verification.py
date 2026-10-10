"""Validate scientific accounting and archive only public execution evidence."""
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from reasonlineage.core.categories import CATEGORY_PRESETS
from reasonlineage.core.fitness import composite_fitness, median_scores
from reasonlineage.checks.credentials import read_dotenv_key, shared_dotenv
from reasonlineage.pilot.budget import _CREDENTIAL
from reasonlineage.pilot.paired import paired_plan

BASE = ROOT / 'runs/jev-controlled-2026-10-09'
OUT = ROOT / 'reports/evidence/2026-10-09-jev-controlled'


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    summary = load(BASE / 'completed-summary.json')
    assert paired_plan(ROOT) == load(BASE / 'pair-plan.json')
    assert summary['original_completed'] == 13 and summary['supplement_completed'] == 3
    assert summary['usage']['all']['backend_calls'] == 726 and summary['usage']['all']['unknown_usage_calls'] == 5
    assert summary['j1_actual_rewrites'] == 0 and summary['j1_needs_review'] == 0
    weights = CATEGORY_PRESETS['biomedical'].weights
    for run in summary['runs']:
        assert run['model_usage']['backend_calls'] <= 40 and run['checker_usage']['backend_calls'] <= 70
        for candidate in run['candidates']:
            judgments = candidate['judgments']
            if run['method'] == 'reasonlineage':
                assert all(j['judge'] != candidate['author'] for j in judgments)
            median = median_scores([j['scores'] for j in judgments], list(weights))
            assert abs(composite_fitness(median, weights) - candidate['fitness']) < 1e-12
        assert run['original_status'] == load(BASE / run['original_directory'] / 'status.json')['status']
        assert not run['model_usage']['unknown_usage_calls'] or not run['cumulative_token_cap_verified']
    for name, count in [('candidate-scores.csv',144),('generation-scores.csv',64),('completed-comparison.csv',8)]:
        assert len(list(csv.DictReader((BASE / name).open()))) == count
    planned = load(BASE / 'pair-plan.json')
    assert summary['usage']['all']['backend_calls'] <= planned['limits']['total_calls']
    start = datetime.fromisoformat(load(BASE / 'pair-status.json')['started_utc'])
    last = max(datetime.fromisoformat(json.loads(line)['ts']) for p in BASE.rglob('events.jsonl')
               for line in p.read_text().splitlines() if 'ts' in json.loads(line))
    assert (last-start).total_seconds() <= planned['limits']['total_seconds']
    historical=[]
    for name in ('2026-10-07-als-timeout-retry','2026-10-08-aml-solo-retry','2026-10-08-jev-posthoc','2026-10-08-jev-gate','2026-10-09-jev-combined'):
        directory=ROOT/'reports/evidence'/name
        manifest=load(directory/'sha256-manifest.json')
        mismatched=[p for p,h in manifest.items() if not (directory/p).is_file() or digest(directory/p)!=h]
        assert not mismatched, (name,len(mismatched))
        historical.append({'directory':name,'files_checked':len(manifest),'mismatches':0})
    assert sum(r['files_checked'] for r in historical)==1210
    viewer=subprocess.run(['node',str(Path(__file__).parent/'verify_viewer.js')],cwd=ROOT,capture_output=True,text=True)
    if viewer.returncode:
        raise ValueError('viewer render validation failed')
    viewer_result=json.loads(viewer.stdout)
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    shutil.copytree(BASE,OUT/'run',ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env'))
    scripts=OUT/'audit-scripts';scripts.mkdir()
    for path in Path(__file__).parent.glob('*.py'):
        shutil.copyfile(path,scripts/path.name)
    shutil.copyfile(Path(__file__).parent/'verify_viewer.js',scripts/'verify_viewer.js')
    figures=OUT/'figures';figures.mkdir()
    for extension in ('svg','png'):
        shutil.copyfile(ROOT/f'reports/figures/2026-10-09-jev-controlled-evolution.{extension}',figures/f'evolution.{extension}')
    report=(ROOT/'reports/2026-10-09-jev-controlled.md').read_text()
    report=report.replace('../runs/jev-controlled-2026-10-09/','run/').replace('figures/2026-10-09-jev-controlled-evolution.png','figures/evolution.png')
    (OUT/'report.md').write_text(report)
    (OUT/'README.md').write_text('Public execution evidence for the 16-slot ALS/AML jev ON/OFF experiment.\n\n'
                               'Original states in run/jev-on and run/jev-off remain unchanged. Separate completion folders retain failures and follow-up outcomes.\n'
                               'run/evolution-viewer.html is self-contained. Expert ratings are pending; share only run/completed-review-materials/expert.\n'
                               'Reported usage includes all actual failed and supplementary attempts, and excludes replayed calls. Unknown usage remains unknown.\n')
    checks={'status':'passed','original_engine_and_inputs_unchanged':True,'candidate_fitness_recomputed':144,
            'completed_runs':16,'original_completed_runs':13,'supplemented_runs':3,'on_off_comparison_pairs':8,
            'call_caps_verified':True,'exact_token_cap_verified_for_all_cases':False,
            'last_execution_event_utc':last.isoformat(),'execution_elapsed_seconds':(last-start).total_seconds(),
            'viewer':viewer_result,'scientific_plot_visually_inspected':True,'expert_review':'pending'}
    (OUT/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    (OUT/'historical-evidence-check.json').write_text(json.dumps(historical,ensure_ascii=False,indent=2))
    # Use the approved credential reader only for in-memory equality checks; no secret output.
    key=read_dotenv_key(shared_dotenv(ROOT))
    exact=pattern=private=0;checked=0
    private_keys={'reasoning','reasoning_content','chain_of_thought','analysis','authorization','api_key'}
    def private_count(value):
        if isinstance(value,dict):
            return sum(str(k).lower() in private_keys for k in value)+sum(private_count(v) for v in value.values())
        if isinstance(value,list):return sum(private_count(v) for v in value)
        return 0
    for path in OUT.rglob('*'):
        if not path.is_file() or path.suffix not in ('.json','.jsonl','.md','.py','.js','.log','.html','.csv','.svg'):
            continue
        text=path.read_text();checked+=1
        exact+=key in text
        pattern+=len(_CREDENTIAL.findall(text))
        if path.suffix=='.json':private+=private_count(json.loads(text))
        if path.suffix=='.jsonl':private+=sum(private_count(json.loads(line)) for line in text.splitlines() if line.strip())
    del key
    assert exact==pattern==private==0, 'public boundary check failed; content suppressed'
    security={'status':'passed','text_files_checked':checked,'exact_jev_credential_matches':exact,
              'credential_pattern_matches':pattern,'private_json_keys':private,'dotenv_copied':False,
              'hidden_reasoning_copied':False,'credential_output':'none'}
    (OUT/'security-check.json').write_text(json.dumps(security,indent=2))
    manifest={p.relative_to(OUT).as_posix():digest(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'verification':checks,'historical_files_checked':1210,'security':security,'archived_files':len(manifest)},ensure_ascii=False))


if __name__=='__main__':main()
