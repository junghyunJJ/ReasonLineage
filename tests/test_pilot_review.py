import json

import pytest

from reasonlineage.pilot.review import export_expert, validate_review, citation_audit, comparable, derive_preferences


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
    assert packet['pairs'] == []
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


def test_public_packet_does_not_reveal_the_comparison_graph(tmp_path):
    packet = export_expert(tmp_path, statuses(), {'als': 'Evidence'})
    assert packet['pairs'] == []
    ratings = json.loads((tmp_path / 'expert/ratings.json').read_text())
    assert ratings['overall_ordering'][0]['tie_groups'] == []
    assert len(json.loads((tmp_path / 'analyst/mapping.json').read_text())['pairs']) == 3


@pytest.mark.parametrize('text', ['As GPT, I propose this.', 'As Claude I propose this.',
                                  'This final revision improves my initial proposal.'])
def test_explicit_model_alias_or_stage_disclosure_is_quarantined(tmp_path, text):
    data = statuses()[:1]
    data[0]['initial'] = proposal(text)
    data[0]['final'] = proposal(text)
    packet = export_expert(tmp_path, data, {'als': 'Evidence'})
    assert packet['proposals'] == []


def test_biological_gpt_and_statistical_glm_terms_remain_public(tmp_path):
    data = statuses()[:1]
    data[0]['initial'] = data[0]['final'] = proposal('GPT-dependent transamination is measured using a GLM estimator.')
    assert len(export_expert(tmp_path, data, {'als': 'Evidence'})['proposals']) == 1


def test_blinded_overall_order_derives_planned_pairs_with_ties_and_unknowns():
    ordering = [{'case': 'als', 'tie_groups': [['a'], ['b', 'c']], 'unrankable_ids': ['d']}]
    pairs = [{'id': '1', 'case': 'als', 'first': 'a', 'second': 'b'},
             {'id': '2', 'case': 'als', 'first': 'b', 'second': 'c'},
             {'id': '3', 'case': 'als', 'first': 'a', 'second': 'd'}]
    result = derive_preferences(ordering, pairs)
    assert [r['preference'] for r in result] == ['first', 'tie', 'unsure']
    with pytest.raises(ValueError):
        derive_preferences([{'case': 'als', 'tie_groups': [['a'], ['a']]}], pairs)
