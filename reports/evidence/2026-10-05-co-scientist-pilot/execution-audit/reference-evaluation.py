"""User-approved exploratory assessment; no generation, repair, or retry."""
import asyncio
import hashlib
import json
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'src'))
from reasonlineage.cli import _cancel_on_signals
from reasonlineage.engine.answer import normalize_answer
from reasonlineage.engine.config import build_backend, load_setup
from reasonlineage.pilot.budget import Budget
from reasonlineage.pilot.review import RATINGS, _IDENTITY, _DISCLOSURE, citation_audit
from reasonlineage.pilot.run import save_json
from reasonlineage.pilot.study import independent_reviews, evaluator_member, cost_summary, supervise

RUN = ROOT / 'runs/co-scientist-pilot-2026-10-05'


def collect_references(study):
    references = []
    for status in study['runs']:
        case, method = status['header']['case'], status['header']['method']
        directory = RUN / 'runs' / f'{case}-{method}'
        authored = []
        for path in sorted(directory.glob('calls/g*/*/*/*.json')):
            parts = path.relative_to(directory / 'calls').parts
            if parts[1] not in ('write', 'mutate', 'cross'):
                continue
            try:
                data = normalize_answer(json.loads(path.read_text())['response']['data'], None)
            except (ValueError, TypeError):
                continue
            if len(data['ranking']) == 1:
                authored.append((int(parts[0][1:]), parts[2], data, str(path.relative_to(RUN))))
        initial = status.get('initial')
        chosen = []
        if initial:
            chosen.append((0, initial['id'], initial['answer'], 'initial_best', None))
        else:
            seeds = [a for a in authored if a[0] == 0 and 400 <= len(a[2]['answer'].split()) <= 800]
            if seeds:
                gen, cid, data, source = min(seeds, key=lambda a: a[1])
                chosen.append((gen, cid, data, 'earliest_valid_seed_no_scored_initial', source))
        revisions = [a for a in authored if a[0] > 0]
        if revisions:
            latest = max(a[0] for a in revisions)
            chosen.extend((gen, cid, data, 'latest_available_revision', source)
                          for gen, cid, data, source in revisions if gen == latest)
        for gen, cid, data, stage, source in chosen:
            references.append({'case': case, 'method': method, 'stage': stage, 'candidate': cid,
                               'generation': gen, 'answer': data, 'source_call': source,
                               'full_run_status': status['status'], 'word_count': len(data['answer'].split()),
                               'word_range_valid': 400 <= len(data['answer'].split()) <= 800,
                               'full_protocol_completed': status['status'] == 'completed'})
    return references


