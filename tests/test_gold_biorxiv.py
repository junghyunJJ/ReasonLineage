"""bioRxiv preprints as gold set A (bioRxiv design 4): pool, sentences, DeepSeek steps, review, files."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from reasonlineage.backends.base import BackendError
from reasonlineage.diagnose.gold import correctness
from reasonlineage.engine.config import load_task
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


# --- 4.3 sentences ---

def test_abbreviations_initials_and_decimals_do_not_end_a_sentence():
    text = ("Neurons fire (e.g. in cortex). Smith et al. showed this in Fig. 2. J. Doe agreed. "
            "Levels rose 3.5-fold. 12 mice were used. Thus X holds!")
    assert bx.sentences(text) == ["Neurons fire (e.g. in cortex).", "Smith et al. showed this in Fig. 2.",
                                  "J. Doe agreed.", "Levels rose 3.5-fold.", "12 mice were used.", "Thus X holds!"]


@pytest.mark.parametrize("first, ok", [(1, False), (2, True), (4, True), (5, False), ("2", False), (None, False)])
def test_a_split_needs_background_before_and_results_after(first, ok):
    assert (bx.split_problems(["a.", "b.", "c.", "d."], first) == []) is ok


def test_results_over_400_words_are_too_long():
    parts = ["Background.", " ".join(["x"] * 401)]
    assert bx.split_problems(parts, 2) == ["the results have 401 words, more than 400"]


REAL = "Drug X increased neuronal firing by 40% in mouse cortex."
REV = "Drug X decreased neuronal firing by 40% in mouse cortex."
ALT = "Drug X increased neuronal firing by 40% in mouse retina."


@pytest.mark.parametrize("reversed_, altered, problem", [
    (REV, ALT, None),
    (REAL, ALT, "repeats"),
    (REV, " ".join(REV.split()).upper(), "repeats"),
    (REV, "Short.", "times as long"),
    (None, ALT, "not text"),
])
def test_rewritten_results_must_differ_and_match_the_length(reversed_, altered, problem):
    problems = bx.alteration_problems(REAL, reversed_, altered)
    assert (problems == []) if problem is None else any(problem in p for p in problems)


# --- 4.3-4.5 DeepSeek steps, with a fake backend ---

ABSTRACT = ("Cortex matters for behavior. We gave drug X to mice and recorded neurons. "
            "Drug X increased neuronal firing by 40% in mouse cortex. This suggests X excites cortex.")
PAPER = {"doi": "10.1/p", "category": "neuroscience", "date": "2026-07-02", "title": "X excites cortex", "abstract": ABSTRACT}
MEMBER = SimpleNamespace(model="deepseek", effort="max")


class FakeDeepSeek:
    """Answers each kind of request by its system prompt; `tell` picks a letter for the wording check."""

    def __init__(self, first_result=3, rewrite=None, tell="real", fail_first=0):
        self.first_result, self.tell, self.fail_first = first_result, tell, fail_first
        self.rewrite = rewrite or {"reversed": "Drug X decreased neuronal firing by 40% in mouse cortex. This suggests X calms cortex.",
                                   "altered": "Drug X increased neuronal firing by 40% in mouse retina. This suggests X excites retina."}
        self.calls = []

    async def complete(self, request):
        self.calls.append(request.system)
        if len(self.calls) <= self.fail_first:
            raise BackendError("server busy")
        if request.system == bx.LABEL_SYSTEM:
            return SimpleNamespace(data={"first_result": self.first_result})
        if request.system == bx.ALTER_SYSTEM:
            return SimpleNamespace(data=dict(self.rewrite))
        lines = [line for line in request.prompt.split("\n\n")]
        real = "Drug X increased neuronal firing by 40% in mouse cortex. This suggests X excites cortex."
        letter = next(line[7] for line in lines if line[10:] == real) if self.tell == "real" else self.tell
        return SimpleNamespace(data={"real": letter})


def make(backend, paper=PAPER):
    return asyncio.run(bx.make_candidate(paper, backend, MEMBER))


def test_a_paper_whose_real_result_is_hidden_in_the_wording_is_kept():
    entry = make(FakeDeepSeek(tell="A"))
    assert entry["status"] == "kept" and entry["tell"] == [True, False, False]
    assert entry["context"] == "Cortex matters for behavior. We gave drug X to mice and recorded neurons."
    assert entry["result"] == "Drug X increased neuronal firing by 40% in mouse cortex. This suggests X excites cortex."


def test_a_paper_whose_real_result_shows_in_the_wording_is_dropped():
    entry = make(FakeDeepSeek(tell="real"))
    assert entry["status"] == "dropped" and "wording alone" in entry["reason"] and entry["tell"] == [True, True, True]


def test_a_split_with_no_background_is_dropped_before_rewriting():
    backend = FakeDeepSeek(first_result=1)
    entry = make(backend)
    assert entry["status"] == "dropped" and "no background" in entry["reason"]
    assert backend.calls == [bx.LABEL_SYSTEM]


def test_unusable_rewrites_are_asked_once_more_then_dropped():
    backend = FakeDeepSeek(rewrite={"reversed": "Short.", "altered": "Short too."})
    entry = make(backend)
    assert entry["status"] == "dropped" and "rewritten" in entry["reason"]
    assert backend.calls == [bx.LABEL_SYSTEM, bx.ALTER_SYSTEM, bx.ALTER_SYSTEM]


def test_a_failed_call_is_tried_once_more():
    assert make(FakeDeepSeek(tell="A", fail_first=1))["status"] == "kept"


def papers(n_per_field):
    return [dict(PAPER, doi=f"10.1/{field}-{i}", category=field) for field in bx.CATEGORIES for i in range(n_per_field)]


def test_candidates_follow_a_fixed_order_per_field_and_reuse_earlier_results():
    pool = papers(3)
    found = asyncio.run(bx.candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    assert [e["category"] for e in found] == list(bx.CATEGORIES) and all(e["status"] == "kept" for e in found)
    again = asyncio.run(bx.candidates("set-a", pool, 1, None, MEMBER, previous=found))
    assert again == found
    other = asyncio.run(bx.candidates("set-b", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    assert [e["doi"] for e in other] != [e["doi"] for e in found]


def test_excluded_papers_are_skipped():
    pool = papers(2)
    first = asyncio.run(bx.candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    second = asyncio.run(bx.candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER, exclude={e["doi"] for e in first}))
    assert not {e["doi"] for e in first} & {e["doi"] for e in second}


def test_a_field_that_runs_out_of_usable_papers_stops_with_the_count():
    with pytest.raises(bx.SourceError, match="only 0 of 1 papers usable after trying all 2"):
        asyncio.run(bx.candidates("set-a", papers(2), 1, FakeDeepSeek(tell="real"), MEMBER))


# --- 4.6 review and 4.7 files ---

def kept(field, i):
    return {"doi": f"10.1/{field}-{i}", "category": field, "status": "kept", "context": f"Background {field} {i}.",
            "result": "Real result.", "reversed": "Reversed result.", "altered": "Altered result.", "title": "Title tells"}


def found(n_per_field=2):
    return [kept(field, i) for field in bx.CATEGORIES for i in range(n_per_field)]


def keep_all(entries):
    return {"keep": bx.review_sample(entries), "drop": []}


SOURCE = {"api": bx.API, "pool_sha256": "abc"}


def test_the_review_sample_is_the_first_kept_paper_of_each_field():
    entries = found()
    assert bx.review_sample(entries) == [f"10.1/{f}-0" for f in bx.CATEGORIES]
    assert bx.review_sample(entries, {"10.1/immunology-0"})[2] == "10.1/immunology-1"


def test_the_review_sheet_shows_the_real_and_rewritten_results():
    sheet = bx.review_sheet(found(), ["10.1/neuroscience-0"])
    assert "## neuroscience — 10.1/neuroscience-0" in sheet and "**Real result.** Real result." in sheet
    assert "**Reversed.**" in sheet and "**Altered.**" in sheet


@pytest.mark.parametrize("review, problem", [
    ({"keep": [f"10.1/{f}-0" for f in bx.CATEGORIES[:4]], "drop": []}, "cell_biology-0: not reviewed"),
    ({"keep": [f"10.1/{f}-0" for f in bx.CATEGORIES] + ["10.1/none"], "drop": []}, "10.1/none: not a kept candidate"),
    ({"keep": [f"10.1/{f}-0" for f in bx.CATEGORIES] * 2, "drop": []}, "reviewed twice"),
    ({"keep": [f"10.1/{f}-0" for f in bx.CATEGORIES[1:]], "drop": [{"doi": "10.1/pharmacology_and_toxicology-0", "why": " "}]},
     "dropped without a reason"),
])
def test_review_rules_are_enforced(review, problem):
    assert any(problem in p for p in bx.check_review(review, found()))


def test_build_writes_tasks_that_hide_the_title_and_shuffle_the_letters(tmp_path):
    paths = bx.build("set-a", found(1), keep_all(found(1)), 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    gold = json.loads((tmp_path / "gold.json").read_text())
    assert gold["source"] == SOURCE and [p.name for p in paths] == [f"set-a-0{i}.json" for i in range(1, 6)]
    letters = set()
    for path in paths:
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert task.candidates == ("Result A", "Result B", "Result C") and task.category == "analytical"
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}
        assert "Title tells" not in task.question and task.question.startswith("Background ")
        letter = truth["approved"][0][-1]
        assert f"- Result {letter}: Real result." in task.question
        assert correctness([truth["approved"][0], *truth["failed"]], truth) == 1.0
        letters.add(letter)
    assert len(letters) > 1  # the real result is not always in the same place
    again = tmp_path / "again"
    bx.build("set-a", found(1), keep_all(found(1)), 1, SOURCE, again / "tasks", again / "gold.json")
    assert (again / "gold.json").read_text() == (tmp_path / "gold.json").read_text()


def test_a_paper_dropped_in_review_is_replaced_by_the_next_kept_one(tmp_path):
    entries = found(2)
    review = {"keep": [d for d in bx.review_sample(entries) if "immunology" not in d] + ["10.1/immunology-1"],
              "drop": [{"doi": "10.1/immunology-0", "why": "the altered result is not clearly different"}]}
    bx.build("set-a", entries, review, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    assert json.loads((tmp_path / "gold.json").read_text())["tasks"]["set-a-03"]["doi"] == "10.1/immunology-1"


def test_build_stops_when_review_left_too_few_papers_or_breaks_a_rule(tmp_path):
    entries = found(1)
    review = {"keep": bx.review_sample(entries)[1:], "drop": [{"doi": "10.1/pharmacology_and_toxicology-0", "why": "leaks"}]}
    with pytest.raises(bx.ReviewError, match="run `candidates` again"):
        bx.build("set-a", entries, review, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    with pytest.raises(bx.ReviewError, match="not reviewed"):
        bx.build("set-a", entries, {"keep": [], "drop": []}, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    assert not (tmp_path / "gold.json").exists()


def test_build_refuses_task_files_it_does_not_make(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "set-a-09.json").write_text("{}")
    with pytest.raises(bx.ReviewError, match="set-a-09.json is not built by this review"):
        bx.build("set-a", found(1), keep_all(found(1)), 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")


# --- final review fixes (2026-10-02) ---

def test_api_markup_is_decoded_to_the_characters_authors_wrote():
    # The real result is the abstract's own text; if it kept "{beta}" while a rewrite wrote "β", the markup alone
    # would tell the real one (final review).
    raw = ("IL-1{beta} rose {+/-} 5 at 37{degrees}C in 10 {micro}M, [&ge;]2-fold, p &lt; 0.05 and [~]3 cells, "
           "NF-{kappa}B and {Delta}F508")
    assert bx.clean_abstract(raw) == "IL-1β rose ± 5 at 37°C in 10 µM, ≥2-fold, p < 0.05 and ~3 cells, NF-κB and ΔF508"


@pytest.mark.parametrize("raw", [
    "Highlights C_LIO_LIThe cortex fires C_LI " + WORDS,
    "O_FIG O_LINKSMALLFIG C_FIG " + WORDS,
    "BackgroundThe cortex matters. " + WORDS,
    "Cells grew in {termination} medium. " + WORDS,
])
def test_abstracts_with_list_figure_heading_or_unknown_markup_are_left_out(raw):
    assert bx.clean_abstract(raw) is None


def test_a_paper_withdrawn_in_a_later_version_is_left_out_of_the_pool(tmp_path):
    records = [record("10.1/w"), record("10.1/w", version="2", date="2026-08-11", type_="withdrawn",
                                        title="WITHDRAWN: A study"), record("10.1/k", abstract="{beta} " + WORDS)]

    def get(url):
        return page(records if "neuroscience" in url else [], 3 if "neuroscience" in url else 0)

    pool = bx.build_pool(tmp_path, get)
    assert [p["doi"] for p in pool] == ["10.1/k"] and pool[0]["abstract"].startswith("β ")


def test_rewrites_are_stored_with_plain_spacing():
    backend = FakeDeepSeek(tell="A", rewrite={
        "reversed": "Drug X decreased neuronal firing by 40% in mouse cortex.\nThis suggests  X calms cortex.",
        "altered": "Drug X increased neuronal firing by 40% in mouse retina. This suggests X excites retina."})
    entry = make(backend)
    assert entry["reversed"] == "Drug X decreased neuronal firing by 40% in mouse cortex. This suggests X calms cortex."


@pytest.mark.parametrize("text, count", [
    ("Cells grew in 2D. Our metrics improved.", 2),
    ("NF-κB was active. Levels rose.", 2),
    ("We treated mice with vehicle. scRNA-seq analysis showed loss of Lgr5. mTOR was inhibited. p53 rose. β-cells died.", 5),
    ("Infection with K. pneumoniae rose in mice.", 1),
    ("Smith et al. showed this, e.g. in cortex.", 1),
])
def test_sentences_end_after_a_digit_or_a_lowercase_start_but_not_after_initials(text, count):
    # Under-splitting merged a method sentence with a result sentence in about 10% of abstracts (final review).
    assert len(bx.sentences(text)) == count


def test_a_paper_dropped_in_review_stays_on_record_and_the_next_one_is_added():
    pool = papers(3)
    first = asyncio.run(bx.candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    gone = first[0]["doi"]
    again = asyncio.run(bx.candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER, previous=first, dropped={gone}))
    field = [e for e in again if e["category"] == first[0]["category"]]
    assert field[0]["doi"] == gone and len(field) == 2 and field[1]["status"] == "kept"


@pytest.mark.parametrize("per_field", [1, 4])
def test_the_real_result_is_spread_evenly_over_the_letters(tmp_path, per_field):
    # A pull toward the first option would inflate the pilot rule if the real result sat mostly at A; the
    # per-task shuffle put it at A in 4 of the 5 pilot tasks (final review).
    entries = found(per_field)
    bx.build("set-a", entries, keep_all(entries), per_field, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    tasks = json.loads((tmp_path / "gold.json").read_text())["tasks"].values()
    counts = [sum(t["approved"][0] == f"Result {x}" for t in tasks) for x in bx.LETTERS]
    assert sum(counts) == 5 * per_field and max(counts) - min(counts) <= 1
