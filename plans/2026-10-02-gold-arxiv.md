# arXiv 결과 예측 정답지 (A2 세트) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bioRxiv 세트와 같은 과제 방식을 arXiv(기계학습·자연어처리·재료물리·천문·계량경제)에 적용해, 파일럿 5과제와 본 세트 20과제로 1단계를 다시 재고 분석 보고서를 낸다. 생의학 밖에서도 되는지와, 안전 분류기에 막히지 않는 경로를 함께 확인한다.

**Architecture:**
- bioRxiv 모듈의 절반(문장 나누기, DeepSeek 단계, 검토, 파일 쓰기)은 자료와 무관하다. 그 절반을 `gold/abstracts.py`로 옮기고, `gold/biorxiv.py`에는 수집만 남긴다. 동작은 바뀌지 않는다.
- `gold/arxiv.py`가 arXiv 수집과 LaTeX 정리를 맡는다.
- 두 자료의 스크립트가 같아서 `scripts/build_set.py SOURCE …` 하나로 합친다(`build_biorxiv.py`는 지운다).
- 실행과 판정은 기존 `scripts/run_gold.sh`와 `reasonlineage gold --analysis`를 그대로 쓴다. 엔진과 프로토콜(1.0.5)은 바꾸지 않는다.

**Tech Stack:** Python 3.11 이상, 표준 라이브러리만(urllib, xml.etree, re, unicodedata, asyncio, hashlib), pytest, bash, arXiv API, 로컬 vLLM의 DeepSeek-V4-Flash.

**Spec:** `specs/2026-10-02-gold-arxiv-design.md` (과제 방식은 `specs/2026-10-02-gold-biorxiv-design.md`, 판정 규칙은 `specs/2026-09-30-gold-dev-design.md` 6.1–6.2)

**미리 확인한 것 (2026-10-02):**
- 코드를 임시 복사본에서 모두 짜고, 실제 arXiv API로 돌려 봤다.
  - 기간 안의 논문 수: cs.LG 13,944, cs.CL 7,153, cond-mat.mtrl-sci 2,645, astro-ph.GA 1,978, econ.EM 373편.
  - 한 페이지(100편) 기준 쓸 수 있는 논문: cs.LG 48, cs.CL 62, cond-mat 62, astro-ph 54, econ.EM 45편. 나머지는 개정본(v1 아님), 교차 등록, 짧은 초록, 정리 못 하는 LaTeX다.
  - LaTeX가 남는 비율은 분야마다 2–16%였다(astro-ph가 가장 높다).
- `$`를 먼저 지우면 `$^\circ$C`가 `\circC` 한 덩어리로 붙어 전체가 버려졌다. 그래서 명령을 먼저 글자로 바꾸고 `$`를 지운다.
- `gold-biorxiv` 브랜치의 새 복사본에 Task 1–3을 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED는 아래 Expected처럼 실패했고 GREEN은 통과했다. 전체 테스트는 Task 1–3 뒤에 511 → 534 → 537 passed, 3 deselected다. Task 1 뒤가 511(리팩터 전과 같은 수)인 것이 "동작이 바뀌지 않았다"는 증거다.

## Global Constraints

**시점**
- **Task 1은 bioRxiv 본 세트 실행이 끝난 뒤에 시작한다.** 측정 중에 공용 코드가 바뀌면 실행 기록의 출처가 흐려진다. 실행 상태는 `.superpowers/sdd/2026-10-02-gold-biorxiv/`의 진행 기록과 `runs/gold-biorxiv-v1/`로 확인한다.

**작업 환경**
- Python 3.11 이상. 엔진의 `dependencies = []`는 그대로 두고, 새 코드는 표준 라이브러리만 쓴다.
- 작업은 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 새 브랜치 `gold-arxiv`(`gold-biorxiv` 위)에서 한다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령은 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`를 붙인다.

**보안과 개인정보**
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다.
- 사용자의 이메일이나 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다. arXiv API 요청에도 넣지 않는다.

**실행과 멈춤**
- 실행(모델 호출)은 미리 승인받았다. 사용자에게 멈춰 묻는 곳은 두 곳뿐이다: 파일럿 5과제 검토(Task 4 끝)와 본 세트 표본 5과제 검토(Task 6 끝).
- 파일럿 규칙에 걸리면 멈추고 사용자와 정한다(`share_correct ≥ 0.8` 천장, `≤ 0.375` 우연 수준).
- 긴 실행은 `setsid nohup`으로 분리해서 돌린다. 백그라운드 작업은 2시간에 끊긴다.
- 멈춘 실행은 5분 뒤 이어 돌리고, 최대 3번까지만 한다.
- **제공자가 거부하면 논문을 빼기 전에 대조 확인부터 한다.** 이미 정상으로 돌아간 과제를 같은 프롬프트로 다시 물어본다. 그것도 거부되면 제공자 상태 문제이니 논문은 그대로 두고 기다린다(bioRxiv 설계 7).

**고정한 값**
- 기간은 2026-07-01 ~ 2026-10-01이다. v1 제출일이 그 안이고 아직 v1인 논문만 쓴다.
- 분야는 `cs.LG`, `cs.CL`, `cond-mat.mtrl-sci`, `astro-ph.GA`, `econ.EM`이고, 주 분류로 가른다.
- 세트는 파일럿 `arxiv-pilot`(분야당 1개)와 본 세트 `arxiv-v1`(분야당 4개, 파일럿 논문 제외)이다.
- 1단계 판정 기준은 바꾸지 않는다: 천장 80%, 쌍 10개, 일치율 0.70, 적합도 동점 0.5.
- **판정은 세트마다 따로 한다.** bioRxiv 세트와 합친 수치는 보고서의 보조 수치로만 적는다.
- 결과를 본 뒤 과제나 판정 기준을 바꾸지 않는다.

**문서**
- Task 3에서 스크립트 이름이 바뀌므로, bioRxiv 설계 3장과 그 구현 계획의 `scripts/build_biorxiv.py`를 `scripts/build_set.py biorxiv`로 고친다(Task 3 Step 5).
- arXiv 논문의 식별자는 그 논문의 arXiv DOI(`10.48550/arXiv.<id>`)다. 공용 모듈의 `doi` 칸을 그대로 쓰고, `arxiv_id`도 목록에 남긴다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 테스트는 그 코드를 맡은 Task에 들어 있다.
- **공용 모듈이 한 자료의 분야 이름에 매이면 안 된다.** 분야 목록을 인자로 받아야 arXiv 분야에서도 섞이지 않는다(Task 1 `tests/test_gold_abstracts.py`의 `FIELDS` 사용, Task 2 `test_the_pool_keeps_one_paper_per_id_with_its_arxiv_doi`의 `counts`).
- **`$`를 지우면 명령이 뒷글자와 붙는다.** `$^\circ$C`가 `\circC`가 되어 초록 전체가 버려지면 안 된다(Task 2 `test_latex_is_written_as_plain_characters`의 `°C` 경우).
- **개정된 논문(v2 이상)은 들어오면 안 된다.** API가 최신 버전을 주기 때문에 초록과 첫 공개일이 어긋난다(Task 2 `test_only_first_versions_of_the_field_submitted_in_the_window_are_kept`).
- **합친 스크립트가 다른 자료의 캐시나 색인을 쓰면 안 된다.** 기본 색인은 `gold/SOURCE/pool.json`이고, 전체 목록은 그 자료의 캐시에 둔다(Task 3 `test_fetch_step_writes_the_full_pool_and_its_index`).
- **초록 길이는 정리한 뒤에 잰다.** LaTeX를 지우면 단어 수가 줄어서, 정리 전 기준으로 재면 짧은 초록이 들어온다(Task 2 `test_an_abstract_shorter_than_the_minimum_is_left_out`).

---

### Task 1: 공용 파이프라인을 `gold/abstracts.py`로 옮기기

**Files:**
- Create: `src/reasonlineage/gold/abstracts.py`
- Modify: `src/reasonlineage/gold/biorxiv.py` (수집만 남긴다)
- Create: `tests/test_gold_abstracts.py`
- Modify: `tests/test_gold_biorxiv.py` (수집 테스트만 남긴다)
- Modify: `scripts/build_biorxiv.py`, `tests/test_build_biorxiv_script.py` (공용 모듈을 부르게)

**Interfaces:**
- Consumes: `reasonlineage.gold.build.shuffled`, `reasonlineage.backends.base`
- Produces (`abstracts`):
  - `SourceError(RuntimeError)`, `ReviewError(ValueError)`
  - `pool_bytes(papers) -> bytes`, `load_pool(path, sha256) -> list[dict]`
  - `sentences(text)`, `split_problems(parts, first_result)`, `alteration_problems(result, reversed_, altered)`
  - `LETTERS`, `QUESTION`, `MAX_RESULT_WORDS`, `ROTATIONS`, `LABEL_SYSTEM`, `ALTER_SYSTEM`, `TELL_SYSTEM`, 각 schema
  - `label_request`, `alter_request`, `tell_request(member, passages, context=None)`
  - `make_candidate(paper, backend, member)`
  - `candidates(set_name, papers, per_category, backend, member, categories, exclude=…, previous=…, dropped=…)`
  - `review_sample(found, categories, dropped=…)`, `review_sheet(found, sample)`, `check_review(review, found, categories)`
  - `build(set_name, found, review, per_category, source, tasks_dir, gold_path, categories, limits=None)`
  - **분야 목록을 인자로 받는 것이 이 Task의 핵심 변화다.** 전에는 모듈의 `CATEGORIES`를 썼다.
- Produces (`biorxiv`): `API`, `START`, `END`, `CATEGORIES`, `MIN_WORDS`, `CACHE`, `WITHDRAWN`, `SYMBOLS`, `RESIDUE`, `clean_abstract`, `keep`, `fetch_category`, `build_pool`. `SourceError`와 `pool_bytes`는 공용 모듈에서 가져온다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_abstracts.py`를 만든다.