def assemble(references):
    destination = RUN / 'reference-materials'
    expert, analyst = destination / 'expert', destination / 'analyst'
    expert.mkdir(parents=True, exist_ok=False)
    analyst.mkdir()
    proposals, mapping, excluded, seen = [], [], [], {}
    for ref in references:
        data = ref['answer']
        text, title = data['answer'], data['ranking'][0]['item']
        metadata = {k: v for k, v in ref.items() if k != 'answer'}
        if _IDENTITY.search(text + title) or _DISCLOSURE.search(text + title):
            excluded.append({**metadata, 'reason': 'identity or stage disclosure'})
            continue
        digest = hashlib.sha256(' '.join(text.split()).encode()).hexdigest()
        key = ref['case'], digest
        if key not in seen:
            pid = 'P' + secrets.token_hex(5)
            seen[key] = pid
            proposals.append({'id': pid, 'case': ref['case'], 'title': title, 'text': text})
            (expert / f'{pid}.md').write_text(f'# {pid}\n\n{text}\n')
        mapping.append({**metadata, 'id': seen[key], 'content_sha256': digest})
    import random
    random.SystemRandom().shuffle(proposals)
    packet = {'proposals': proposals, 'pairs': []}
    save_json(expert / 'packet.json', packet)
    save_json(expert / 'ratings.json', {'ratings': [{'id': p['id'], **dict.fromkeys(RATINGS),
               'reason': '', 'novelty_note': '', 'possible_unblinding': ''} for p in proposals],
               'overall_ordering': [{'case': c, 'tie_groups': [], 'unrankable_ids': [], 'reason': ''} for c in ('als', 'aml')]})
    save_json(analyst / 'mapping.json', {'proposals': mapping, 'excluded': excluded,
              'scope': 'exploratory initial and latest available revisions; original final comparison remains incomplete',
              'selection': 'scored initial best or earliest valid seed by ID; all authored responses in latest available revision generation'})
    evidence = {}
    audits = []
    for case in ('als', 'aml'):
        source = RUN / f'frozen-inputs/research/co-scientist-pilot/{case}-evidence.md'
        shutil.copy2(source, expert / source.name)
        evidence[case] = source.read_text()
    for proposal in proposals:
        ref = next(r for r in references if r['case'] == proposal['case'] and r['answer']['answer'] == proposal['text'])
        audits.append({'id': proposal['id'], 'case': proposal['case'],
                       **citation_audit(proposal['text'], ref['answer']['ranking'][0]['pmids'], evidence[proposal['case']])})
    save_json(destination / 'citation-audit.json', audits)
    (expert / 'README.md').write_text('These anonymous proposals are exploratory reference material from incomplete pilot sequences. '
        'They do not establish final method superiority. Assess scientific content against the common evidence: grounding, causal rigor, '
        'specificity, testability and feasibility from 1 (major defects) to 5 (unusually strong). Record novelty descriptively, limitations '
        'and possible unblinding. Order proposal IDs in tie_groups from strongest to weakest within each case; use unrankable_ids when '
        'you cannot assess a proposal. Model/stage mapping and automatic scores are withheld.\n')
    return packet, evidence


async def evaluate():
    if (RUN / 'reference-materials').exists() or (RUN / 'reference-independent').exists():
        raise FileExistsError('reference assessment exists; no requests dispatched')
    original = json.loads((RUN / 'study.json').read_text())
    assert not any(e['status'] != 'unstarted' for e in original['independent_evaluations'])
    shutil.copy2(RUN / 'study.json', RUN / 'generation-only-study.json')
    references = collect_references(original)
    assert references and len(references) <= 20
    packet, evidence = assemble(references)
    shared = Budget(seconds=14400, calls=404, tokens=None)
    shared.started = json.loads((RUN / 'clock.json').read_text())['monotonic']
    usage = original['usage']
    for attr, key in [('calls_used', 'backend_calls'), ('reported_input', 'reported_input_tokens'),
                      ('reported_output', 'reported_output_tokens'), ('reported_tokens', 'reported_tokens'),
                      ('unknown', 'unknown_usage_calls')]:
        setattr(shared, attr, usage[key])
    setup = load_setup(ROOT / 'configs/co-scientist-pilot.json')
    service = build_backend(evaluator_member(setup), 1)
    cancelled = False
    try:
        results = await independent_reviews(RUN / 'reference-independent', packet, evidence, service, shared)
    except asyncio.CancelledError:
        cancelled = True
        results = json.loads((RUN / 'reference-independent/status.json').read_text())['evaluations']
    finally:
        original['reference_evaluations'] = results
        original['reference_proposal_count'] = len(packet['proposals'])
        original['reference_packet'] = 'reference-materials/expert'
        original['reference_scope'] = 'User-approved exploratory initial/intermediate assessment; no completed final run or primary method comparison'
        original['usage'] = shared.snapshot()
        original['cost'] = cost_summary(RUN)
        save_json(RUN / 'study.json', original)
    if cancelled:
        raise asyncio.CancelledError
    print('Reference evaluations:', [(e['case'], e['order'], e['status']) for e in results], flush=True)


if __name__ == '__main__':
    if '--worker' in sys.argv:
        asyncio.run(_cancel_on_signals(evaluate()))
    else:
        raise SystemExit(supervise([sys.executable, '-B', str(Path(__file__).resolve()), '--worker'], RUN / 'clock.json'))
