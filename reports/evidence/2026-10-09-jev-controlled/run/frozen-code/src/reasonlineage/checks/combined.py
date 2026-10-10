"""Conditional composition of typed judgments, not a joint probability estimate."""
import hashlib
import json

COMPONENTS = ('mechanism', 'premises', 'validation', 'falsifier')


def policy_hash(j1):
    return hashlib.sha256(json.dumps({k:v for k,v in j1.items() if k != 'enforce'},
                                    sort_keys=False, ensure_ascii=False).encode()).hexdigest()


def verdict(answers, j1):
    result = {'would_rewrite': False, 'needs_review': False, 'review_reason': None,
              'focus': [], 'reasons': [], 'adequacy': {}, 'enforced': bool(j1['enforce'])}
    if not answers:
        return {**result, 'needs_review': True, 'review_reason': 'checker_unavailable'}
    present = answers['proposal_present']['probabilities'].get('yes', 0.0)
    result['proposal_probability'] = present
    if present < j1['thresholds']['proposal']:
        return {**result, 'would_rewrite': True, 'focus': ['proposal'],
                'reasons': [j1['proposal_rewrite_reason']]}
    categories = answers['primary_gap']['probabilities']
    primary = max(categories, key=categories.get)
    adequacy = {name: sum(answers[spec['question']]['probabilities'].get(str(level), 0.0) for level in (2,3))
                for name,spec in j1['components'].items()}
    weak = [name for name,value in adequacy.items() if value < j1['thresholds']['adequacy']]
    result.update(primary_gap=primary, primary_probability=categories[primary], adequacy=adequacy, weak=weak)
    if primary == 'none' and not weak:
        return result
    if primary not in weak:
        return {**result, 'needs_review': True, 'review_reason': 'choice_score_disagreement'}
    focus = [primary, *(name for name in weak if name != primary)]
    return {**result, 'would_rewrite': True, 'focus': focus,
            'reasons': [j1['components'][name]['rewrite_reason'] for name in focus]}