```python
"""The shared pipeline of a result-prediction gold set (bioRxiv design 4.3-4.7), with a fake DeepSeek."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from reasonlineage.backends.base import BackendError
from reasonlineage.diagnose.gold import correctness
from reasonlineage.engine.config import load_task
from reasonlineage.gold import abstracts as bx

# A source supplies the fields; these stand in for bioRxiv's five.
FIELDS = ("pharmacology_and_toxicology", "cancer_biology", "immunology", "neuroscience", "cell_biology")
SOURCE = {"source": "test", "pool_sha256": "abc"}


def candidates(*args, **kw):
    return bx.candidates(*args, categories=FIELDS, **kw)


def review_sample(found, dropped=frozenset()):
    return bx.review_sample(found, FIELDS, dropped)


def check_review(review, found):
    return bx.check_review(review, found, FIELDS)


def build(*args, **kw):
    return bx.build(*args, categories=FIELDS, **kw)



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

ABSTRACT = ("Cortex matters for behavior. We gave drug X to mice and recorded neurons. "
            "Drug X increased neuronal firing by 40% in mouse cortex. This suggests X excites cortex.")

PAPER = {"doi": "10.1/p", "category": "neuroscience", "date": "2026-07-02", "title": "X excites cortex", "abstract": ABSTRACT}

MEMBER = SimpleNamespace(model="deepseek", effort="max")

class FakeDeepSeek:
    """Answers each kind of request by its system prompt; `tell` picks a letter for the wording check."""

    def __init__(self, first_result=3, rewrite=None, tell="real", fail_first=0, tell_context=None):
        self.first_result, self.tell, self.fail_first = first_result, tell, fail_first
        self.tell_context = tell if tell_context is None else tell_context  # the answer when the background is shown
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
        tell = self.tell_context if request.prompt.startswith("Background and methods:") else self.tell
        letter = next(line[7] for line in lines if line[10:] == real) if tell == "real" else tell
        return SimpleNamespace(data={"real": letter})

def make(backend, paper=PAPER):
    return asyncio.run(bx.make_candidate(paper, backend, MEMBER))

def test_a_paper_whose_real_result_is_hidden_in_the_wording_is_kept():
    entry = make(FakeDeepSeek(tell="A"))
    assert entry["status"] == "kept" and entry["tell"] == [True, False, False]
    assert entry["tell_context"] == [True, False, False]
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
    return [dict(PAPER, doi=f"10.1/{field}-{i}", category=field) for field in FIELDS for i in range(n_per_field)]

def test_candidates_follow_a_fixed_order_per_field_and_reuse_earlier_results():
    pool = papers(3)
    found = asyncio.run(candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    assert [e["category"] for e in found] == list(FIELDS) and all(e["status"] == "kept" for e in found)
    again = asyncio.run(candidates("set-a", pool, 1, None, MEMBER, previous=found))
    assert again == found
    other = asyncio.run(candidates("set-b", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    assert [e["doi"] for e in other] != [e["doi"] for e in found]

def test_excluded_papers_are_skipped():
    pool = papers(2)
    first = asyncio.run(candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    second = asyncio.run(candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER, exclude={e["doi"] for e in first}))
    assert not {e["doi"] for e in first} & {e["doi"] for e in second}

def test_a_field_that_runs_out_of_usable_papers_stops_with_the_count():
    with pytest.raises(bx.SourceError, match="only 0 of 1 papers usable after trying all 2"):
        asyncio.run(candidates("set-a", papers(2), 1, FakeDeepSeek(tell="real"), MEMBER))

def kept(field, i):
    return {"doi": f"10.1/{field}-{i}", "category": field, "status": "kept", "context": f"Background {field} {i}.",
            "result": "Real result.", "reversed": "Reversed result.", "altered": "Altered result.", "title": "Title tells"}

def found(n_per_field=2):
    return [kept(field, i) for field in FIELDS for i in range(n_per_field)]

def keep_all(entries):
    return {"keep": review_sample(entries), "drop": []}


def test_the_review_sample_is_the_first_kept_paper_of_each_field():
    entries = found()
    assert review_sample(entries) == [f"10.1/{f}-0" for f in FIELDS]
    assert review_sample(entries, {"10.1/immunology-0"})[2] == "10.1/immunology-1"

def test_the_review_sheet_shows_the_real_and_rewritten_results():
    sheet = bx.review_sheet(found(), ["10.1/neuroscience-0"])
    assert "## neuroscience — 10.1/neuroscience-0" in sheet and "**Real result.** Real result." in sheet
    assert "**Reversed.**" in sheet and "**Altered.**" in sheet

@pytest.mark.parametrize("review, problem", [
    ({"keep": [f"10.1/{f}-0" for f in FIELDS[:4]], "drop": []}, "cell_biology-0: not reviewed"),
    ({"keep": [f"10.1/{f}-0" for f in FIELDS] + ["10.1/none"], "drop": []}, "10.1/none: not a kept candidate"),
    ({"keep": [f"10.1/{f}-0" for f in FIELDS] * 2, "drop": []}, "reviewed twice"),
    ({"keep": [f"10.1/{f}-0" for f in FIELDS[1:]], "drop": [{"doi": "10.1/pharmacology_and_toxicology-0", "why": " "}]},
     "dropped without a reason"),
])

def test_review_rules_are_enforced(review, problem):
    assert any(problem in p for p in check_review(review, found()))

def test_build_writes_tasks_that_hide_the_title_and_shuffle_the_letters(tmp_path):
    paths = build("set-a", found(1), keep_all(found(1)), 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    gold = json.loads((tmp_path / "gold.json").read_text())
    assert gold["source"] == SOURCE | {"limits": {}} and [p.name for p in paths] == [f"set-a-0{i}.json" for i in range(1, 6)]
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
    build("set-a", found(1), keep_all(found(1)), 1, SOURCE, again / "tasks", again / "gold.json")
    assert (again / "gold.json").read_text() == (tmp_path / "gold.json").read_text()

def test_a_paper_dropped_in_review_is_replaced_by_the_next_kept_one(tmp_path):
    entries = found(2)
    review = {"keep": [d for d in review_sample(entries) if "immunology" not in d] + ["10.1/immunology-1"],
              "drop": [{"doi": "10.1/immunology-0", "why": "the altered result is not clearly different"}]}
    build("set-a", entries, review, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    assert json.loads((tmp_path / "gold.json").read_text())["tasks"]["set-a-03"]["doi"] == "10.1/immunology-1"

def test_build_stops_when_review_left_too_few_papers_or_breaks_a_rule(tmp_path):
    entries = found(1)
    review = {"keep": review_sample(entries)[1:], "drop": [{"doi": "10.1/pharmacology_and_toxicology-0", "why": "leaks"}]}
    with pytest.raises(bx.ReviewError, match="run `candidates` again"):
        build("set-a", entries, review, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    with pytest.raises(bx.ReviewError, match="not reviewed"):
        build("set-a", entries, {"keep": [], "drop": []}, 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    assert not (tmp_path / "gold.json").exists()

def test_build_refuses_task_files_it_does_not_make(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "set-a-09.json").write_text("{}")
    with pytest.raises(bx.ReviewError, match="set-a-09.json is not built by this review"):
        build("set-a", found(1), keep_all(found(1)), 1, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")

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
    first = asyncio.run(candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER))
    gone = first[0]["doi"]
    again = asyncio.run(candidates("set-a", pool, 1, FakeDeepSeek(tell="A"), MEMBER, previous=first, dropped={gone}))
    field = [e for e in again if e["category"] == first[0]["category"]]
    assert field[0]["doi"] == gone and len(field) == 2 and field[1]["status"] == "kept"

@pytest.mark.parametrize("per_field", [1, 4])

def test_the_real_result_is_spread_evenly_over_the_letters(tmp_path, per_field):
    # A pull toward the first option would inflate the pilot rule if the real result sat mostly at A; the
    # per-task shuffle put it at A in 4 of the 5 pilot tasks (final review).
    entries = found(per_field)
    build("set-a", entries, keep_all(entries), per_field, SOURCE, tmp_path / "tasks", tmp_path / "gold.json")
    tasks = json.loads((tmp_path / "gold.json").read_text())["tasks"].values()
    counts = [sum(t["approved"][0] == f"Result {x}" for t in tasks) for x in bx.LETTERS]
    assert sum(counts) == 5 * per_field and max(counts) - min(counts) <= 1

def test_a_paper_whose_real_result_follows_from_the_background_is_dropped():
    # In the first pilot the panel rejected rewrites that contradicted the background ("GABAergic" against
    # "monoaminergic centers"), so 19 of 20 answers were right (pilot ceiling, 2026-10-02).
    entry = make(FakeDeepSeek(tell="A", tell_context="real"))
    assert entry["status"] == "dropped" and "background" in entry["reason"] and entry["tell_context"] == [True, True, True]

def test_the_rewrites_must_not_contradict_the_background_and_the_check_shows_it():
    assert "never contradict anything the background and methods state" in bx.ALTER_SYSTEM
    request = bx.tell_request(MEMBER, ["a", "b", "c"], context="We used mice.")
    assert request.prompt.startswith("Background and methods:\nWe used mice.\n\nResult A: a")
    assert bx.tell_request(MEMBER, ["a", "b", "c"]).prompt.startswith("Result A: a")

def test_a_field_can_have_fewer_tasks_than_the_others(tmp_path):
    # Immunology ran out of papers the providers would accept, so the main set keeps 2 there and 4 elsewhere.
    entries = found(4)
    paths = build("set-a", entries, keep_all(entries), 4, SOURCE, tmp_path / "tasks", tmp_path / "gold.json",
                     limits={"immunology": 2})
    gold = json.loads((tmp_path / "gold.json").read_text())
    assert len(paths) == 18 and gold["source"]["limits"] == {"immunology": 2}
    immunology = [t for t, g in gold["tasks"].items() if "immunology" in g["doi"]]
    assert immunology == ["set-a-09", "set-a-10"]
    assert [t for t, g in gold["tasks"].items() if "neuroscience" in g["doi"]][0] == "set-a-11"

def test_giving_one_field_fewer_tasks_leaves_the_other_tasks_untouched(tmp_path):
    # The letters are drawn for the set's declared size, so shrinking a field cannot invalidate measured tasks.
    entries = found(4)
    full = tmp_path / "full"
    build("set-a", entries, keep_all(entries), 4, SOURCE, full / "tasks", full / "gold.json")
    short = tmp_path / "short"
    build("set-a", entries, keep_all(entries), 4, SOURCE, short / "tasks", short / "gold.json",
             limits={"immunology": 2})
    before = json.loads((full / "gold.json").read_text())["tasks"]
    after = json.loads((short / "gold.json").read_text())["tasks"]
    kept = [f"set-a-{i:02d}" for i in range(1, 11)]
    assert all(before[k]["approved"] == after[k]["approved"] for k in kept)
    assert [(short / "tasks" / f"{k}.json").read_text() == (full / "tasks" / f"{k}.json").read_text() for k in kept]


def test_a_pool_file_that_is_not_the_recorded_one_is_refused(tmp_path):
    path = tmp_path / "pool.json"
    path.write_bytes(bx.pool_bytes([{"doi": "10.1/a"}]))
    assert bx.load_pool(path, hashlib.sha256(path.read_bytes()).hexdigest()) == [{"doi": "10.1/a"}]
    with pytest.raises(bx.SourceError, match="not the recorded"):
        bx.load_pool(path, "0" * 64)
```

