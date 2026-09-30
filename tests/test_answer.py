import pytest

from reasonlineage.engine.answer import (
    AnswerIssues,
    answer_schema,
    from_content,
    normalize_answer,
    normalize_pmids,
    ranking_line,
    render_for_judge,
    to_content,
    top_item,
    validate_answer,
)

CANDIDATES = ["metformin", "imatinib", "sildenafil"]


def entry(item, pmids=()):
    return {"item": item, "promisingness": 0.5, "confidence": 0.5, "pmids": list(pmids)}


def answer(items, prose=None):
    return {"answer": prose if prose is not None else " ".join(items), "ranking": [entry(i) for i in items]}


def test_schema_fixes_candidate_names_and_count():
    ranking = answer_schema(CANDIDATES)["properties"]["ranking"]
    assert ranking["minItems"] == ranking["maxItems"] == 3
    assert ranking["items"]["properties"]["item"]["enum"] == CANDIDATES
    assert answer_schema(CANDIDATES)["additionalProperties"] is False


def test_open_question_schema_allows_3_to_10_items():
    ranking = answer_schema(None)["properties"]["ranking"]
    assert (ranking["minItems"], ranking["maxItems"]) == (3, 10)
    assert "enum" not in ranking["items"]["properties"]["item"]


def test_case_and_space_variants_map_to_task_names():
    raw = {"answer": "Metformin first, then IMATINIB, then sildenafil.",
           "ranking": [entry(" Metformin "), entry("IMATINIB"), entry("sildenafil")]}
    data = normalize_answer(raw, CANDIDATES)
    assert [e["item"] for e in data["ranking"]] == CANDIDATES
    assert validate_answer(data, CANDIDATES) == AnswerIssues()


def test_missing_extra_and_repeated_items_are_hard_issues():
    data = normalize_answer(answer(["metformin", "metformin", "aspirin"]), CANDIDATES)
    issues = validate_answer(data, CANDIDATES)
    assert any("leaves out: imatinib, sildenafil" in h for h in issues.hard)
    assert any("not in the task: aspirin" in h for h in issues.hard)
    assert any("more than once: metformin" in h for h in issues.hard)


def test_item_never_named_in_prose_is_a_soft_issue():
    data = normalize_answer(answer(CANDIDATES, prose="Only metformin and imatinib are discussed."), CANDIDATES)
    issues = validate_answer(data, CANDIDATES)
    assert issues.hard == ()
    assert issues.soft == ("The prose never names the ranked item sildenafil.",)
    assert issues.describe() == "- The prose never names the ranked item sildenafil."


def test_open_question_rejects_repeats_only():
    assert validate_answer(answer(["a", "b", "c"]), None) == AnswerIssues()
    assert validate_answer(answer(["a", "A", "c"]), None).hard == ("The ranking lists an item more than once.",)


def test_pmids_are_cleaned():
    assert normalize_pmids(["PMID: 29967351", "29967351", "PMC7654321", "unknown", " 24836312 "]) == ["29967351", "24836312"]


@pytest.mark.parametrize("bad", [
    None,
    {"answer": "x"},
    {"answer": "x", "ranking": [{"promisingness": 0.5}]},
    {"answer": "x", "ranking": [{"item": "a", "promisingness": 1.5, "confidence": 0.5, "pmids": []}]},
])
def test_bad_structure_raises(bad):
    with pytest.raises(ValueError):
        normalize_answer(bad, None)


def test_render_for_judge_lists_the_ranking_with_pmids():
    data = normalize_answer({"answer": "Prose.", "ranking": [entry("metformin", ["29967351"]), entry("imatinib")]}, None)
    text = render_for_judge(data)
    assert text.startswith("Prose.\n\nFinal ranking:\n1. metformin")
    assert "PMIDs: 29967351" in text and "PMIDs: none" in text
    assert top_item(data) == "metformin"
    assert ranking_line(data) == "metformin > imatinib"
    assert from_content(to_content(data)) == data
