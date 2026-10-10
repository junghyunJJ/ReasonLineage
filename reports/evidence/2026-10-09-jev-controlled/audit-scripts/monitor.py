"""Only public progress metadata; never reads credentials or provider reasoning."""
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
DEST=ROOT/'runs/jev-controlled-2026-10-09'


def events(path):
    if not path.exists():
        return []
    rows=[]
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def execute():
    marker=DEST/'pair-status.json'
    state=json.loads(marker.read_text()) if marker.exists() else {}
    output={'utc':datetime.now(timezone.utc).isoformat(),'pair_status':state,'slots':[]}
    for arm in ('jev-on','jev-off'):
        for folder in sorted((DEST/arm/'runs').glob('*')):
            if not folder.is_dir():
                continue
            path=folder/'status.json'
            status=json.loads(path.read_text()) if path.exists() else None
            rows=events(folder/'events.jsonl')
            done=[r for r in rows if r.get('event')=='call.completed' and not r.get('replayed')]
            scored=[r for r in rows if r.get('event')=='candidate.scored']
            initial=[r for r in rows if r.get('event')=='pilot.initial']
            checks=events(folder/'checks.jsonl')
            output['slots'].append({'arm':arm,'slot':folder.name,'status':status['status'] if status else 'running',
                'public_responses_recorded':len(done),'scored_candidates':len(scored),
                'last_completed_call':done[-1]['name'] if done else None,
                'inflight_requests':'engine does not persist started events; not inferred',
                'j1_checks':len(checks),'j1_unresolved':sum(bool(r.get('needs_review')) for r in checks),
                'initial_fitness':status.get('initial',{}).get('fitness') if status else initial[-1].get('fitness') if initial else None,
                'latest_scored_fitness':scored[-1].get('fitness') if scored else None,
                'final_fitness':status.get('final',{}).get('fitness') if status else None,
                'last_event':rows[-1]['event'] if rows else None,'reason':status.get('reason') if status else None})
    (Path(__file__).parent/'latest-status.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':
    execute()