`tests/test_gold_biorxiv.py`를 다음으로 바꾼다(수집 테스트만 남는다).

```python
"""bioRxiv as a source of abstracts (bioRxiv design 4.1-4.2): the pool, its filters and the markup cleanup."""

import pytest

from reasonlineage.gold import biorxiv as bx

WORDS = " ".join(["word"] * 130)


def record(doi="10.1/a", version="1", date="2026-07-01", type_="new results", published="NA", title="A study",
           abstract=WORDS):
    return {"doi": doi, "version": version, "date": date, "type": type_, "published": published, "title": title,
            "abstract": abstract, "category": "neuroscience"}


def page(records, total):
    return {"messages": [{"status": "ok", "total": str(total)}], "collection": records}


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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_abstracts.py tests/test_gold_biorxiv.py`
Expected: FAIL, `ImportError: cannot import name 'abstracts' from 'reasonlineage.gold'` (1 error)

- [ ] **Step 3: 공용 모듈을 만들고 bioRxiv 모듈을 줄이기**

`src/reasonlineage/gold/abstracts.py`를 만든다.

```python
"""The shared half of a result-prediction gold set: sentences, the DeepSeek steps, the review and the files.

A source module (biorxiv.py, arxiv.py) fetches papers and hands them here as {doi, category, date, title, abstract}.
Everything below is the same for every source, so the two sets differ only in where the abstracts come from.
"""

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..backends.base import BackendError, ModelBackend, ModelRequest
from .build import shuffled


class SourceError(RuntimeError):
    """A source could not be read, a saved pool is not the recorded one, or a field ran out of usable papers."""


def pool_bytes(papers: Sequence[Mapping[str, Any]]) -> bytes:
    return (json.dumps(list(papers), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def load_pool(path: str | Path, sha256: str) -> list[dict[str, Any]]:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SourceError(f"{path} has sha256 {digest}, not the recorded {sha256}; run `fetch` again")
    return json.loads(data)


# --- 4.3 sentences and the checks on DeepSeek's work ---

MAX_RESULT_WORDS = 400
ABBREVIATIONS = {"e.g", "i.e", "al", "fig", "figs", "vs", "approx", "ca", "cf", "no", "dr", "ref", "refs", "eq",
                 "resp", "incl", "st", "sp", "spp"}
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[^\W_])")  # any letter or digit may start one
_LAST_WORD = re.compile(r"(?<![\w\-}])([A-Za-z][A-Za-z.]*)\.$")  # a whole word, not the end of "2D" or "κB"


def sentences(text: str) -> list[str]:
    """The abstract split into sentences; abbreviations, initials and decimals do not end one."""
    parts, start = [], 0
    for match in _BOUNDARY.finditer(text):
        word = _LAST_WORD.search(text[start:match.start()])
        if word and (word.group(1).lower() in ABBREVIATIONS or re.fullmatch(r"[A-Z]", word.group(1))):
            continue
        parts.append(text[start:match.start()].strip())
        start = match.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def split_problems(parts: Sequence[str], first_result: Any) -> list[str]:
    """Why the split at `first_result` (1-based) cannot make a task; empty when it can (4.3)."""
    if not isinstance(first_result, int) or not 2 <= first_result <= len(parts):
        return [f"first result sentence {first_result!r} leaves no background or no result"]
    words = len(" ".join(parts[first_result - 1:]).split())
    return [f"the results have {words} words, more than {MAX_RESULT_WORDS}"] if words > MAX_RESULT_WORDS else []


def alteration_problems(result: str, reversed_: Any, altered: Any) -> list[str]:
    """Why the two rewritten results cannot be used; empty when they can (4.4)."""
    if not isinstance(reversed_, str) or not isinstance(altered, str):
        return ["the rewritten results are not text"]
    norm = [" ".join(t.split()).casefold() for t in (result, reversed_, altered)]
    problems = []
    if len(set(norm)) < 3:
        problems.append("a rewritten result repeats the real one or the other")
    for name, text in (("reversed", reversed_), ("altered", altered)):
        ratio = len(text) / max(len(result), 1)
        if not 0.75 <= ratio <= 1.25:
            problems.append(f"the {name} result is {ratio:.2f} times as long as the real one")
    return problems


# --- 4.3-4.5 DeepSeek ---

LETTERS = ("A", "B", "C")
LABEL_SYSTEM = ("You read the abstract of a biology preprint, split into numbered sentences. Find the first sentence "
                "that reports a finding or a conclusion of this study itself (what the authors found or showed, not "
                "what was known before or what they set out to do or how they did it). Every sentence from that one "
                "to the end will be treated as the study's results.")
ALTER_SYSTEM = (
    "You write two false versions of the results passage of a biology abstract, for a test in which experts read "
    "the background and methods and must pick the real results from three versions. Both versions must never "
    "contradict anything the background and methods state (organisms, cells, targets, techniques, definitions, "
    "numbers): change only what the study found, so that the background alone cannot rule a version out.\n"
    '- "reversed": reverse the direction of one central finding (increase and decrease, promotes and inhibits, '
    "required and dispensable, present and absent) and adjust the rest so the passage stays internally consistent. "
    "If the passage reports how well a method performs, do not make the method fail; reverse which comparison, "
    "condition or group shows the effect instead.\n"
    '- "altered": keep the direction but change one central detail so that the conclusion differs: the cell type or '
    "tissue, the target, the condition, the mechanism, or the size of the effect.\n"
    "Both versions must read like results that authors would publish: keep the authors' confident, positive "
    "framing, keep every value physically possible (no negative rates or counts), and keep the number of sentences, "
    "the length (within 20%), the style, the terminology and the number format of the real passage. A reader who "
    "knows only that the passage comes from a published abstract must not be able to reject either version for "
    "sounding like a failed study, for an impossible value or for an internal contradiction. Each version must reach "
    "a conclusion clearly different from the real passage and from the other version. Never say that anything was "
    "changed.")
TELL_SYSTEM = ("Exactly one of three passages is the real results text of a published biology abstract; the other "
               "two were rewritten. Say which one is real.")
LABEL_SCHEMA = {"type": "object", "properties": {"first_result": {"type": "integer"}}, "required": ["first_result"],
                "additionalProperties": False}
ALTER_SCHEMA = {"type": "object", "properties": {"reversed": {"type": "string"}, "altered": {"type": "string"}},
                "required": ["reversed", "altered"], "additionalProperties": False}
TELL_SCHEMA = {"type": "object", "properties": {"real": {"type": "string", "enum": list(LETTERS)}},
               "required": ["real"], "additionalProperties": False}
ROTATIONS = ((0, 1, 2), (1, 2, 0), (2, 0, 1))  # the real passage lands on A, C and B


def _request(member: Any, system: str, prompt: str, schema: Mapping[str, Any]) -> ModelRequest:
    return ModelRequest(system=system, prompt=prompt, model=member.model, effort=member.effort,
                        json_schema=dict(schema), timeout_s=1800, max_tokens=64000)


def label_request(member: Any, parts: Sequence[str]) -> ModelRequest:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(parts, 1))
    return _request(member, LABEL_SYSTEM, f"Abstract:\n{numbered}", LABEL_SCHEMA)


def alter_request(member: Any, context: str, result: str) -> ModelRequest:
    return _request(member, ALTER_SYSTEM, f"Background and methods:\n{context}\n\nReal results:\n{result}", ALTER_SCHEMA)


def tell_request(member: Any, passages: Sequence[str], context: str | None = None) -> ModelRequest:
    """The wording check (no context) or, with `context`, the background check."""
    lines = "\n\n".join(f"Result {letter}: {text}" for letter, text in zip(LETTERS, passages))
    prompt = f"Background and methods:\n{context}\n\n{lines}" if context else lines
    return _request(member, TELL_SYSTEM, prompt, TELL_SCHEMA)


async def _ask(backend: ModelBackend, request: ModelRequest, valid: Callable[[Mapping[str, Any]], bool]):
    """The answer's data, asking once more if the call fails or the answer is not usable; None after two tries."""
    for _ in range(2):
        try:
            data = (await backend.complete(request)).data
        except BackendError:
            continue
        if isinstance(data, Mapping) and valid(data):
            return dict(data)
    return None


async def make_candidate(paper: Mapping[str, Any], backend: ModelBackend, member: Any) -> dict[str, Any]:
    """One paper through splitting, rewriting and the wording check; status "kept" or "dropped" with the reason."""
    entry: dict[str, Any] = {key: paper[key] for key in ("doi", "category", "date", "title", "abstract")}

    def dropped(reason: str) -> dict[str, Any]:
        return entry | {"status": "dropped", "reason": reason}

    parts = sentences(paper["abstract"])
    entry["sentences"] = parts
    label = await _ask(backend, label_request(member, parts), lambda d: "first_result" in d)
    if label is None:
        return dropped("DeepSeek gave no usable split")
    entry["first_result"] = label["first_result"]
    problems = split_problems(parts, label["first_result"])
    if problems:
        return dropped("; ".join(problems))
    k = label["first_result"]
    entry["context"], entry["result"] = " ".join(parts[:k - 1]), " ".join(parts[k - 1:])
    rewrite = await _ask(backend, alter_request(member, entry["context"], entry["result"]),
                         lambda d: not alteration_problems(entry["result"], d.get("reversed"), d.get("altered")))
    if rewrite is None:
        return dropped("DeepSeek gave no usable rewritten results")
    entry["reversed"], entry["altered"] = (" ".join(rewrite[k].split()) for k in ("reversed", "altered"))
    texts = (entry["result"], entry["reversed"], entry["altered"])
    votes = await asyncio.gather(*(_ask(backend, tell_request(member, [texts[i] for i in order]),
                                        lambda d: d.get("real") in LETTERS) for order in ROTATIONS))
    if any(v is None for v in votes):
        return dropped("DeepSeek gave no usable answer in the wording check")
    entry["tell"] = [LETTERS[order.index(0)] == v["real"] for order, v in zip(ROTATIONS, votes)]
    if all(entry["tell"]):
        return dropped("the real result can be told from the wording alone (3 of 3)")
    # The first pilot hit the ceiling because rewrites contradicted the background (pilot, 2026-10-02).
    votes = await asyncio.gather(*(_ask(backend, tell_request(member, [texts[i] for i in order], entry["context"]),
                                        lambda d: d.get("real") in LETTERS) for order in ROTATIONS))
    if any(v is None for v in votes):
        return dropped("DeepSeek gave no usable answer in the background check")
    entry["tell_context"] = [LETTERS[order.index(0)] == v["real"] for order, v in zip(ROTATIONS, votes)]
    if all(entry["tell_context"]):
        return dropped("the real result follows from the background (3 of 3)")
    return entry | {"status": "kept"}


async def candidates(set_name: str, papers: Sequence[Mapping[str, Any]], per_category: int, backend: ModelBackend,
                     member: Any, categories: Sequence[str], exclude: set[str] = frozenset(),
                     previous: Sequence[Mapping[str, Any]] = (), dropped: set[str] = frozenset()
                     ) -> list[dict[str, Any]]:
    """Papers tried for each field in sample order until `per_category` are kept (4.2); earlier results are reused.

    `exclude` skips papers (another set's); `dropped` are papers the review dropped: they stay on record, so the
    review can still name them, but do not count toward `per_category`.
    """
    done = {entry["doi"]: dict(entry) for entry in previous}
    by_doi = {paper["doi"]: paper for paper in papers}

    def usable(tried: list[dict[str, Any]]) -> int:
        return sum(e["status"] == "kept" and e["doi"] not in dropped for e in tried)

    async def field(category: str) -> list[dict[str, Any]]:
        order = shuffled(sorted(d for d, p in by_doi.items() if p["category"] == category), f"{set_name}:{category}")
        tried: list[dict[str, Any]] = []
        for doi in order:
            if usable(tried) >= per_category:
                return tried
            if doi in exclude:
                continue
            tried.append(done.get(doi) or await make_candidate(by_doi[doi], backend, member))
        if usable(tried) < per_category:
            raise SourceError(f"{category}: only {usable(tried)} of {per_category} papers usable after trying all "
                              f"{len(tried)}")
        return tried

    return [entry for batch in await asyncio.gather(*(field(c) for c in categories)) for entry in batch]


# --- 4.6 review and 4.7 files ---

class ReviewError(ValueError):
    """The review record breaks a rule of bioRxiv design 4.6, or the task folder holds files `build` does not make."""


QUESTION = ("Three candidate results follow. Exactly one is what this study reported.\n{lines}\n"
            "Which result did this study report? Rank the candidates, and give the mechanism, the key evidence, and "
            "a validation experiment for the top pick.")


def review_sample(found: Sequence[Mapping[str, Any]], categories: Sequence[str],
                  dropped: set[str] = frozenset()) -> list[str]:
    """The DOIs to review: the first kept paper of each field not dropped in review (4.6)."""
    sample = []
    for category in categories:
        for entry in found:
            if entry["category"] == category and entry["status"] == "kept" and entry["doi"] not in dropped:
                sample.append(entry["doi"])
                break
    return sample


def review_sheet(found: Sequence[Mapping[str, Any]], sample: Sequence[str]) -> str:
    by_doi = {entry["doi"]: entry for entry in found}
    lines = ["# Review sheet", "",
             "For each paper: are both rewritten results plausible yet clearly a different conclusion from the real "
             "one, and does the background leak no result? Write review.json as "
             '{"keep": [doi, ...], "drop": [{"doi": ..., "why": ...}]}.', ""]
    for doi in sample:
        e = by_doi[doi]
        lines += [f"## {e['category']} — {doi}", "", f"**Background and methods.** {e['context']}", "",
                  f"**Real result.** {e['result']}", "", f"**Reversed.** {e['reversed']}", "",
                  f"**Altered.** {e['altered']}", ""]
    return "\n".join(lines)


def check_review(review: Mapping[str, Any], found: Sequence[Mapping[str, Any]], categories: Sequence[str]
                 ) -> list[str]:
    """What breaks the review rules (4.6); empty when the record is usable."""
    kept = {e["doi"] for e in found if e["status"] == "kept"}
    keep_list = list(review.get("keep", []))
    drops = list(review.get("drop", []))
    named = keep_list + [d.get("doi") for d in drops]
    problems = [f"{doi}: reviewed twice" for doi in sorted({d for d in named if named.count(d) > 1})]
    problems += [f"{doi}: not a kept candidate" for doi in named if doi not in kept]
    problems += [f"{d.get('doi')}: dropped without a reason ('why')" for d in drops if not str(d.get("why", "")).strip()]
    dropped = {d.get("doi") for d in drops}
    problems += [f"{doi}: not reviewed" for doi in review_sample(found, categories, dropped) if doi not in named]
    return problems


def build(set_name: str, found: Sequence[Mapping[str, Any]], review: Mapping[str, Any], per_category: int,
          source: Mapping[str, Any], tasks_dir: str | Path, gold_path: str | Path, categories: Sequence[str],
          limits: Mapping[str, int] | None = None) -> list[Path]:
    """Write the task files and the gold file; nothing is written if the review breaks a rule (4.7).

    `limits` gives a field fewer tasks than `per_category`: immunology ran out of papers every provider accepts.
    """
    limits = dict(limits or {})
    problems = check_review(review, found, categories)
    if problems:
        raise ReviewError("; ".join(problems))
    dropped = {d["doi"] for d in review.get("drop", [])}
    chosen = []
    for category in categories:
        usable = [e for e in found if e["category"] == category and e["status"] == "kept" and e["doi"] not in dropped]
        want = limits.get(category, per_category)
        if len(usable) < want:
            raise ReviewError(f"{category}: {len(usable)} usable papers for {want} tasks; run `candidates` "
                              f"again to replace the papers dropped in review")
        chosen += usable[:want]
    ids = [f"{set_name}-{i:02d}" for i in range(1, len(chosen) + 1)]
    tasks_dir, gold_path = Path(tasks_dir), Path(gold_path)
    stale = [f"{path} is not built by this review; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise ReviewError("; ".join(stale))
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold = {"source": dict(source) | {"limits": limits}, "tasks": {}}
    written = []
    # The real result's letter is spread evenly over the set, in an order fixed by the set name (final review).
    declared = per_category * len(categories)  # the set's declared size: a short field must not re-draw the letters
    real_letters = shuffled([LETTERS[i % len(LETTERS)] for i in range(declared)], f"{set_name}:letters")[:len(chosen)]
    for task_id, entry, real in zip(ids, chosen, real_letters):
        others = shuffled([x for x in LETTERS if x != real], task_id)
        letter = {"result": real, "reversed": others[0], "altered": others[1]}
        lines = "\n".join(f"- Result {letter[kind]}: {entry[kind]}" for kind in sorted(letter, key=letter.get))
        body = {"id": task_id, "question": entry["context"] + "\n\n" + QUESTION.format(lines=lines),
                "candidates": [f"Result {x}" for x in LETTERS], "category": "analytical", "data_sensitivity": "public"}
        path = tasks_dir / f"{task_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        gold["tasks"][task_id] = {"approved": [f"Result {letter['result']}"],
                                  "failed": sorted(f"Result {letter[k]}" for k in ("reversed", "altered")),
                                  "doi": entry["doi"]}
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
```

