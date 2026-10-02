"""The bioRxiv build script (bioRxiv design 3, 4): candidates from a saved pool, then build from the review."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_biorxiv.py"
sys.path.insert(0, str(ROOT / "scripts"))

import build_biorxiv  # noqa: E402
from reasonlineage.gold import biorxiv as bx  # noqa: E402

FIELDS = bx.CATEGORIES


def pool_files(tmp_path, n_per_field=2):
    pool = [{"doi": f"10.1/{f}-{i}", "category": f, "date": "2026-07-02", "title": "T", "abstract": "A."}
            for f in FIELDS for i in range(n_per_field)]
    full = tmp_path / "pool-full.json"
    full.write_bytes(bx.pool_bytes(pool))
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"full_pool": str(full), "sha256": hashlib.sha256(full.read_bytes()).hexdigest()}))
    return index


async def fake_candidate(paper, backend, member):
    return {**paper, "status": "kept", "context": "Background.", "result": "Real.", "reversed": "Reversed.",
            "altered": "Altered."}


def run_candidates(tmp_path, monkeypatch, *extra):
    monkeypatch.setattr(bx, "make_candidate", fake_candidate)
    monkeypatch.setattr(build_biorxiv, "load_setup",
                        lambda path: SimpleNamespace(local_checkers={"deepseek": SimpleNamespace(model="deepseek-test")}))
    monkeypatch.setattr(build_biorxiv, "build_backend", lambda member, n: None)
    return build_biorxiv.main(["--index", str(pool_files(tmp_path)), "--gold-root", str(tmp_path / "gold"),
                               "candidates", "set-a", "--per-category", "1", *extra])


def test_candidates_step_saves_the_papers_and_a_review_sheet(tmp_path, monkeypatch, capsys):
    assert run_candidates(tmp_path, monkeypatch) == 0
    saved = json.loads((tmp_path / "gold" / "set-a" / "candidates.json").read_text())
    assert len(saved["papers"]) == 5 and saved["source"]["writer"] == "deepseek-test" and saved["source"]["per_category"] == 1
    assert (tmp_path / "gold" / "set-a" / "review_sheet.md").read_text().count("## ") == 5
    assert "5 kept, 0 dropped; review these:" in capsys.readouterr().out


def test_candidates_step_skips_another_sets_papers(tmp_path, monkeypatch):
    assert run_candidates(tmp_path, monkeypatch) == 0
    (tmp_path / "gold" / "set-a").rename(tmp_path / "gold" / "pilot")
    assert run_candidates(tmp_path, monkeypatch, "--exclude-set", "pilot") == 0
    first = {e["doi"] for e in json.loads((tmp_path / "gold" / "pilot" / "candidates.json").read_text())["papers"]}
    second = {e["doi"] for e in json.loads((tmp_path / "gold" / "set-a" / "candidates.json").read_text())["papers"]}
    assert first and second and not first & second


def test_candidates_step_without_a_pool_says_to_fetch(tmp_path, capsys):
    code = build_biorxiv.main(["--index", str(tmp_path / "none.json"), "--gold-root", str(tmp_path), "candidates", "set-a",
                               "--per-category", "1"])
    assert code == 1 and "run `fetch` first" in capsys.readouterr().err


def build(tmp_path, review):
    gold = tmp_path / "gold" / "set-a"
    gold.mkdir(parents=True)
    papers = [{"doi": f"10.1/{f}", "category": f, "status": "kept", "context": "Background.", "result": "Real.",
               "reversed": "Reversed.", "altered": "Altered."} for f in FIELDS]
    (gold / "candidates.json").write_text(json.dumps({"source": {"per_category": 1}, "papers": papers}))
    if review is not None:
        (gold / "review.json").write_text(json.dumps(review))
    return subprocess.run([sys.executable, str(SCRIPT), "--gold-root", str(tmp_path / "gold"), "--tasks-root",
                           str(tmp_path / "tasks"), "build", "set-a"], capture_output=True, text=True)


def test_build_step_writes_tasks_and_gold(tmp_path):
    result = build(tmp_path, {"keep": [f"10.1/{f}" for f in FIELDS], "drop": []})
    assert result.returncode == 0, result.stderr
    assert "5 task files" in result.stdout and (tmp_path / "gold" / "set-a" / "gold.json").exists()


def test_build_step_needs_the_review(tmp_path):
    result = build(tmp_path, None)
    assert result.returncode == 1 and "write review.json first" in result.stderr


def test_build_step_refuses_a_broken_review(tmp_path):
    result = build(tmp_path, {"keep": [], "drop": []})
    assert result.returncode == 1 and "review.json breaks the rules" in result.stderr and "not reviewed" in result.stderr


def test_a_bad_set_name_is_refused(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), "build", "Set_A"], capture_output=True, text=True)
    assert result.returncode == 2 and "lowercase letters" in result.stderr


def test_a_paper_dropped_in_review_is_replaced_and_the_set_builds(tmp_path, monkeypatch):
    # Before the final-review fix the dropped paper vanished from candidates.json and build refused the review.
    assert run_candidates(tmp_path, monkeypatch) == 0
    gold = tmp_path / "gold" / "set-a"
    sample = bx.review_sample(json.loads((gold / "candidates.json").read_text())["papers"])
    drop = [{"doi": sample[0], "why": "the background leaks a result"}]
    (gold / "review.json").write_text(json.dumps({"keep": sample[1:], "drop": drop}))
    assert run_candidates(tmp_path, monkeypatch) == 0
    saved = json.loads((gold / "candidates.json").read_text())["papers"]
    (gold / "review.json").write_text(json.dumps({"keep": bx.review_sample(saved, {sample[0]}), "drop": drop}))
    code = build_biorxiv.main(["--gold-root", str(tmp_path / "gold"), "--tasks-root", str(tmp_path / "tasks"), "build", "set-a"])
    assert code == 0
    tasks = json.loads((gold / "gold.json").read_text())["tasks"]
    assert len(tasks) == 5 and sample[0] not in {t["doi"] for t in tasks.values()}


def test_candidates_step_skips_the_papers_of_several_sets(tmp_path, monkeypatch):
    monkeypatch.setattr(bx, "make_candidate", fake_candidate)
    monkeypatch.setattr(build_biorxiv, "load_setup",
                        lambda path: SimpleNamespace(local_checkers={"deepseek": SimpleNamespace(model="deepseek-test")}))
    monkeypatch.setattr(build_biorxiv, "build_backend", lambda member, n: None)
    index, gold = pool_files(tmp_path, 3), tmp_path / "gold"

    def run(name, *extra):
        assert build_biorxiv.main(["--index", str(index), "--gold-root", str(gold), "candidates", name,
                                   "--per-category", "1", *extra]) == 0
        return {e["doi"] for e in json.loads((gold / name / "candidates.json").read_text())["papers"]}

    one = run("one")
    two = run("two", "--exclude-set", "one")
    three = run("three", "--exclude-set", "one", "--exclude-set", "two")
    assert not (one & two) and not (three & (one | two)) and len(three) == 5

