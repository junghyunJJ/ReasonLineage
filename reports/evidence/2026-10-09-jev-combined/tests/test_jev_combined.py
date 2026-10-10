import asyncio
import importlib.util
from types import SimpleNamespace

import pytest

from reasonlineage.checks.base import CheckAnswer, CheckResult
from reasonlineage.checks.gate import Gate
from reasonlineage.engine.events import read_events

COMPONENTS = ('mechanism', 'premises', 'validation', 'falsifier')


def module():
    assert importlib.util.find_spec('reasonlineage.checks.combined'), 'combined decision policy is missing'
    from reasonlineage.checks import combined
    return combined


def config():
    return {'policy': 'conditioned', 'enforce': True, 'thresholds': {'proposal': .5, 'adequacy': .5},
            'components': {name: {'question': name + '_quality', 'rewrite_reason': 'Improve ' + name}
                           for name in COMPONENTS}, 'proposal_rewrite_reason': 'Write a substantive hypothesis',
            'recheck_attempts': 1}


def answers(*, proposal=.99, gap='none', weak=()):
    rows = {'proposal_present': CheckAnswer('noul', {'yes': proposal, 'no': 1-proposal}).to_dict(),
            'primary_gap': CheckAnswer('choice', {key: float(key == gap) for key in
                           (*COMPONENTS, 'none', 'no_proposal', 'uncertain')}).to_dict()}
    for name in COMPONENTS:
        rows[name+'_quality'] = CheckAnswer('score', {'1' if name in weak else '3': 1.0}).to_dict()
    return rows


def test_missing_proposal_ignores_irrelevant_choice_and_scores():
    result = module().verdict(answers(proposal=.1, gap='validation', weak=('validation',)), config())
    assert result['would_rewrite'] and not result['needs_review']
    assert result['focus'] == ['proposal']


def test_named_gap_and_matching_weak_score_produce_targeted_rewrite():
    result = module().verdict(answers(gap='validation', weak=('validation',)), config())
    assert result['would_rewrite'] and not result['needs_review']
    assert result['focus'] == ['validation'] and result['reasons'] == ['Improve validation']
    assert result['adequacy']['mechanism'] == 1 and result['adequacy']['validation'] == 0


def test_two_missing_parts_are_corrected_together_with_primary_gap_first():
    result = module().verdict(answers(gap='falsifier', weak=('mechanism', 'falsifier')), config())
    assert result['focus'] == ['falsifier', 'mechanism']


@pytest.mark.parametrize('gap,weak', [('none', ('validation',)), ('mechanism', ('validation',)),
                                     ('no_proposal', ()), ('uncertain', ())])
def test_disagreement_is_review_state_not_a_silent_pass_or_rewrite(gap, weak):
    result = module().verdict(answers(gap=gap, weak=weak), config())
    assert result['needs_review'] and not result['would_rewrite']


def test_exact_half_passes_without_multiplying_model_outputs():
    data = answers(proposal=.5)
    data['validation_quality'] = CheckAnswer('score', {'1': .5, '2': .5}).to_dict()
    result = module().verdict(data, config())
    assert not result['would_rewrite'] and not result['needs_review']


def test_distribution_decides_even_when_expected_score_order_is_reversed():
    low_mean = answers()
    low_mean['validation_quality'] = CheckAnswer('score', {'0': .45, '3': .55}).to_dict()
    high_mean = answers(gap='validation', weak=('validation',))
    high_mean['validation_quality'] = CheckAnswer('score', {'1': .55, '3': .45}).to_dict()
    assert low_mean['validation_quality']['value'] < high_mean['validation_quality']['value']
    assert not module().verdict(low_mean, config())['would_rewrite']
    assert module().verdict(high_mean, config())['would_rewrite']


def test_calibration_and_policy_hashes_bind_choice_option_order():
    from reasonlineage.checks.calibration import questions_hash
    first = protocol()
    second = protocol()
    criteria = second.j1['questions']['primary_gap']['criteria']
    second.j1['questions']['primary_gap']['criteria'] = dict(reversed(list(criteria.items())))
    assert questions_hash(first) != questions_hash(second)
    assert module().policy_hash(first.j1) != module().policy_hash(second.j1)