`src/reasonlineage/gold/biorxiv.py`를 다음으로 바꾼다.

```python
"""bioRxiv preprints as the source of gold set A (bioRxiv design).

Each task shows the background and methods sentences of an abstract first posted on or after 2026-07-01 and three
results: the abstract's own results and two versions rewritten by DeepSeek, which is outside the panel. The truth is
what the study reported, so it cannot be worked out from the prompt.
"""

import json
import re
import time
import urllib.request
import unicodedata
import html
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .abstracts import SourceError, pool_bytes

API = "https://api.biorxiv.org/details/biorxiv/{start}/{end}/{cursor}?category={category}"
START, END = "2026-07-01", "2026-10-01"
CATEGORIES = ("pharmacology_and_toxicology", "cancer_biology", "immunology", "neuroscience", "cell_biology")
MIN_WORDS = 120
CACHE = Path.home() / ".cache" / "reasonlineage" / "biorxiv"
WITHDRAWN = re.compile(r"^\s*withdrawn|\b(manuscript|preprint|article) (has been|was|is being) withdrawn", re.I)

def _get(url: str, tries: int = 4, wait_s: float = 5.0) -> dict[str, Any]:
    """One API page; the server sometimes drops a connection, so a failure is tried again after a pause."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                page = json.load(response)
            time.sleep(0.5)  # be gentle with a free API
            return page
        except (OSError, ValueError):
            if attempt == tries:
                raise
            time.sleep(wait_s * attempt)
    raise AssertionError("unreachable")


def fetch_category(category: str, cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """Every record the API lists for `category` in the window, page by page; each page is fetched once."""
    records: list[dict[str, Any]] = []
    cursor = 0
    while True:
        path = Path(cache) / category / f"{cursor}.json"
        if path.exists():
            page = json.loads(path.read_text(encoding="utf-8"))
        else:
            url = API.format(start=START, end=END, cursor=cursor, category=category)
            try:
                page = get(url)
            except (OSError, ValueError) as exc:
                raise SourceError(f"could not fetch {url}: {exc}") from None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(page), encoding="utf-8")
        batch = page.get("collection") or []
        records += batch
        cursor += len(batch)
        if not batch or cursor >= int(page["messages"][0].get("total", 0)):
            return records


def keep(record: Mapping[str, Any]) -> bool:
    """A first version posted in the window, new results, not in a journal, a real abstract, not withdrawn (4.1)."""
    abstract = record.get("abstract") or ""
    return (record.get("version") == "1" and START <= (record.get("date") or "") <= END
            and record.get("type") == "new results" and record.get("published") == "NA"
            and len(abstract.split()) >= MIN_WORDS
            and not WITHDRAWN.search(record.get("title") or "") and not WITHDRAWN.search(abstract))


# The API writes some characters as markup ("{beta}", "[&ge;]"). The real result is the abstract's own text, so
# undecoded markup would set it apart from DeepSeek's rewrites (final review, 2026-10-02).
SYMBOLS = {"micro": "µ", "degrees": "°", "+/-": "±", "-": "−", "approx": "≈", "square": "²", "triangleup": "△",
           "schwa": "ə", "propto": "∝", "uparrow": "↑", "downarrow": "↓", ",": ",", "varepsilon": "ε", "varphi": "φ"}
# List, figure and glued-heading residue of structured abstracts: left out rather than repaired.
RESIDUE = re.compile(r"\b[OC]_(?:LI|FIG|TBL)|O_LINK|\b(?:Summary|Significance Statement|Highlights|Graphical Abstract|"
                     r"Abstract|Background|Introduction|Methods|Results|Conclusions?|Objectives?|Aims?|Purpose)[A-Z][a-z]")


def _symbol(match: re.Match) -> str:
    name = match.group(1)
    if name in SYMBOLS:
        return SYMBOLS[name]
    try:
        return unicodedata.lookup(f"GREEK {'CAPITAL' if name[0].isupper() else 'SMALL'} LETTER {name.upper()}")
    except KeyError:
        return match.group(0)  # unknown markup stays, and the abstract is left out below


def clean_abstract(text: str) -> str | None:
    """The abstract with the API's markup decoded; None when residue or unknown markup is left."""
    if RESIDUE.search(text):
        return None
    text = re.sub(r"\{([^{}\s]{1,20})\}", _symbol, text)
    text = html.unescape(re.sub(r"\[(&[a-zA-Z]+;|~)\]", r"\1", text))
    if re.search(r"\{[^{}]*\}|&[a-zA-Z#0-9]+;", text):
        return None
    return " ".join(text.split())


def build_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """The kept papers of the five fields, one per DOI, in DOI order.

    A paper withdrawn in any version is left out, though its first version looks usable on its own.
    """
    records = [(category, record) for category in CATEGORIES for record in fetch_category(category, cache, get)]
    withdrawn = {r["doi"] for _, r in records if r.get("type") == "withdrawn" or WITHDRAWN.search(r.get("title") or "")}
    papers: dict[str, dict[str, Any]] = {}
    for category, record in records:
        if record["doi"] in withdrawn or record["doi"] in papers or not keep(record):
            continue
        abstract = clean_abstract(record["abstract"])
        if abstract is not None:
            papers[record["doi"]] = {"doi": record["doi"], "category": category, "date": record["date"],
                                     "title": " ".join(record["title"].split()), "abstract": abstract}
    return [papers[doi] for doi in sorted(papers)]
```

