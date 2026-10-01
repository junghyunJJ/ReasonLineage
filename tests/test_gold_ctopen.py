"""CT Open as the source of gold v0 (gold v0 design 4): safe loading, trial selection, review, grouping, files."""

import hashlib
import pickle

import pytest

from reasonlineage.gold import ctopen

FIRED = []


def fire():
    FIRED.append("ran")


class Carrier:
    """Loading a pickled Carrier would call fire(): a stand-in for a file that carries code."""

    def __reduce__(self):
        return (fire, ())


PLAIN = pickle.dumps({("NCT00000001", "{}"): {"arms": [], "n": 1.5, "pair": (1, 2)}})


def pin(monkeypatch, sha256):
    monkeypatch.setitem(ctopen.SETS, "test-2025", {"file": "Test.pickle", "commit": "abc123", "sha256": sha256, "after": "2025-01-01"})


def test_plain_data_loads():
    assert ctopen.safe_load(PLAIN) == {("NCT00000001", "{}"): {"arms": [], "n": 1.5, "pair": (1, 2)}}


def test_a_file_that_carries_code_is_refused_without_running_it():
    with pytest.raises(ctopen.SourceError, match="more than plain data"):
        ctopen.safe_load(pickle.dumps({"x": Carrier()}))
    assert FIRED == []


def test_a_pinned_set_is_fetched_once_and_its_checksum_checked(tmp_path, monkeypatch):
    pin(monkeypatch, hashlib.sha256(PLAIN).hexdigest())
    fetched = []

    def download(url):
        fetched.append(url)
        return PLAIN

    assert ctopen.load_set("test-2025", cache=tmp_path, download=download) == ctopen.safe_load(PLAIN)
    assert ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: pytest.fail("fetched twice"))
    assert fetched == ["https://raw.githubusercontent.com/ClinicalTrial-OpenChallenge/CT_Open/abc123/datasets/Test.pickle"]


def test_a_file_that_is_not_the_pinned_one_is_refused(tmp_path, monkeypatch):
    pin(monkeypatch, "0" * 64)
    with pytest.raises(ctopen.SourceError, match="not the pinned"):
        ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: PLAIN)


def test_a_file_that_is_not_a_dict_of_entries_is_refused(tmp_path, monkeypatch):
    listed = pickle.dumps([1, 2])
    pin(monkeypatch, hashlib.sha256(listed).hexdigest())
    with pytest.raises(ctopen.SourceError, match="dict of entries"):
        ctopen.load_set("test-2025", cache=tmp_path, download=lambda url: listed)


def test_an_unknown_set_and_a_failed_download_are_source_errors(tmp_path):
    with pytest.raises(ctopen.SourceError, match="unknown CT Open set"):
        ctopen.load_set("spring-2031", cache=tmp_path)

    def down(url):
        raise OSError("no route to host")

    with pytest.raises(ctopen.SourceError, match="could not fetch"):
        ctopen.load_set("summer-2025", cache=tmp_path, download=down)


def test_the_2025_sets_are_pinned():
    assert ctopen.SETS["winter-2025"]["after"] == "2025-02-01" and ctopen.SETS["summer-2025"]["after"] == "2025-09-01"
    assert all(len(p["sha256"]) == 64 and len(p["commit"]) == 40 for p in ctopen.SETS.values())
