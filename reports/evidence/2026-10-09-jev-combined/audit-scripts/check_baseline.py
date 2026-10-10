"""Old gate on the same manually labelled structural cases; bounded comparison."""
import asyncio,json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from calibrate_jev import RecordingChecker
from reasonlineage.checks.combined_calibration import build_cases
from reasonlineage.checks.gate import Gate
from reasonlineage.checks.credentials import read_dotenv_key,shared_dotenv
from reasonlineage.checks.jev import JevChecker
from reasonlineage.checks.calibration import VERSION
from reasonlineage.engine.events import read_events
from reasonlineage.pilot.run import save_json
from reasonlineage.protocol import load_protocol


async def execute():
    dest=ROOT/'runs/jev-combined-baseline-2026-10-09'
    dest.mkdir(parents=True,exist_ok=False)
    protocol=load_protocol(ROOT/'research/co-scientist-pilot/protocol-three-initial-jev')
    key=read_dotenv_key(shared_dotenv(ROOT))
    checker=RecordingChecker(JevChecker(key,VERSION,data_sensitivity='public'))
    cases=build_cases(ROOT)
    save_json(dest/'cases.json',cases)
    save_json(dest/'frozen-j1.json',dict(protocol.j1))
    rows=[];started=time.monotonic()
    for case in cases:
        gate=Gate(dest/case['id'],checker,protocol,case['evidence'],'experiment')
        await gate(case['id'],0,'anonymous',case['answer'],0)
        record=read_events(dest/case['id']/'checks.jsonl')[-1]
        rows.append({'id':case['id'],'kind':case['kind'],**record})
        save_json(dest/'records.json',rows)
        if record.get('error'):
            break
    by_kind={kind:{'cases':sum(c['kind']==kind for c in cases),
                   'rewrites':sum(r['would_rewrite'] for r in rows if r['kind']==kind)}
             for kind in dict.fromkeys(c['kind'] for c in cases)}
    summary={'cases':len(cases),'records':len(rows),'by_kind':by_kind,
             'action_correct':sum(r['would_rewrite']==c['expected_rewrite'] for c,r in zip(cases,rows)),
             'failed':sum(bool(r.get('error')) for r in rows),'backend_calls':checker.calls,
             'reported_input_tokens':checker.counts[0],'reported_output_tokens':checker.counts[1],
             'reported_tokens':checker.counts[2],'unknown_usage_calls':checker.unknown,
             'generator_calls':0,'deepseek_calls':0,'elapsed_seconds':round(time.monotonic()-started,3),
             'limitation':'Old policy tests proposal/argument presence, not the four structural fields. This is a scope comparison, not overall superiority.'}
    save_json(dest/'summary.json',summary)
    assert all(key.encode() not in p.read_bytes() for p in dest.rglob('*') if p.is_file())
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:
        asyncio.run(execute())
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'details':'suppressed'}),flush=True)
        raise SystemExit(2)