- [ ] **Step 4: 스크립트와 그 테스트를 공용 모듈에 맞추기**

`scripts/build_biorxiv.py`를 여섯 군데 고친다.

```python
# 이것을
from reasonlineage.gold import biorxiv as bx  # noqa: E402
```

```python
# 이렇게
from reasonlineage.gold import abstracts, biorxiv as bx  # noqa: E402
```

```python
# 이것을
    data = bx.pool_bytes(pool)
```

```python
# 이렇게
    data = abstracts.pool_bytes(pool)
```

```python
# 이것을
        pool = bx.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, bx.SourceError) as exc:
```

```python
# 이렇게
        pool = abstracts.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, abstracts.SourceError) as exc:
```

```python
# 이것을
        found = asyncio.run(bx.candidates(args.set, pool, args.per_category, build_backend(member, 6), member,
                                          exclude=exclude, previous=previous, dropped=dropped))
    except bx.SourceError as exc:
        print(f"cannot fill {args.set}: {exc}", file=sys.stderr)
```

```python
# 이렇게
        found = asyncio.run(abstracts.candidates(args.set, pool, args.per_category, build_backend(member, 6),
                                                 member, bx.CATEGORIES, exclude=exclude, previous=previous,
                                                 dropped=dropped))
    except abstracts.SourceError as exc:
        print(f"cannot fill {args.set}: {exc}", file=sys.stderr)
```

```python
# 이것을
    sample = bx.review_sample(found, dropped)
    (gold_dir / "review_sheet.md").write_text(bx.review_sheet(found, sample), encoding="utf-8")
```

```python
# 이렇게
    sample = abstracts.review_sample(found, bx.CATEGORIES, dropped)
    (gold_dir / "review_sheet.md").write_text(abstracts.review_sheet(found, sample), encoding="utf-8")
```

```python
# 이것을
        written = bx.build(args.set, saved["papers"], review, saved["source"]["per_category"], saved["source"],
                           args.tasks_root / args.set, gold_dir / "gold.json", limits=dict(args.limit))
    except bx.ReviewError as exc:
```

```python
# 이렇게
        written = abstracts.build(args.set, saved["papers"], review, saved["source"]["per_category"],
                                  saved["source"], args.tasks_root / args.set, gold_dir / "gold.json",
                                  bx.CATEGORIES, limits=dict(args.limit))
    except abstracts.ReviewError as exc:
```


`tests/test_build_biorxiv_script.py`를 세 군데 고친다(두 번째와 세 번째는 나오는 곳 모두).

```python
# 이것을
from reasonlineage.gold import biorxiv as bx  # noqa: E402

FIELDS = bx.CATEGORIES

```

```python
# 이렇게
from reasonlineage.gold import abstracts, biorxiv as bx  # noqa: E402

FIELDS = bx.CATEGORIES


def review_sample(found, dropped=frozenset()):
    return abstracts.review_sample(found, FIELDS, dropped)

```

```python
# 이것을 (나오는 곳 2군데 모두)
monkeypatch.setattr(bx, "make_candidate", fake_candidate)
```

```python
# 이렇게
monkeypatch.setattr(abstracts, "make_candidate", fake_candidate)
```

```python
# 이것을 (나오는 곳 2군데 모두)
bx.review_sample(
```

```python
# 이렇게
review_sample(
```


- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_abstracts.py tests/test_gold_biorxiv.py`
Expected: `65 passed`

Run: `python -m pytest -q`
Expected: `511 passed, 3 deselected` (리팩터 전과 같은 수. 동작이 바뀌지 않았다는 뜻이다)

- [ ] **Step 6: 커밋**

```bash
git add src/reasonlineage/gold/abstracts.py src/reasonlineage/gold/biorxiv.py tests/test_gold_abstracts.py tests/test_gold_biorxiv.py scripts/build_biorxiv.py tests/test_build_biorxiv_script.py
git commit -m "Move the source-independent half of a gold set into gold/abstracts.py

The pipeline now takes the field list, so a second source can reuse it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: arXiv 수집과 LaTeX 정리

**Files:**
- Create: `src/reasonlineage/gold/arxiv.py`
- Create: `tests/test_gold_arxiv.py`

**Interfaces:**
- Consumes: Task 1의 `abstracts.SourceError`
- Produces:
  - `API`, `WINDOW`, `START`, `END`, `CATEGORIES`, `MIN_WORDS`, `PAGE`, `CACHE`, `DOI`, `NS`
  - `SYMBOLS`, `UNWRAP`, `REFUSED`, `SPACING`, `COMMAND`
  - `normalize(text) -> str | None`
  - `entries(page) -> (list[dict], int)`: 레코드는 `{id, version, published, primary, title, abstract}`다.
  - `fetch_category(category, cache=CACHE, get=_get) -> list[dict]`
  - `keep(record, category) -> bool`
  - `build_pool(cache=CACHE, get=_get) -> list[dict]`: 원소는 `{doi, arxiv_id, category, date, title, abstract}`다.
  - `counts(papers) -> dict[str, int]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_arxiv.py`를 만든다.

```python
"""arXiv as a source of abstracts (arXiv design 4.1-4.2): the pool, its filters and the LaTeX cleanup."""

import urllib.parse

import pytest

from reasonlineage.gold import arxiv as ax

WORDS = " ".join(["word"] * 130)
ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>{total}</opensearch:totalResults>
  {entries}
</feed>"""
ENTRY = """  <entry>
    <id>http://arxiv.org/abs/{id}v{version}</id>
    <published>{published}T12:00:00Z</published>
    <title>A
      study</title>
    <summary>{abstract}</summary>
    <arxiv:primary_category term="{primary}"/>
    <category term="stat.ML"/>
  </entry>"""


def entry(ident="2607.00001", version="1", published="2026-07-02", primary="cs.LG", abstract=WORDS):
    return ENTRY.format(id=ident, version=version, published=published, primary=primary, abstract=abstract)


def page(entries, total):
    return ATOM.format(total=total, entries="\n".join(entries))


# --- 4.1 reading the API ---

def test_an_entry_gives_the_id_version_date_field_and_text():
    (record,), total = ax.entries(page([entry()], 7))
    assert total == 7
    assert record["id"] == "2607.00001" and record["version"] == "1" and record["published"] == "2026-07-02"
    assert record["primary"] == "cs.LG" and record["title"] == "A study" and record["abstract"] == WORDS


def test_a_reply_that_is_not_atom_xml_is_refused():
    with pytest.raises(ax.SourceError, match="did not return an Atom feed"):
        ax.entries("<html>503</html>")


@pytest.mark.parametrize("change, kept", [
    ({}, True),
    ({"version": "2"}, False),
    ({"published": "2026-06-30"}, False),
    ({"published": "2026-07-01"}, True),
    ({"published": "2026-10-01"}, True),
    ({"published": "2026-10-02"}, False),
    ({"primary": "stat.ML"}, False),
])
def test_only_first_versions_of_the_field_submitted_in_the_window_are_kept(change, kept):
    (record,), _ = ax.entries(page([entry(**change)], 1))
    assert ax.keep(record, "cs.LG") is kept


def test_a_field_is_read_page_by_page_and_each_page_fetched_once(tmp_path):
    pages = {0: page([entry("2607.00001"), entry("2607.00002")], 3), 2: page([entry("2607.00003")], 3)}
    asked = []

    def get(url):
        start = int(url.split("start=")[1].split("&")[0])
        asked.append(start)
        return pages[start]

    found = ax.fetch_category("cs.LG", tmp_path, get)
    assert [r["id"] for r in found] == ["2607.00001", "2607.00002", "2607.00003"] and asked == [0, 2]
    assert len(ax.fetch_category("cs.LG", tmp_path, lambda url: pytest.fail("fetched again"))) == 3


def test_a_failed_fetch_names_the_page(tmp_path):
    def get(url):
        raise OSError("connection reset")

    with pytest.raises(ax.SourceError, match="could not fetch https://export.arxiv.org"):
        ax.fetch_category("cs.CL", tmp_path, get)


def test_the_pool_keeps_one_paper_per_id_with_its_arxiv_doi(tmp_path):
    by_field = {"cs.LG": [entry("2607.00002"), entry("2607.00001", version="3")],
                "cs.CL": [entry("2607.00003", primary="cs.CL"), entry("2607.00002", primary="cs.CL")]}

    def get(url):
        field = next(c for c in ax.CATEGORIES if c in urllib.parse.unquote(url))
        pages = by_field.get(field, [])
        return page(pages, len(pages))

    pool = ax.build_pool(tmp_path, get)
    assert [(p["doi"], p["category"], p["arxiv_id"]) for p in pool] == [
        ("10.48550/arXiv.2607.00002", "cs.LG", "2607.00002"),
        ("10.48550/arXiv.2607.00003", "cs.CL", "2607.00003")]
    assert ax.counts(pool) == {"cs.LG": 1, "cs.CL": 1, "cond-mat.mtrl-sci": 0, "astro-ph.GA": 0, "econ.EM": 0}


def test_an_abstract_shorter_than_the_minimum_is_left_out(tmp_path):
    def get(url):
        short = " ".join(["word"] * 119)
        return page([entry(abstract=short)] if "cs.LG" in url.replace("%3A", ":") else [], 1)

    assert ax.build_pool(tmp_path, get) == []


# --- 4.2 LaTeX ---

@pytest.mark.parametrize("raw, clean", [
    ("We find $M = 3.5 \\times 10^{10} M_{\\odot}$ in the disk.", "We find M = 3.5 × 10^10 M_☉ in the disk."),
    ("Accuracy rose by $5\\%$ ($p < 0.05$).", "Accuracy rose by 5% (p < 0.05)."),
    ("The \\textit{Gaia} sample has $v \\sim 200$ km s$^{-1}$.", "The Gaia sample has v ~ 200 km s^-1."),
    ("Values of $\\alpha$ and $\\Delta T \\geq 3$ $^\\circ$C held.", "Values of α and Δ T ≥ 3 °C held."),
    ("We use \\mathrm{CO} and\\, \\textbf{bold} text.", "We use CO and bold text."),
    ("Spacing   collapses\nacross lines.", "Spacing collapses across lines."),
])
def test_latex_is_written_as_plain_characters(raw, clean):
    assert ax.normalize(raw) == clean


@pytest.mark.parametrize("raw", [
    "We cite \\cite{smith2026} here.",
    "See \\ref{fig:one} for the fit.",
    "\\begin{equation} E = mc^2 \\end{equation}",
    "An unknown macro \\mycommand{x} appears.",
])
def test_an_abstract_whose_markup_cannot_be_written_as_characters_is_left_out(raw):
    assert ax.normalize(raw) is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_arxiv.py`
