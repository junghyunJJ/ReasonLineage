"""The PMID check on a small hand-written event log and a fake PubMed reply."""

from diagnose_data import EFETCH_XML, EVENTS, write_events
from reasonlineage.diagnose.pmid import PubmedRecord, classify, parse_efetch, pmid_uses, run_pmid_check


def test_parse_efetch_and_classify():
    records = parse_efetch(EFETCH_XML)
    assert records["29967351"].title.startswith("Metformin reverses")
    assert classify("metformin", records["29967351"]) == "match"
    assert classify("metformin", records["20866024"]) == "unrelated"
    assert classify("metformin", None) == "missing"
    pair = PubmedRecord("1", "CXCL12 signals through CXCR4", "CXCL12 signals through CXCR4")
    assert classify("CXCL12–CXCR4", pair) == "match" and classify("CXCL12–CCR7", pair) == "unrelated"


def test_pmid_uses_mark_inherited_and_new_citations():
    uses, empty = pmid_uses(EVENTS)
    origins = {(u["candidate"], u["pmid"]): u["origin"] for u in uses}
    assert origins == {("c001", "29967351"): "new", ("c005", "29967351"): "inherited",
                       ("c005", "20866024"): "new", ("c005", "11111111"): "new"}
    assert empty == [{"candidate": "c001", "generation": 0, "item": "imatinib"}]


def test_run_pmid_check_counts_verdicts(tmp_path):
    write_events(tmp_path)
    fetched = []
    summary = run_pmid_check(tmp_path, fetch=lambda ids: fetched.append(list(ids)) or EFETCH_XML)
    assert fetched == [["11111111", "20866024", "29967351"]]  # each PMID once
    assert summary == {"citations": 4, "match": 2, "unrelated": 1, "missing": 1, "items_without_pmids": 1}
