import asyncio
import importlib.util
import io
import json
import urllib.error

import pytest

from reasonlineage.checks.base import CheckerError
from reasonlineage.checks.jev import JevChecker, parse_jev
from reasonlineage.checks.questions import j1_questions
from reasonlineage.protocol import load_protocol
from test_jev import REPLY


def credentials():
    assert importlib.util.find_spec('reasonlineage.checks.credentials'), 'safe dotenv reader is missing'
    from reasonlineage.checks.credentials import read_dotenv_key
    return read_dotenv_key


def test_dotenv_reader_never_executes_expands_or_outputs_values(tmp_path, capsys):
    reader = credentials()
    path = tmp_path / '.env'
    secret = 'test-key-$(touch_should_not_run)-${UNSET}'
    text = f'OTHER=value\nexport JEV_API_KEY="{secret}" # comment\n'
    path.write_text(text)
    assert reader(path) == secret
    assert path.read_text() == text
    output = capsys.readouterr()
    assert secret not in output.out + output.err


@pytest.mark.parametrize('text', ['JEV_API_KEY="test-secret-unclosed',
                                  'JEV_API_KEY=first-test-secret\nJEV_API_KEY=second-test-secret'])
def test_malformed_or_duplicate_key_is_rejected_without_value(text, tmp_path):
    path = tmp_path / '.env'
    path.write_text(text)
    with pytest.raises(ValueError) as error:
        credentials()(path)
    assert 'test-secret' not in str(error.value)


def test_http_error_cannot_echo_credential(monkeypatch):
    secret = 'test-only-private-key'
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, secret, {}, io.BytesIO(secret.encode()))
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(CheckerError, match='401') as error:
        asyncio.run(JevChecker(secret, 'jev-1.13.0', data_sensitivity='public').ask(
            'public text', j1_questions(load_protocol(), 'candidate')))
    assert secret not in str(error.value)


@pytest.mark.parametrize('probability', [float('nan'), -0.1, 1.1])
def test_invalid_probability_cannot_be_used_as_gate_evidence(probability):
    reply = json.loads(json.dumps(REPLY))
    reply['answers']['top_item_argument']['noul'] = probability
    with pytest.raises(CheckerError):
        parse_jev(reply, j1_questions(load_protocol(), 'candidate'))


def test_provider_usage_is_available_for_checker_metering():
    result = parse_jev(REPLY, j1_questions(load_protocol(), 'candidate'))
    assert result.usage == {'input_tokens': 300, 'output_tokens': 12}
