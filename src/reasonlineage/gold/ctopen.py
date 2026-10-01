"""CT Open (arXiv 2604.16742) as the source of gold v0 (gold v0 design).

Every quarter CT Open publishes clinical trial outcome questions whose answers were not public before the
window's cutoff, with the dated reports each answer came from. Gold v0 keeps the primary-endpoint results of
trials that test an already approved drug and were first reported after every panel model's training cutoff.
"""

import hashlib
import io
import pickle
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO = "ClinicalTrial-OpenChallenge/CT_Open"
COMMIT_2025 = "cc78ff33e90cc8da01f9db4e3b3d35dcc9ce4539"
# Each set's file, pinned by commit and sha256, and the earliest first-report date it accepts (gold v0 design 4.1).
SETS: dict[str, dict[str, str]] = {
    "winter-2025": {"file": "Winter_2025.pickle", "commit": COMMIT_2025,
                    "sha256": "849c36f258a84787a5360500ca246c800880418e5cb1996f73f8cb4927736141", "after": "2025-02-01"},
    "summer-2025": {"file": "Summer_2025.pickle", "commit": COMMIT_2025,
                    "sha256": "1b01f622d68c42d522916734cf4b04fb5a437901b6cea2f7e39df91085ca9567", "after": "2025-09-01"},
}
CACHE = Path.home() / ".cache" / "reasonlineage" / "ctopen"


class SourceError(RuntimeError):
    """A CT Open file could not be fetched, is not the pinned file, or does not hold the expected plain data."""


class _PlainOnly(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"{module}.{name}")


def safe_load(data: bytes) -> Any:
    """The pickled object, if it is plain data (dicts, lists, tuples, strings, numbers).

    A pickle can run code while it loads, so every class and function it asks for is refused.
    """
    try:
        return _PlainOnly(io.BytesIO(data)).load()
    except pickle.UnpicklingError as exc:
        raise SourceError(f"the file holds more than plain data ({exc}); refusing to load it") from None


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def load_set(name: str, cache: str | Path = CACHE, download: Callable[[str], bytes] = _download) -> dict:
    """The entries of a pinned CT Open set, fetched once into `cache`."""
    if name not in SETS:
        raise SourceError(f"unknown CT Open set {name!r}; add it to ctopen.SETS with its commit, file, sha256 "
                          f"and date (gold v0 design 4.1)")
    pin = SETS[name]
    url = f"https://raw.githubusercontent.com/{REPO}/{pin['commit']}/datasets/{pin['file']}"
    path = Path(cache) / pin["file"]
    if not path.exists():
        try:
            data = download(url)
        except OSError as exc:
            raise SourceError(f"could not fetch {url}: {exc}") from None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != pin["sha256"]:
        raise SourceError(f"{path} has sha256 {digest}, not the pinned {pin['sha256']}; delete it to fetch again")
    entries = safe_load(data)
    if not isinstance(entries, dict):
        raise SourceError(f"{path} does not hold a dict of entries (gold v0 design 4.2)")
    return entries
