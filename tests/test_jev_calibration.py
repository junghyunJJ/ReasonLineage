import importlib.util
from collections import Counter

from test_pilot_run import ROOT


def calibration():
    assert importlib.util.find_spec('reasonlineage.checks.calibration'), 'J1 calibration cases are missing'
    from reasonlineage.checks import calibration
    return calibration


def test_calibration_covers_normal_and_four_deliberate_defects_in_both_cases():
    cases = calibration().build_cases(ROOT)
    assert len(cases) == len({c['id'] for c in cases}) == 30
    assert Counter(c['kind'] for c in cases) == dict.fromkeys(
        ['normal', 'refusal', 'meta', 'grader', 'no_argument'], 6)
    assert Counter(c['case'] for c in cases) == {'als': 15, 'aml': 15}
    assert all(c['expected_rewrite'] == (c['kind'] != 'normal') for c in cases)
    assert all(c['answer']['answer'] and len(c['answer']['ranking']) == 1 for c in cases)


def test_one_false_rewrite_or_missed_defect_prevents_activation():
    m = calibration()
    cases = m.build_cases(ROOT)
    rows = [{'id': c['id'], 'status': 'completed', 'would_rewrite': c['expected_rewrite']} for c in cases]
    assert m.summarize(cases, rows)['passed']
    rows[0]['would_rewrite'] = not rows[0]['would_rewrite']
    assert not m.summarize(cases, rows)['passed']
    assert not m.summarize(cases, rows[:-1])['passed']


def test_certificate_binds_question_text_thresholds_and_both_validation_sets(tmp_path):
    import json
    import shutil
    from reasonlineage.protocol import load_protocol
    m = calibration()
    assert hasattr(m, 'validate_certificate'), 'calibration proof validation is missing'
    root = ROOT / 'research/co-scientist-pilot/protocol-three-initial-jev'
    m.validate_certificate(load_protocol(root))
    copy = tmp_path / 'profile'
    shutil.copytree(root, copy)
    path = copy / 'protocol.json'
    data = json.loads(path.read_text())
    data['j1']['thresholds']['top_item_argument'] = .4
    path.write_text(json.dumps(data))
    import pytest
    with pytest.raises(ValueError, match='calibration'):
        m.validate_certificate(load_protocol(copy))