Expected: FAIL, `ImportError: cannot import name 'arxiv' from 'reasonlineage.gold'` (1 error)

- [ ] **Step 3: 모듈 쓰기**

`src/reasonlineage/gold/arxiv.py`를 만든다.

```python
"""arXiv preprints as the source of gold set A2 (arXiv design 4.1-4.2).

Only first versions submitted on or after 2026-07-01 are used: the API serves the latest version's abstract, so a
revised paper's text and its first-posting date would not match. The abstracts carry LaTeX, and the real result is
the abstract's own text, so the markup is normalized before anything else sees it; an abstract whose markup cannot
be normalized is left out rather than repaired.
"""

import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .abstracts import SourceError

API = ("https://export.arxiv.org/api/query?search_query={query}&start={start}&max_results={page}"
       "&sortBy=submittedDate&sortOrder=descending")
WINDOW = "submittedDate:[202607010000 TO 202610010000]"
START, END = "2026-07-01", "2026-10-01"
CATEGORIES = ("cs.LG", "cs.CL", "cond-mat.mtrl-sci", "astro-ph.GA", "econ.EM")
MIN_WORDS = 120
PAGE = 100
CACHE = Path.home() / ".cache" / "reasonlineage" / "arxiv"
DOI = "10.48550/arXiv.{id}"  # every arXiv paper has this DOI, so the pipeline's identifier stays a DOI
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "opensearch": "http://a9.com/-/spec/opensearch/1.1/"}

# --- 4.2 LaTeX ---

SYMBOLS = {"sim": "~", "approx": "≈", "simeq": "≃", "times": "×", "pm": "±", "mp": "∓", "percent": "%", "%": "%",
           "mu": "µ", "odot": "☉", "oplus": "⊕", "deg": "°", "circ": "°", "leq": "≤", "geq": "≥", "le": "≤",
           "ge": "≥", "ll": "≪", "gg": "≫", "lesssim": "≲", "gtrsim": "≳", "neq": "≠", "to": "→",
           "rightarrow": "→", "leftarrow": "←", "cdot": "·", "dots": "…", "ldots": "…", "infty": "∞",
           "propto": "∝", "sum": "Σ", "sqrt": "√", "partial": "∂", "nabla": "∇", "angstrom": "Å", "AA": "Å",
           "&": "&", "_": "_", "#": "#", "$": "$"}
UNWRAP = ("text", "textit", "textbf", "textrm", "textsc", "emph", "mathrm", "mathbf", "mathit", "mathcal", "rm",
          "it", "bf", "operatorname")
REFUSED = re.compile(r"\\begin\{|\\end\{|\\cite|\\ref\{|\\label\{|\\url|\\footnote")
SPACING = re.compile(r"\\[,;:!> ]|\\quad|\\qquad|\\\\|\\noindent")
COMMAND = re.compile(r"\\([A-Za-z]+|[^A-Za-z\s])")


def _greek(name: str) -> str | None:
    try:
        case = "CAPITAL" if name[0].isupper() else "SMALL"
        return unicodedata.lookup(f"GREEK {case} LETTER {name.upper()}")
    except KeyError:
        return None


def _command(match: re.Match) -> str:
    name = match.group(1)
    if name in SYMBOLS:
        return SYMBOLS[name]
    greek = _greek(name.removeprefix("var"))
    return greek if greek is not None else match.group(0)


def normalize(text: str) -> str | None:
    """The abstract with its LaTeX written as plain characters, or None when some markup is left.

    The rewrites are written from this text, so the real result and the rewrites share one convention; undecoded
    markup would set the real one apart on sight (the same failure the bioRxiv markup caused).
    """
    if REFUSED.search(text):
        return None
    text = SPACING.sub(" ", text).replace("~", " ")
    for name in UNWRAP:
        text = re.sub(r"\\" + name + r"\s*\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\" + name + r"(?![A-Za-z])\s*", "", text)
    # The commands are read while the $ delimiters still separate them: "$^\\circ$C" is \\circ, not \\circC.
    text = COMMAND.sub(_command, text).replace("$", "").replace("^°", "°")
    text = re.sub(r"([\^_])\{([^{}]*)\}", r"\1\2", text)  # km s^{-1} -> km s^-1
    text = re.sub(r"(?<!\\)\{([^{}]*)\}", r"\1", text)  # plain LaTeX grouping
    if "\\" in text or "{" in text or "}" in text:
        return None
    return " ".join(text.split())


# --- 4.1 the pool ---

def _get(url: str, tries: int = 4, wait_s: float = 5.0) -> str:
    """One API page, tried again after a pause; arXiv asks for three seconds between requests."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                page = response.read().decode("utf-8")
            time.sleep(3)
            return page
        except (OSError, ValueError):
            if attempt == tries:
                raise
            time.sleep(wait_s * attempt)
    raise AssertionError("unreachable")


def entries(page: str) -> tuple[list[dict[str, Any]], int]:
    """The page's records and how many the query has in all."""
    try:
        root = ET.fromstring(page)
    except ET.ParseError as exc:
        raise SourceError(f"the API did not return Atom XML: {exc}") from None
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise SourceError(f"the API did not return an Atom feed but <{root.tag}>")
    total = root.findtext("opensearch:totalResults", default="0", namespaces=NS)
    records = []
    for entry in root.findall("atom:entry", NS):
        url = (entry.findtext("atom:id", default="", namespaces=NS)).rsplit("/", 1)[-1]
        ident, _, version = url.partition("v")
        primary = entry.find("arxiv:primary_category", NS)
        records.append({
            "id": ident, "version": version,
            "published": (entry.findtext("atom:published", default="", namespaces=NS))[:10],
            "primary": primary.get("term") if primary is not None else "",
            "title": " ".join((entry.findtext("atom:title", default="", namespaces=NS)).split()),
            "abstract": entry.findtext("atom:summary", default="", namespaces=NS),
        })
    return records, int(total)


def fetch_category(category: str, cache: Path = CACHE, get: Callable[[str], str] = _get) -> list[dict[str, Any]]:
    """Every record the API lists for `category` in the window, page by page; each page is fetched once."""
    found: list[dict[str, Any]] = []
    start = 0
    while True:
        path = Path(cache) / category / f"{start}.xml"
        if path.exists():
            page = path.read_text(encoding="utf-8")
        else:
            url = API.format(query=urllib.parse.quote(f"cat:{category} AND {WINDOW}"), start=start, page=PAGE)
            try:
                page = get(url)
            except (OSError, ValueError) as exc:
                raise SourceError(f"could not fetch {url}: {exc}") from None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page, encoding="utf-8")
        batch, total = entries(page)
        found += batch
        start += len(batch)
        if not batch or start >= total:
            return found


def keep(record: Mapping[str, Any], category: str) -> bool:
    """A first version submitted in the window whose primary field is `category` (4.1)."""
    return (record.get("version") == "1" and START <= (record.get("published") or "") <= END
            and record.get("primary") == category)


def build_pool(cache: Path = CACHE, get: Callable[[str], str] = _get) -> list[dict[str, Any]]:
    """The kept papers of the five fields, one per paper, in DOI order."""
    papers: dict[str, dict[str, Any]] = {}
    for category in CATEGORIES:
        for record in fetch_category(category, cache, get):
            doi = DOI.format(id=record["id"])
            if doi in papers or not keep(record, category):
                continue
            abstract = normalize(record["abstract"])
            if abstract is not None and len(abstract.split()) >= MIN_WORDS:
                papers[doi] = {"doi": doi, "arxiv_id": record["id"], "category": category,
                               "date": record["published"], "title": record["title"], "abstract": abstract}
    return [papers[doi] for doi in sorted(papers)]


def counts(papers: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {category: sum(1 for p in papers if p["category"] == category) for category in CATEGORIES}
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_arxiv.py`
Expected: `23 passed`

Run: `python -m pytest -q`
Expected: `534 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/arxiv.py tests/test_gold_arxiv.py
git commit -m "Fetch first-version arXiv preprints and write their LaTeX as characters

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 두 자료를 하나의 스크립트로

**Files:**
- Create: `scripts/build_set.py` (실행 권한)
- Delete: `scripts/build_biorxiv.py`
- Create: `tests/test_build_set_script.py`
- Delete: `tests/test_build_biorxiv_script.py`
- Modify: `specs/2026-10-02-gold-biorxiv-design.md`, `plans/2026-10-02-gold-biorxiv.md` (스크립트 이름)

**Interfaces:**
- Consumes: Task 1의 `abstracts`, Task 2의 `arxiv`, 기존 `biorxiv`
- Produces:
  - `SOURCES = {"biorxiv": biorxiv, "arxiv": arxiv}`
  - `python scripts/build_set.py SOURCE fetch [--cache DIR] [--full FILE]`
  - `python scripts/build_set.py SOURCE candidates SET --per-category N [--exclude-set OTHER ...]`
  - `python scripts/build_set.py SOURCE build SET [--limit FIELD=N]`
  - 기본 색인은 `gold/SOURCE/pool.json`, 기본 전체 목록은 그 자료의 캐시다. 종료 코드는 성공 0, 실패 1, 인자 오류 2다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_build_set_script.py`를 만든다.

