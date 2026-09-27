from helpers import scored, uniform
from reasonlineage.core import Candidate, LineageLog, select_survivors


def test_lineage_round_trip(tmp_path):
    log = LineageLog(tmp_path / "run" / "lineage.jsonl")
    child = Candidate("mut-gen-1-1", "D1 > D3 > D2", "codex", "mutation", ("seed-2",), generation=1)
    log.candidate_created(child)
    child.judge_scores = [uniform(0.7, "claude"), uniform(0.8, "gemini")]
    child.fitness, child.critique = 0.75, ["D2 evidence is thin"]
    log.candidate_scored(child)
    log.selection(1, select_survivors([scored("seed-2", 0.7, "codex"), child], 1))

    records = LineageLog.read(log.path)
    assert [r["event"] for r in records] == ["candidate.created", "candidate.scored", "selection"]
    assert records[0]["parent_ids"] == ["seed-2"]
    assert [j["judge"] for j in records[1]["judges"]] == ["claude", "gemini"]
    assert records[2]["survivors"] == ["mut-gen-1-1"]