def protocol():
    specs = {'proposal_present': {'type': 'noul', 'instructions': 'Does the answer contain a hypothesis?'},
             'primary_gap': {'type': 'choice', 'instructions': 'Which essential field is missing?',
                             'criteria': dict.fromkeys((*COMPONENTS, 'none', 'no_proposal', 'uncertain'), 'description')}}
    specs.update({name+'_quality': {'type': 'score', 'instructions': 'Rate '+name,
                                   'criteria': ['absent', 'vague', 'adequate', 'clear']} for name in COMPONENTS})
    return SimpleNamespace(j1={**config(), 'questions': specs,
                              'recheck_instructions': 'Assess only the proposed answer; do not invent missing content.'})


class Checker:
    name, pinned_version = 'jev', 'jev-1.13.0'
    def __init__(self, replies):
        self.replies, self.calls = replies, []
    async def ask(self, state, questions):
        self.calls.append((state, questions))
        raw = self.replies[min(len(self.calls)-1, len(self.replies)-1)]
        return CheckResult(self.pinned_version, {k: CheckAnswer(v['kind'], v['probabilities']) for k,v in raw.items()},
                           {'input_tokens': 10, 'output_tokens': 10})


ANSWER = {'answer': 'A hypothetical mechanism with explicit premises and a test.',
          'ranking': [{'item': 'A', 'promisingness': .7, 'confidence': .6, 'pmids': []}]}


def test_conflict_is_rechecked_once_then_rewrite_is_routed_by_resolved_result(tmp_path):
    checker = Checker([answers(gap='none', weak=('validation',)), answers(gap='validation', weak=('validation',))])
    gate = Gate(tmp_path, checker, protocol(), 'Evidence and research question', 'experiment')
    decision = asyncio.run(gate('c1', 0, 'glm', ANSWER, 0))
    assert decision.rewrite and decision.reasons == ('Improve validation',)
    assert len(checker.calls) == 2
    records = read_events(tmp_path/'checks.jsonl')
    assert records[0]['rechecked'] and not records[0]['needs_review']
    assert records[0]['initial_verdict']['needs_review']
    assert checker.calls[1][0].startswith('Proposed answer:')


def test_unresolved_conflict_is_bounded_recorded_and_cached_per_attempt(tmp_path):
    checker = Checker([answers(gap='none', weak=('validation',))])
    gate = Gate(tmp_path, checker, protocol(), 'Question', 'experiment')
    first = asyncio.run(gate('c1', 0, 'glm', ANSWER, 0))
    assert not first.rewrite
    second = asyncio.run(gate('c1', 0, 'glm', ANSWER, 1))
    assert not second.rewrite and len(checker.calls) == 2
    records = read_events(tmp_path/'checks.jsonl')
    assert [r['attempt'] for r in records] == [0,1]
    assert all(r['needs_review'] for r in records)


def test_recheck_removes_obsolete_component_verdict_when_proposal_is_absent(tmp_path):
    checker = Checker([answers(gap='none', weak=('validation',)), answers(proposal=.1)])
    gate = Gate(tmp_path, checker, protocol(), 'Question', 'experiment')
    assert asyncio.run(gate('c1', 0, 'glm', ANSWER, 0)).rewrite
    record = read_events(tmp_path/'checks.jsonl')[0]
    assert record['focus'] == ['proposal']
    assert record['adequacy'] == {}
    assert not any(k in record for k in ('primary_gap', 'primary_probability', 'weak'))
    assert record['initial_verdict']['weak'] == ['validation']


def test_holdout_answer_bodies_are_disjoint_from_development_cases():
    from pathlib import Path
    from reasonlineage.checks.combined_calibration import build_cases
    root = Path(__file__).resolve().parents[1]
    development = {c['answer']['answer'] for c in build_cases(root)}
    held = build_cases(root, holdout=True)
    assert len(held) == 48
    assert development.isdisjoint(c['answer']['answer'] for c in held)
    for case in ('als', 'aml'):
        for kind in ('refusal', 'meta', 'grader'):
            first = next(c for c in build_cases(root) if c['case'] == case and c['kind'] == kind)
            assert all(first['answer']['answer'] not in c['answer']['answer'] for c in held
                       if c['case'] == case and c['kind'] == kind)