```python
"""The build script (bioRxiv design 3, 4; arXiv design 3, 4): candidates from a saved pool, then build."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_set.py"
sys.path.insert(0, str(ROOT / "scripts"))

import build_set  # noqa: E402
from reasonlineage.gold import abstracts, biorxiv as bx  # noqa: E402

FIELDS = bx.CATEGORIES


def review_sample(found, dropped=frozenset()):
    return abstracts.review_sample(found, FIELDS, dropped)


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
    monkeypatch.setattr(abstracts, "make_candidate", fake_candidate)
    monkeypatch.setattr(build_set, "load_setup",
                        lambda path: SimpleNamespace(local_checkers={"deepseek": SimpleNamespace(model="deepseek-test")}))
    monkeypatch.setattr(build_set, "build_backend", lambda member, n: None)
    return build_set.main(["biorxiv", "--index", str(pool_files(tmp_path)), "--gold-root", str(tmp_path / "gold"),
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
    code = build_set.main(["biorxiv", "--index", str(tmp_path / "none.json"), "--gold-root", str(tmp_path), "candidates",
                               "set-a", "--per-category", "1"])
    assert code == 1 and "run `fetch` first" in capsys.readouterr().err


def build(tmp_path, review):
    gold = tmp_path / "gold" / "set-a"
    gold.mkdir(parents=True)
    papers = [{"doi": f"10.1/{f}", "category": f, "status": "kept", "context": "Background.", "result": "Real.",
               "reversed": "Reversed.", "altered": "Altered."} for f in FIELDS]
    (gold / "candidates.json").write_text(json.dumps({"source": {"per_category": 1}, "papers": papers}))
    if review is not None:
        (gold / "review.json").write_text(json.dumps(review))
    return subprocess.run([sys.executable, str(SCRIPT), "biorxiv", "--gold-root", str(tmp_path / "gold"), "--tasks-root",
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
    result = subprocess.run([sys.executable, str(SCRIPT), "biorxiv", "build", "Set_A"], capture_output=True, text=True)
    assert result.returncode == 2 and "lowercase letters" in result.stderr


def test_a_paper_dropped_in_review_is_replaced_and_the_set_builds(tmp_path, monkeypatch):
    # Before the final-review fix the dropped paper vanished from candidates.json and build refused the review.
    assert run_candidates(tmp_path, monkeypatch) == 0
    gold = tmp_path / "gold" / "set-a"
    sample = review_sample(json.loads((gold / "candidates.json").read_text())["papers"])
    drop = [{"doi": sample[0], "why": "the background leaks a result"}]
    (gold / "review.json").write_text(json.dumps({"keep": sample[1:], "drop": drop}))
    assert run_candidates(tmp_path, monkeypatch) == 0
    saved = json.loads((gold / "candidates.json").read_text())["papers"]
    (gold / "review.json").write_text(json.dumps({"keep": review_sample(saved, {sample[0]}), "drop": drop}))
    code = build_set.main(["biorxiv", "--gold-root", str(tmp_path / "gold"), "--tasks-root", str(tmp_path / "tasks"),
                            "build", "set-a"])
    assert code == 0
    tasks = json.loads((gold / "gold.json").read_text())["tasks"]
    assert len(tasks) == 5 and sample[0] not in {t["doi"] for t in tasks.values()}


def test_candidates_step_skips_the_papers_of_several_sets(tmp_path, monkeypatch):
    monkeypatch.setattr(abstracts, "make_candidate", fake_candidate)
    monkeypatch.setattr(build_set, "load_setup",
                        lambda path: SimpleNamespace(local_checkers={"deepseek": SimpleNamespace(model="deepseek-test")}))
    monkeypatch.setattr(build_set, "build_backend", lambda member, n: None)
    index, gold = pool_files(tmp_path, 3), tmp_path / "gold"

    def run(name, *extra):
        assert build_set.main(["biorxiv", "--index", str(index), "--gold-root", str(gold), "candidates", name,
                                   "--per-category", "1", *extra]) == 0
        return {e["doi"] for e in json.loads((gold / name / "candidates.json").read_text())["papers"]}

    one = run("one")
    two = run("two", "--exclude-set", "one")
    three = run("three", "--exclude-set", "one", "--exclude-set", "two")
    assert not (one & two) and not (three & (one | two)) and len(three) == 5



@pytest.mark.parametrize("source", ["biorxiv", "arxiv"])
def test_fetch_step_writes_the_full_pool_and_its_index(tmp_path, monkeypatch, capsys, source):
    module = build_set.SOURCES[source]
    first = module.CATEGORIES[0]
    papers = [{"doi": "10.1/a", "category": first, "date": "2026-07-02", "title": "T", "abstract": "A."}]
    monkeypatch.setattr(module, "build_pool", lambda cache: papers)
    index, full = tmp_path / "index.json", tmp_path / "pool-full.json"
    assert build_set.main([source, "--index", str(index), "fetch", "--full", str(full)]) == 0
    saved = json.loads(index.read_text())
    assert saved["source"] == source and saved["categories"] == list(module.CATEGORIES)
    assert saved["counts"][first] == 1 and saved["full_pool"] == str(full)
    assert saved["sha256"] == hashlib.sha256(full.read_bytes()).hexdigest()
    assert abstracts.load_pool(full, saved["sha256"]) == papers
    assert f"1 papers: {first} 1" in capsys.readouterr().out


def test_an_unknown_source_is_refused():
    result = subprocess.run([sys.executable, str(SCRIPT), "medrxiv", "fetch"], capture_output=True, text=True)
    assert result.returncode == 2 and "invalid choice: 'medrxiv'" in result.stderr
```

`tests/test_build_biorxiv_script.py`를 지운다.

```bash
git rm tests/test_build_biorxiv_script.py
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_build_set_script.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'build_set'` (1 error)

- [ ] **Step 3: 스크립트 쓰기**

`scripts/build_set.py`를 만들고 `chmod +x scripts/build_set.py`로 실행 권한을 준다.

```python
#!/usr/bin/env python3
"""Build a result-prediction gold set from a source of abstracts (bioRxiv design 3, 4; arXiv design 3, 4).

    python scripts/build_set.py SOURCE fetch
        # the pool: ~/.cache/reasonlineage/SOURCE/pool.json, and its index gold/SOURCE/pool.json with the sha256
    python scripts/build_set.py SOURCE candidates SET --per-category N [--exclude-set OTHER ...]
        # DeepSeek splits, rewrites and checks papers: gold/SET/candidates.json and gold/SET/review_sheet.md
    (the user reads review_sheet.md and writes gold/SET/review.json)
    python scripts/build_set.py SOURCE build SET [--limit FIELD=N]
        # tasks/SET/*.json and gold/SET/gold.json, from the saved candidates and review (no model calls)

SOURCE is biorxiv or arxiv. Only the fetching differs; everything after it is reasonlineage.gold.abstracts.
"""

import argparse
import asyncio
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.engine.config import build_backend, load_setup  # noqa: E402
from reasonlineage.gold import abstracts, arxiv, biorxiv  # noqa: E402

SOURCES = {"biorxiv": biorxiv, "arxiv": arxiv}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args: argparse.Namespace) -> int:
    source = args.module
    try:
        pool = source.build_pool(args.cache or source.CACHE)
    except abstracts.SourceError as exc:
        print(f"cannot read {args.source}: {exc}", file=sys.stderr)
        return 1
    data = abstracts.pool_bytes(pool)
    full = args.full or source.CACHE / "pool.json"
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    counts = collections.Counter(p["category"] for p in pool)
    write_json(args.index, {"source": args.source, "api": source.API, "window": [source.START, source.END],
                            "categories": list(source.CATEGORIES), "full_pool": str(full),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "counts": {c: counts[c] for c in source.CATEGORIES},
                            "papers": [[p["doi"], p["category"], p["date"]] for p in pool]})
    print(f"{len(pool)} papers: " + ", ".join(f"{c} {counts[c]}" for c in source.CATEGORIES))
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    gold_dir = args.gold_root / args.set
    try:
        index = read_json(args.index)
        pool = abstracts.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, abstracts.SourceError) as exc:
        print(f"cannot read the pool ({exc}); run `fetch` first", file=sys.stderr)
        return 1
    previous = read_json(gold_dir / "candidates.json")["papers"] if (gold_dir / "candidates.json").exists() else []
    exclude = {e["doi"] for other in args.exclude_set for e in read_json(args.gold_root / other / "candidates.json")["papers"]}
    review = gold_dir / "review.json"
    dropped = {d["doi"] for d in read_json(review).get("drop", [])} if review.exists() else set()
    member = load_setup(args.config).local_checkers["deepseek"]
    try:
        found = asyncio.run(abstracts.candidates(args.set, pool, args.per_category, build_backend(member, 6),
                                                 member, args.module.CATEGORIES, exclude=exclude, previous=previous,
                                                 dropped=dropped))
    except abstracts.SourceError as exc:
        print(f"cannot fill {args.set}: {exc}", file=sys.stderr)
        return 1
    source = {"source": args.source, "api": args.module.API, "window": [args.module.START, args.module.END],
              "pool_sha256": index["sha256"], "writer": member.model, "set": args.set,
              "per_category": args.per_category, "exclude_sets": args.exclude_set}
    write_json(gold_dir / "candidates.json", {"source": source, "papers": found})
    sample = abstracts.review_sample(found, args.module.CATEGORIES, dropped)
    (gold_dir / "review_sheet.md").write_text(abstracts.review_sheet(found, sample), encoding="utf-8")
    kept = sum(e["status"] == "kept" for e in found)
    print(f"{kept} kept, {len(found) - kept} dropped; review these: {', '.join(sample)}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    gold_dir = args.gold_root / args.set
    try:
        saved = read_json(gold_dir / "candidates.json")
        review = read_json(gold_dir / "review.json")
    except OSError as exc:
        print(f"cannot read the saved candidates or review ({exc}); run `candidates` and write review.json first",
              file=sys.stderr)
        return 1
    try:
        written = abstracts.build(args.set, saved["papers"], review, saved["source"]["per_category"],
                                  saved["source"], args.tasks_root / args.set, gold_dir / "gold.json",
                                  args.module.CATEGORIES, limits=dict(args.limit))
    except abstracts.ReviewError as exc:
        print(f"review.json breaks the rules: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_root / args.set}")
    return 0


def set_name(text: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", text):
        raise argparse.ArgumentTypeError("the set name takes lowercase letters, digits and single hyphens")
    return text


def limit(text: str) -> tuple[str, int]:
    field, _, count = text.partition("=")
    known = [c for module in SOURCES.values() for c in module.CATEGORIES]
    if field not in known or not count.isdigit():
        raise argparse.ArgumentTypeError(f"--limit takes FIELD=N with a field of {', '.join(known)}")
    return field, int(count)


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("--index", type=Path, help="default: gold/SOURCE/pool.json")
    parser.add_argument("--gold-root", type=Path, default=ROOT / "gold")
    parser.add_argument("--tasks-root", type=Path, default=ROOT / "tasks")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--cache", type=Path)
    fetch.add_argument("--full", type=Path)
    cand = sub.add_parser("candidates")
    cand.add_argument("set", type=set_name)
    cand.add_argument("--per-category", type=positive, required=True)
    cand.add_argument("--exclude-set", type=set_name, action="append", default=[], help="repeat for several sets")
    cand.add_argument("--config", type=Path, default=ROOT / "configs" / "main.json")
    build = sub.add_parser("build")
    build.add_argument("set", type=set_name)
    build.add_argument("--limit", type=limit, action="append", default=[], metavar="FIELD=N",
                       help="give FIELD fewer tasks than --per-category; repeat for several fields")
    args = parser.parse_args(argv)
    args.module = SOURCES[args.source]
    args.index = args.index or ROOT / "gold" / args.source / "pool.json"
    return {"fetch": cmd_fetch, "candidates": cmd_candidates, "build": cmd_build}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
```

