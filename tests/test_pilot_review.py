import json

import pytest

from reasonlineage.pilot.review import export_expert, validate_review, citation_audit, comparable


def proposal(text):
    return {'id': 'c001', 'author': 'gpt', 'fitness': .85,
            'answer': {'answer': text, 'ranking': [{'item': 'Hypothesis', 'promisingness': .9,
                                                  'confidence': .8, 'pmids': ['29311743']}]}}


def statuses():
    return [{'header': {'case': 'als', 'method': method}, 'status': 'completed',
             'initial': proposal('Initial hypothesis [S1].'), 'final': proposal(text),
             'usage': {'reported_tokens': 100, 'unknown_usage_calls': 0}}
            for method, text in [('reasonlineage', 'Pore hypothesis [S1].'), ('gpt', 'Different hypothesis [S2].')]]


def test_anonymous_export_deduplicates_and_hides_identity_stages_and_scores(tmp_path):
    data = statuses()
    packet = export_expert(tmp_path, data, {'als': 'Shared evidence'})
    assert len(packet['proposals']) == 3
    mapping = json.loads((tmp_path / 'analyst/mapping.json').read_text())
    assert len(mapping['proposals']) == 4
    public = ''.join(p.read_text() for p in (tmp_path / 'expert').rglob('*') if p.is_file())
    for secret in ('reasonlineage', 'gpt', 'c001', 'fitness', 'promisingness', 'confidence'):
        assert secret not in public.lower()
    assert len(packet['pairs']) == 3
    assert len({p['id'] for p in packet['proposals']}) == 3
    with pytest.raises(FileExistsError):
        export_expert(tmp_path, data, {'als': 'Shared evidence'})


def test_failed_final_and_explicit_identity_leak_are_not_exported(tmp_path):
    data = statuses()
    data[1]['status'] = 'failed'
    packet = export_expert(tmp_path, data, {'als': 'Evidence'})
    assert len(packet['proposals']) == 2
    other = tmp_path / 'other'
    data[0]['final'] = proposal('As GPT-6.1-sol I propose this.')
    packet = export_expert(other, data, {'als': 'Evidence'})
    assert len(packet['proposals']) == 1
    assert json.loads((other / 'analyst/mapping.json').read_text())['excluded']


def test_held_out_review_requires_exact_ids_once_and_valid_ratings():
    scores = dict.fromkeys(['grounding', 'causal_rigor', 'specificity', 'testability', 'feasibility'], 4)
    good = {'reviews': [{'id': 'anon1', **scores, 'novelty_note': 'unknown', 'reason': 'Testable.'}]}
    assert validate_review(good, ['anon1']) == good
    with pytest.raises(ValueError):
        validate_review(good, ['anon1', 'missing'])
    with pytest.raises(ValueError):
        validate_review({'reviews': good['reviews'] * 2}, ['anon1'])
    with pytest.raises(ValueError):
        validate_review({'reviews': [dict(good['reviews'][0], grounding=True)]}, ['anon1'])


def test_citation_audit_distinguishes_metadata_from_claim_support():
    result = citation_audit('Hypothesis [S1] [S9], PMID: 12345678; DOI: 10.1000/example.', ['29311743'],
                            '## S1 — Paper\nPMID: `29311743`; DOI: `10.1038/test`.')
    assert result['outside_packet_pmids'] == ['12345678']
    assert result['unknown_source_labels'] == ['S9']
    assert result['claim_verification'] == 'pending'


def test_usage_comparison_does_not_infer_same_budget_from_call_counts():
    a, b = statuses()
    assert comparable(a, b)['comparable_usage']
    b['usage']['reported_tokens'] = 150
    assert not comparable(a, b)['comparable_usage']
    b['usage']['reported_tokens'] = 100
    b['usage']['unknown_usage_calls'] = 1
    assert not comparable(a, b)['comparable_usage']
