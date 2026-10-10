import json,time,sys
from pathlib import Path
r=Path(sys.argv[1]); c=json.loads((r/'clock.json').read_text()); elapsed=time.monotonic()-c['monotonic']
print(json.dumps({'elapsed_minutes':round(elapsed/60,1),'generation_remaining_minutes':round(max(0,12000-elapsed)/60,1),'total_remaining_minutes':round(max(0,14400-elapsed)/60,1)},ensure_ascii=False))
for d in sorted((r/'runs').glob('*')):
 events=[json.loads(x) for x in (d/'events.jsonl').read_text().splitlines() if x.strip()]
 done=[e for e in events if e['event']=='call.completed']; bad=[e for e in events if e['event']=='call.failed']
 candidates=[e for e in events if e['event']=='candidate.created']
 state=json.loads((d/'status.json').read_text()) if (d/'status.json').exists() else {}
 print(json.dumps({'slot':d.name,'status':state.get('status','running'),'reason':state.get('reason'),'completed_calls':len(done),'failed_calls':len(bad),'candidates':len(candidates),'latest_generation':max([e.get('generation',0) for e in candidates],default=0),'judgements':sum(e['event']=='judge.scored' for e in events),'reported_tokens':sum(sum((e.get('tokens') or {}).values()) for e in done)},ensure_ascii=False))
if (r/'independent/status.json').exists():
 a=json.loads((r/'independent/status.json').read_text()); print(json.dumps({'independent':[{k:e.get(k) for k in ('case','order','status')} for e in a['evaluations']], 'usage':a['usage']},ensure_ascii=False))
