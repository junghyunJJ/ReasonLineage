"""Read only the named dotenv value without evaluating shell code or expansions."""
import shlex
import subprocess
from pathlib import Path


def shared_dotenv(root):
    result = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                            cwd=root, capture_output=True, text=True, check=True)
    return Path(result.stdout.strip()).parent / '.env'


def read_dotenv_key(path, name='JEV_API_KEY'):
    try:
        lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    except OSError:
        raise ValueError('dotenv credential file is unavailable') from None
    found = None
    for line in lines:
        line = line.strip()
        if line.startswith('export '):
            line = line[7:].lstrip()
        left, separator, right = line.partition('=')
        if not separator or left.strip() != name:
            continue
        if found is not None:
            raise ValueError('dotenv has a duplicate credential entry')
        try:
            values = shlex.split(right, comments=True, posix=True)
        except ValueError:
            raise ValueError('dotenv credential entry is malformed') from None
        if len(values) != 1 or not values[0] or '\n' in values[0] or '\r' in values[0]:
            raise ValueError('dotenv credential entry is empty or malformed')
        found = values[0]
    if found is None:
        raise ValueError('dotenv has no requested credential entry')
    return found
