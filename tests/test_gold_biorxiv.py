"""bioRxiv preprints as gold set A (bioRxiv design 4): pool, sentences, DeepSeek steps, review, files."""

import hashlib

import pytest

from reasonlineage.gold import biorxiv as bx


WORDS = " ".join(["word"] * 130)


def record(doi="10.1/a", version="1", date="2026-07-01", type_="new results", published="NA", title="A study",
           abstract=WORDS):
    return {"doi": doi, "version": version, "date": date, "type": type_, "published": published, "title": title,
            "abstract": abstract, "category": "neuroscience"}


# --- 4.1 the pool ---

@pytest.mark.parametrize("change, kept", [
    ({}, True),
    ({"date": "2026-06-30"}, False),
    ({"date": "2026-10-01"}, True),
    ({"date": "2026-10-02"}, False),
    ({"version": "2"}, False),
    ({"type_": "confirmatory results"}, False),
    ({"published": "10.1038/x"}, False),
    ({"abstract": " ".join(["word"] * 119)}, False),
    ({"title": "WITHDRAWN: A study"}, False),
    ({"abstract": "This manuscript has been withdrawn by the authors. " + WORDS}, False),
    ({"abstract": "Patients who withdrew from treatment were followed. " + WORDS}, True),
])
def test_only_first_versions_posted_in_the_window_and_not_in_a_journal_are_kept(change, kept):
    assert bx.keep(record(**change)) is kept


def page(records, total):
    return {"messages": [{"status": "ok", "total": str(total)}], "collection": records}


def test_a_field_is_read_page_by_page_and_each_page_fetched_once(tmp_path):
    pages = {0: page([record("10.1/a"), record("10.1/b")], 3), 2: page([record("10.1/c")], 3)}
    asked = []

    def get(url):
        cursor = int(url.split("/")[-1].split("?")[0])
        asked.append(cursor)
        return pages[cursor]

    assert [r["doi"] for r in bx.fetch_category("neuroscience", tmp_path, get)] == ["10.1/a", "10.1/b", "10.1/c"]
    assert asked == [0, 2]
    assert len(bx.fetch_category("neuroscience", tmp_path, lambda url: pytest.fail("fetched again"))) == 3


def test_a_failed_fetch_names_the_page(tmp_path):
    def get(url):
        raise OSError("connection reset")

    with pytest.raises(bx.SourceError, match="could not fetch .*cursor|could not fetch https://api.biorxiv.org"):
        bx.fetch_category("immunology", tmp_path, get)


def test_the_pool_keeps_one_entry_per_doi_in_doi_order(tmp_path):
    by_field = {"immunology": [record("10.1/b"), record("10.1/a", version="2")],
                "neuroscience": [record("10.1/b"), record("10.1/a")]}

    def get(url):
        field = url.split("category=")[1]
        return page(by_field.get(field, []), len(by_field.get(field, [])))

    pool = bx.build_pool(tmp_path, get)
    assert [(p["doi"], p["category"]) for p in pool] == [("10.1/a", "neuroscience"), ("10.1/b", "immunology")]
    assert set(pool[0]) == {"doi", "category", "date", "title", "abstract"}


def test_a_pool_file_that_is_not_the_recorded_one_is_refused(tmp_path):
    path = tmp_path / "pool.json"
    path.write_bytes(bx.pool_bytes([{"doi": "10.1/a"}]))
    assert bx.load_pool(path, hashlib.sha256(path.read_bytes()).hexdigest()) == [{"doi": "10.1/a"}]
    with pytest.raises(bx.SourceError, match="not the recorded"):
        bx.load_pool(path, "0" * 64)