`scripts/build_biorxiv.py`를 지운다.

```bash
git rm scripts/build_biorxiv.py
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_build_set_script.py`
Expected: `12 passed`

Run: `python -m pytest -q`
Expected: `537 passed, 3 deselected`

- [ ] **Step 5: 문서의 스크립트 이름 고치기**

`specs/2026-10-02-gold-biorxiv-design.md`와 `plans/2026-10-02-gold-biorxiv.md`에서 `scripts/build_biorxiv.py`를 `scripts/build_set.py biorxiv`로 바꾼다. 명령 예시의 인자 순서도 맞춘다(`build_set.py biorxiv candidates SET …`).

```bash
python - <<'PY'
from pathlib import Path
for name in ("specs/2026-10-02-gold-biorxiv-design.md", "plans/2026-10-02-gold-biorxiv.md"):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    text = text.replace("scripts/build_biorxiv.py fetch", "scripts/build_set.py biorxiv fetch")
    text = text.replace("scripts/build_biorxiv.py candidates", "scripts/build_set.py biorxiv candidates")
    text = text.replace("scripts/build_biorxiv.py build", "scripts/build_set.py biorxiv build")
    text = text.replace("`scripts/build_biorxiv.py`", "`scripts/build_set.py` (자료 이름을 첫 인자로 받음)")
    path.write_text(text, encoding="utf-8")
PY
grep -rn "build_biorxiv" specs plans | head
```

Expected: 마지막 `grep`이 아무것도 출력하지 않는다.

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_set.py tests/test_build_set_script.py specs/2026-10-02-gold-biorxiv-design.md plans/2026-10-02-gold-biorxiv.md
git commit -m "Build either source's gold set with one script

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: arXiv 목록과 파일럿 후보 (DeepSeek, 사람 검토에서 멈춤)

**Files:**
- Create: `gold/arxiv/pool.json`(색인), `gold/arxiv-pilot/candidates.json`, `gold/arxiv-pilot/review_sheet.md`

**Interfaces:**
- Consumes: Task 3의 스크립트, cp088의 DeepSeek
- Produces: 사용자가 쓸 `gold/arxiv-pilot/review.json`

- [ ] **Step 1: 목록 받기**

```bash
python scripts/build_set.py arxiv fetch
```

Expected: `<N> papers: cs.LG …, cs.CL …, cond-mat.mtrl-sci …, astro-ph.GA …, econ.EM …`
- 2026-10-02 한 페이지 기준으로 쓸 수 있는 비율은 45–62%였다. 전체 26,093편의 절반 정도가 남을 것으로 본다.
- arXiv는 요청 사이에 3초를 쉰다. 처음 받을 때는 20–40분 걸린다(페이지 261개). 캐시가 있으면 바로 끝난다.

- [ ] **Step 2: 파일럿 후보 만들기**

```bash
python scripts/build_set.py arxiv candidates arxiv-pilot --per-category 1
```

Expected: `5 kept, N dropped; review these: <DOI 5개>`. 5분 안팎 걸린다.
- `cannot fill`이 나오면 그 분야의 사유들(`candidates.json`의 `reason`)을 보고 사용자와 정한다.

- [ ] **Step 3: 커밋하고 사용자 검토 요청**

```bash
git add gold/arxiv/pool.json gold/arxiv-pilot/candidates.json gold/arxiv-pilot/review_sheet.md
git commit -m "Add the arXiv pool index and the pilot candidates

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

사용자에게 `gold/arxiv-pilot/review_sheet.md`를 검토해 달라고 하고 **멈춘다**.
- 기준(bioRxiv 설계 4.6과 같다): 두 변조문이 그럴듯하면서도 진짜와 확실히 다른 결론인가, 맥락에 결과가 새지 않았는가, 변조문이 배경·방법과 모순되지 않는가.
- 사용자가 답하면 그 판단으로 `gold/arxiv-pilot/review.json`을 쓴다: `{"keep": [doi…], "drop": [{"doi": …, "why": …}]}`.
- 버린 논문이 있으면 Step 2를 다시 돌린다(앞 결과를 다시 쓰고, 버린 논문 대신 다음 논문을 처리한다). 새로 나온 표본만 다시 검토를 요청한다.

---

### Task 5: 파일럿 만들기, 실행, 규칙 적용

**Files:**
- Create: `tasks/arxiv-pilot/*.json`, `gold/arxiv-pilot/gold.json`, `gold/arxiv-pilot/review.json`

**Interfaces:**
- Consumes: Task 4의 검토 기록, `scripts/run_gold.sh`, `.superpowers/sdd/2026-10-02-gold-biorxiv/run_set.sh`(이어 돌리는 실행 스크립트)
- Produces: `runs/gold-arxiv-pilot/report.json`, `analysis.md`, 그리고 다음 단계 결정(본 세트 / 멈춤)

- [ ] **Step 1: 과제 만들기와 커밋**

```bash
python scripts/build_set.py arxiv build arxiv-pilot
git add gold/arxiv-pilot/review.json gold/arxiv-pilot/gold.json tasks/arxiv-pilot
git commit -m "Build the arXiv pilot set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: `5 task files in …/tasks/arxiv-pilot`

- [ ] **Step 2: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-arxiv
mkdir -p $W
cp .superpowers/sdd/2026-10-02-gold-biorxiv/run_set.sh $W/run_set.sh
setsid nohup bash $W/run_set.sh arxiv-pilot > $W/pilot.log 2>&1 < /dev/null &
```

- 대기는 백그라운드 명령으로 한다: `for i in $(seq 1 200); do kill -0 <PID> 2>/dev/null || break; sleep 30; done; tail -12 $W/pilot.log`
- 100분마다 다시 건다. 끝나면 `pilot.log` 마지막 줄이 `done` 또는 `stopped`다.
- `stopped`면 마지막 오류를 systematic-debugging으로 본다. 안전 사유 거부라면 Global Constraints의 대조 확인을 먼저 한다.

- [ ] **Step 3: 파일럿 규칙 적용**

```bash
python -c "import json; l=json.load(open('runs/gold-arxiv-pilot/report.json'))['level1']; s=l['share_correct']; print(round(s,3), l['pairs'], '->', 'ceiling: stop' if s >= 0.8 - 1e-9 else 'chance: stop' if s <= 0.375 + 1e-9 else 'go to the main set')"
```

Expected: 비율, 쌍 수, 다음 단계가 한 줄로 나온다.
- `stop`이면 사용자에게 한 줄 결론과 `runs/gold-arxiv-pilot/analysis.md`의 요점을 알리고 멈춘다.
- `go`면 진행 기록에 적고 Task 6으로 간다.

---

### Task 6: 본 세트 후보 (DeepSeek, 사람 검토에서 멈춤)

**Files:**
- Create: `gold/arxiv-v1/candidates.json`, `gold/arxiv-v1/review_sheet.md`

**Interfaces:**
- Consumes: Task 4의 목록 색인과 파일럿 후보
- Produces: 사용자가 쓸 `gold/arxiv-v1/review.json`

- [ ] **Step 1: 후보 만들기**

```bash
python scripts/build_set.py arxiv candidates arxiv-v1 --per-category 4 --exclude-set arxiv-pilot
```

Expected: `20 kept, N dropped; review these: <DOI 5개>`. 20–40분 걸린다.

- [ ] **Step 2: 커밋하고 사용자 검토 요청**

```bash
git add gold/arxiv-v1/candidates.json gold/arxiv-v1/review_sheet.md
git commit -m "Add the arXiv main-set candidates

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

사용자에게 `gold/arxiv-v1/review_sheet.md`의 표본 5개를 검토해 달라고 하고 **멈춘다**. 답을 받으면 Task 4 Step 3과 같은 방식으로 `review.json`을 쓴다. 버린 논문이 있으면 Step 1을 다시 돌리고, 새 표본만 다시 검토한다.

---

### Task 7: 본 세트 만들기, 실행, 분석 보고

**Files:**
- Create: `tasks/arxiv-v1/*.json`, `gold/arxiv-v1/gold.json`, `gold/arxiv-v1/review.json`

**Interfaces:**
- Consumes: Task 6의 검토 기록, Task 5의 실행 스크립트
- Produces: `runs/gold-arxiv-v1/report.json`과 `analysis.md`, 사용자에게 보내는 결론

- [ ] **Step 1: 과제 만들기와 커밋**

```bash
python scripts/build_set.py arxiv build arxiv-v1
git add gold/arxiv-v1/review.json gold/arxiv-v1/gold.json tasks/arxiv-v1
git commit -m "Build the arXiv main set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: `20 task files in …/tasks/arxiv-v1`

- [ ] **Step 2: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-arxiv
setsid nohup bash $W/run_set.sh arxiv-v1 > $W/main.log 2>&1 < /dev/null &
```

Task 5 Step 2와 같은 방식으로 기다린다. 과제당 8–10분이면 3–4시간 걸린다.

- [ ] **Step 3: 분석 보고**

`runs/gold-arxiv-v1/analysis.md`를 읽고 사용자에게 알린다.
- 한 줄 결론으로 시작한다: 신호 / 신호 없음 / 보류(천장 또는 쌍 부족), 그리고 왜인지.
- 이어서 근거 수치를 두세 줄로 적는다: 정답률, 쌍 수, 일치도, 심사위원·저자별로 눈에 띄는 점.
- **bioRxiv 세트의 판정과 나란히 적는다.** 두 세트를 따로 판정하고, 합친 수치는 보조로만 적는다.
- 보고서 경로를 링크한다. `signal`이면 2단계 기준을 먼저 정하자고 제안한다.
- 메모리에 결과를 남긴다.
