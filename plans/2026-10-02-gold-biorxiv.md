# bioRxiv 결과 예측 정답지 (A 세트) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-07-01 이후 처음 게시된 bioRxiv 초록으로 "진짜 결과 1 + DeepSeek가 바꾼 결과 2" 과제를 만들어, 파일럿(5과제)과 본 세트(20과제)로 1단계("첫 세대 적합도가 정답을 따라가는가")를 판정하고 분석 보고서를 낸다.

**Architecture:**
- 새 모듈 `src/reasonlineage/gold/biorxiv.py`가 아래를 맡는다.
  - 목록 받기와 거르기
  - 문장 나누기와 검사
  - DeepSeek 단계(나누기, 바꾸기, 티 거르기)
  - 검토 기록
  - 과제·정답 파일
- 스크립트 `scripts/build_biorxiv.py`가 `fetch → candidates → (사람 검토) → build`를 잇는다.
- 판정은 기존 `reasonlineage gold`를 쓰고, 여기에 분석 보고서(`--analysis`)를 더한다.
- 엔진의 실행 경로와 프로토콜(1.0.5)은 바꾸지 않는다.

**Tech Stack:** Python 3.11 이상, 표준 라이브러리(urllib, json, re, asyncio, hashlib), pytest, bash, bioRxiv API, 로컬 vLLM의 DeepSeek-V4-Flash.

**Spec:** `specs/2026-10-02-gold-biorxiv-design.md` (판정 규칙은 `specs/2026-09-30-gold-dev-design.md` 6.1–6.2)

**미리 확인한 것 (2026-10-02):**
- 코드를 임시 복사본에서 모두 짜고, 실제 bioRxiv와 DeepSeek로 돌려 봤다.
  - 목록은 4,792편이었다(약리·독성 167, 암 666, 면역 570, 신경 2,593, 세포 796). 초록 중앙값은 211단어, 받는 데 9.5분 걸렸다.
  - 서버가 한 번 연결을 끊어서, 다시 받기를 넣었다.
- 파일럿 후보 과정은 6편을 3.8분에 처리했다(5편 남김, 1편 문체로 티 나서 버림).
- 첫 변조 지시로는 `reversed`가 "억제율 −39%", "이 방법은 쓸모없다" 같은 실패한 연구 문장이 되어 쉽게 지울 수 있었다. 지시를 고친 뒤 같은 5편에서 논조를 지키는 미묘한 변조가 나왔다.
- `gold-biorxiv` 브랜치의 새 복사본에 Task 1–6을 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED는 아래 Expected처럼 실패했고 GREEN은 통과했다. 전체 테스트는 Task 1–6 뒤에 449 → 462 → 470 → 480 → 487 → 490 passed, 3 deselected다.

## Global Constraints

**작업 환경**
- Python 3.11 이상이다. 엔진의 `dependencies = []`는 그대로 두고, 새 코드는 표준 라이브러리만 쓴다.
- 작업은 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 브랜치 `gold-biorxiv`(`gold-synth` 위)에서 한다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령을 직접 부를 때는 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.

**보안과 개인정보**
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다.
- 사용자의 이메일이나 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다. bioRxiv API 요청에도 넣지 않는다.

**실행과 멈춤**
- 실행(모델 호출)은 미리 승인받았다. 사용자에게 멈춰 묻는 곳은 두 곳뿐이다: 파일럿 5과제 검토(Task 7 끝)와 본 세트 표본 5과제 검토(Task 9 끝).
- 파일럿 규칙에 걸리면 멈추고 사용자와 정한다(`share_correct ≥ 0.8` 천장, `≤ 0.375` 우연 수준).
- 긴 실행은 `setsid nohup`으로 분리해서 돌린다. 백그라운드 작업은 2시간에 끊긴다.
- 멈춘 실행은 5분 뒤 이어 돌리고, 최대 3번까지만 한다.

**고정한 값**
- 기간은 2026-07-01 ~ 2026-10-01이다.
- 분야는 `pharmacology_and_toxicology`, `cancer_biology`, `immunology`, `neuroscience`, `cell_biology`다.
- 세트는 파일럿 `biorxiv-pilot`(분야당 1개)와 본 세트 `biorxiv-v1`(분야당 4개, 파일럿 논문 제외)이다.
- 1단계 판정 기준은 바꾸지 않는다: 천장 80%, 쌍 10개, 일치율 0.70, 적합도 동점 0.5.
- 결과를 본 뒤 과제, 구간, 판정 기준을 바꾸지 않는다.

**기타**
- 최종 검토(새 검토자)는 코드가 끝나는 Task 6 뒤, 모델을 부르는 Task 7 전에 한다. 실행 결과를 보기 전에 과제 생성의 결함을 잡기 위해서다.
- 오류 메시지는 무엇이 잘못됐고 무엇을 하면 되는지 말한다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 테스트는 그 코드를 맡은 Task에 들어 있다.
- **같은 논문이 여러 분야나 여러 버전으로 나올 때:** 한 번만 들어가야 한다. 버전 1만 남고, 먼저 받은 분야를 따른다(Task 1 `test_the_pool_keeps_one_entry_per_doi_in_doi_order`).
- **"withdrew" 같은 평범한 단어:** 철회로 오인해 버리면 안 된다(Task 1 `test_only_first_versions_…` 의 마지막 경우).
- **약어·이니셜·소수점·숫자로 시작하는 문장:** 문장 나누기를 깨면 안 된다(Task 2 `test_abbreviations_initials_and_decimals_do_not_end_a_sentence`).
- **제목:** 과제 질문에 새어 나오면 안 되고, 진짜 결과가 늘 같은 글자에 있으면 안 된다(Task 4 `test_build_writes_tasks_that_hide_the_title_and_shuffle_the_letters`).
- **검토에서 버린 논문:** 같은 분야의 다음 논문으로 바뀌어야 한다. 다시 돌린 `candidates`는 앞의 DeepSeek 결과를 다시 써야 한다(Task 3 `test_candidates_follow_a_fixed_order_per_field_and_reuse_earlier_results`, Task 4 `test_a_paper_dropped_in_review_is_replaced_by_the_next_kept_one`).

---

### Task 1: 목록 받기와 거르기

**Files:**
- Create: `src/reasonlineage/gold/biorxiv.py`
- Create: `tests/test_gold_biorxiv.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - 상수: `API`, `START = "2026-07-01"`, `END = "2026-10-01"`, `CATEGORIES`(분야 5개, API 이름), `MIN_WORDS = 120`, `CACHE = ~/.cache/reasonlineage/biorxiv`
  - `SourceError(RuntimeError)`
  - `keep(record) -> bool`
  - `fetch_category(category, cache=CACHE, get=_get) -> list[dict]`
  - `build_pool(cache=CACHE, get=_get) -> list[dict]`: 원소는 `{doi, category, date, title, abstract}`이고 DOI 순서다.
  - `pool_bytes(papers) -> bytes`
  - `load_pool(path, sha256) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_biorxiv.py`를 만든다.

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: FAIL, `ImportError: cannot import name 'biorxiv' from 'reasonlineage.gold'` (1 error)

- [ ] **Step 3: 모듈 쓰기**

`src/reasonlineage/gold/biorxiv.py`를 만든다.

```python
"""bioRxiv preprints as the source of gold set A (bioRxiv design).

Each task shows the background and methods sentences of an abstract first posted on or after 2026-07-01 and three
results: the abstract's own results and two versions rewritten by DeepSeek, which is outside the panel. The truth is
what the study reported, so it cannot be worked out from the prompt.
"""

import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

API = "https://api.biorxiv.org/details/biorxiv/{start}/{end}/{cursor}?category={category}"
START, END = "2026-07-01", "2026-10-01"
CATEGORIES = ("pharmacology_and_toxicology", "cancer_biology", "immunology", "neuroscience", "cell_biology")
MIN_WORDS = 120
CACHE = Path.home() / ".cache" / "reasonlineage" / "biorxiv"
WITHDRAWN = re.compile(r"^\s*withdrawn|\b(manuscript|preprint|article) (has been|was|is being) withdrawn", re.I)


class SourceError(RuntimeError):
    """The bioRxiv API failed, the saved pool is not the recorded one, or a field ran out of usable papers."""


# --- 4.1 the pool ---

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


def build_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get) -> list[dict[str, Any]]:
    """The kept papers of the five fields, one per DOI, in DOI order."""
    papers: dict[str, dict[str, Any]] = {}
    for category in CATEGORIES:
        for record in fetch_category(category, cache, get):
            if keep(record) and record["doi"] not in papers:
                papers[record["doi"]] = {"doi": record["doi"], "category": category, "date": record["date"],
                                         "title": " ".join(record["title"].split()),
                                         "abstract": " ".join(record["abstract"].split())}
    return [papers[doi] for doi in sorted(papers)]


def pool_bytes(papers: Sequence[Mapping[str, Any]]) -> bytes:
    return (json.dumps(list(papers), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def load_pool(path: str | Path, sha256: str) -> list[dict[str, Any]]:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SourceError(f"{path} has sha256 {digest}, not the recorded {sha256}; run `fetch` again")
    return json.loads(data)
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: `15 passed`

Run: `python -m pytest -q`
Expected: `449 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/biorxiv.py tests/test_gold_biorxiv.py
git commit -m "Fetch first-version bioRxiv preprints of five fields posted since July

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 문장 나누기와 DeepSeek 결과 검사

**Files:**
- Modify: `src/reasonlineage/gold/biorxiv.py` (파일 끝)
- Modify: `tests/test_gold_biorxiv.py` (파일 끝)

**Interfaces:**
- Consumes: Task 1의 모듈
- Produces:
  - `MAX_RESULT_WORDS = 400`
  - `sentences(text) -> list[str]`
  - `split_problems(parts, first_result) -> list[str]`: `first_result`는 1부터 센다.
  - `alteration_problems(result, reversed_, altered) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_biorxiv.py` 끝에 더한다.

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: FAIL, `13 failed, 15 passed`, `AttributeError: module 'reasonlineage.gold.biorxiv' has no attribute 'sentences'`(그리고 `split_problems`, `alteration_problems`)

- [ ] **Step 3: 코드 쓰기**

`biorxiv.py` 끝에 더한다.

```python
# --- 4.3 sentences and the checks on DeepSeek's work ---

MAX_RESULT_WORDS = 400
ABBREVIATIONS = {"e.g", "i.e", "al", "fig", "figs", "vs", "approx", "ca", "cf", "no", "dr", "ref", "refs", "eq",
                 "resp", "incl", "st", "sp", "spp"}
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_LAST_WORD = re.compile(r"([A-Za-z][A-Za-z.]*)\.$")


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
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: `28 passed`

Run: `python -m pytest -q`
Expected: `462 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/biorxiv.py tests/test_gold_biorxiv.py
git commit -m "Split abstracts into sentences and check DeepSeek's split and rewrites

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: DeepSeek 단계와 후보 고르기

**Files:**
- Modify: `src/reasonlineage/gold/biorxiv.py` (import 블록, 파일 끝)
- Modify: `tests/test_gold_biorxiv.py` (import 블록, 파일 끝)

**Interfaces:**
- Consumes:
  - Task 1–2의 함수
  - `reasonlineage.backends.base.ModelRequest`, `BackendError`, `ModelBackend`
  - `reasonlineage.gold.build.shuffled(items, key)`
- Produces:
  - 상수: `LETTERS = ("A", "B", "C")`, `LABEL_SYSTEM`, `ALTER_SYSTEM`, `TELL_SYSTEM`, 각 schema, `ROTATIONS`
  - 요청 만들기: `label_request`, `alter_request`, `tell_request` (member는 `.model`, `.effort`를 가진 객체)
  - `make_candidate(paper, backend, member) -> dict`
    - `status`는 `"kept"` 또는 `"dropped"`이고, 버리면 `reason`을 적는다.
    - 남기면 `sentences`, `first_result`, `context`, `result`, `reversed`, `altered`, `tell`을 담는다.
  - `candidates(set_name, papers, per_category, backend, member, exclude=frozenset(), previous=()) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_biorxiv.py`의 import 블록(`import hashlib`부터 `from reasonlineage.gold import biorxiv as bx`까지)을 다음으로 바꾼다.

```python
import asyncio
import hashlib
from types import SimpleNamespace

import pytest

from reasonlineage.backends.base import BackendError
from reasonlineage.gold import biorxiv as bx
```

파일 끝에 더한다.

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: FAIL, `8 failed, 28 passed`, `AttributeError: module 'reasonlineage.gold.biorxiv' has no attribute 'make_candidate'`(그리고 `candidates`)

- [ ] **Step 3: 코드 쓰기**

`biorxiv.py`의 import 블록(`import hashlib`부터 `from typing import Any, Callable, Mapping, Sequence`까지)을 다음으로 바꾼다.

```python
import asyncio
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..backends.base import BackendError, ModelBackend, ModelRequest
from .build import shuffled
```

파일 끝에 더한다.

```python
# --- 4.3-4.5 DeepSeek ---

LETTERS = ("A", "B", "C")
LABEL_SYSTEM = ("You read the abstract of a biology preprint, split into numbered sentences. Find the first sentence "
                "that reports a finding or a conclusion of this study itself (what the authors found or showed, not "
                "what was known before or what they set out to do or how they did it). Every sentence from that one "
                "to the end will be treated as the study's results.")
ALTER_SYSTEM = (
    "You write two false versions of the results passage of a biology abstract, for a test in which experts read "
    "the background and methods and must pick the real results from three versions.\n"
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


def tell_request(member: Any, passages: Sequence[str]) -> ModelRequest:
    lines = "\n\n".join(f"Result {letter}: {text}" for letter, text in zip(LETTERS, passages))
    return _request(member, TELL_SYSTEM, lines, TELL_SCHEMA)


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
    entry["reversed"], entry["altered"] = rewrite["reversed"], rewrite["altered"]
    texts = (entry["result"], entry["reversed"], entry["altered"])
    votes = await asyncio.gather(*(_ask(backend, tell_request(member, [texts[i] for i in order]),
                                        lambda d: d.get("real") in LETTERS) for order in ROTATIONS))
    if any(v is None for v in votes):
        return dropped("DeepSeek gave no usable answer in the wording check")
    entry["tell"] = [LETTERS[order.index(0)] == v["real"] for order, v in zip(ROTATIONS, votes)]
    if all(entry["tell"]):
        return dropped("the real result can be told from the wording alone (3 of 3)")
    return entry | {"status": "kept"}


async def candidates(set_name: str, papers: Sequence[Mapping[str, Any]], per_category: int, backend: ModelBackend,
                     member: Any, exclude: set[str] = frozenset(), previous: Sequence[Mapping[str, Any]] = ()
                     ) -> list[dict[str, Any]]:
    """Papers tried for each field in sample order until `per_category` are kept (4.2); earlier results are reused."""
    done = {entry["doi"]: dict(entry) for entry in previous}
    by_doi = {paper["doi"]: paper for paper in papers}

    async def field(category: str) -> list[dict[str, Any]]:
        order = shuffled(sorted(d for d, p in by_doi.items() if p["category"] == category), f"{set_name}:{category}")
        tried: list[dict[str, Any]] = []
        for doi in order:
            if sum(e["status"] == "kept" for e in tried) >= per_category:
                return tried
            if doi in exclude:
                continue
            tried.append(done.get(doi) or await make_candidate(by_doi[doi], backend, member))
        if sum(e["status"] == "kept" for e in tried) < per_category:
            raise SourceError(f"{category}: only {sum(e['status'] == 'kept' for e in tried)} of {per_category} "
                              f"papers usable after trying all {len(tried)}")
        return tried

    return [entry for batch in await asyncio.gather(*(field(c) for c in CATEGORIES)) for entry in batch]
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: `36 passed`

Run: `python -m pytest -q`
Expected: `470 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/biorxiv.py tests/test_gold_biorxiv.py
git commit -m "Have DeepSeek split, rewrite and check papers, and pick candidates per field

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 사람 검토와 과제·정답 파일

**Files:**
- Modify: `src/reasonlineage/gold/biorxiv.py` (파일 끝)
- Modify: `tests/test_gold_biorxiv.py` (import 블록, 파일 끝)

**Interfaces:**
- Consumes:
  - Task 3의 `LETTERS`, 후보 dict
  - `build.shuffled`
  - `reasonlineage.engine.config.load_task`
  - `reasonlineage.diagnose.gold.correctness`
- Produces:
  - `ReviewError(ValueError)`
  - `QUESTION`
  - `review_sample(found, dropped=frozenset()) -> list[str]`
  - `review_sheet(found, sample) -> str`
  - `check_review(review, found) -> list[str]`
  - `build(set_name, found, review, per_category, source, tasks_dir, gold_path) -> list[Path]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_biorxiv.py`의 import 블록(`import asyncio`부터 `from reasonlineage.gold import biorxiv as bx`까지)을 다음으로 바꾼다.

```python
import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from reasonlineage.backends.base import BackendError
from reasonlineage.diagnose.gold import correctness
from reasonlineage.engine.config import load_task
from reasonlineage.gold import biorxiv as bx
```

파일 끝에 더한다.

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: FAIL, `10 failed, 36 passed`, `AttributeError: module 'reasonlineage.gold.biorxiv' has no attribute 'build'`(그리고 `review_sample`, `check_review`, `ReviewError`)

- [ ] **Step 3: 코드 쓰기**

`biorxiv.py` 끝에 더한다.

```python
# --- 4.6 review and 4.7 files ---

class ReviewError(ValueError):
    """The review record breaks a rule of bioRxiv design 4.6, or the task folder holds files `build` does not make."""


QUESTION = ("Three candidate results follow. Exactly one is what this study reported.\n{lines}\n"
            "Which result did this study report? Rank the candidates, and give the mechanism, the key evidence, and "
            "a validation experiment for the top pick.")


def review_sample(found: Sequence[Mapping[str, Any]], dropped: set[str] = frozenset()) -> list[str]:
    """The DOIs to review: the first kept paper of each field not dropped in review (4.6)."""
    sample = []
    for category in CATEGORIES:
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


def check_review(review: Mapping[str, Any], found: Sequence[Mapping[str, Any]]) -> list[str]:
    """What breaks the review rules (4.6); empty when the record is usable."""
    kept = {e["doi"] for e in found if e["status"] == "kept"}
    keep_list = list(review.get("keep", []))
    drops = list(review.get("drop", []))
    named = keep_list + [d.get("doi") for d in drops]
    problems = [f"{doi}: reviewed twice" for doi in sorted({d for d in named if named.count(d) > 1})]
    problems += [f"{doi}: not a kept candidate" for doi in named if doi not in kept]
    problems += [f"{d.get('doi')}: dropped without a reason ('why')" for d in drops if not str(d.get("why", "")).strip()]
    dropped = {d.get("doi") for d in drops}
    problems += [f"{doi}: not reviewed" for doi in review_sample(found, dropped) if doi not in named]
    return problems


def build(set_name: str, found: Sequence[Mapping[str, Any]], review: Mapping[str, Any], per_category: int,
          source: Mapping[str, Any], tasks_dir: str | Path, gold_path: str | Path) -> list[Path]:
    """Write the task files and the gold file; nothing is written if the review breaks a rule (4.7)."""
    problems = check_review(review, found)
    if problems:
        raise ReviewError("; ".join(problems))
    dropped = {d["doi"] for d in review.get("drop", [])}
    chosen = []
    for category in CATEGORIES:
        usable = [e for e in found if e["category"] == category and e["status"] == "kept" and e["doi"] not in dropped]
        if len(usable) < per_category:
            raise ReviewError(f"{category}: {len(usable)} usable papers for {per_category} tasks; run `candidates` "
                              f"again to replace the papers dropped in review")
        chosen += usable[:per_category]
    ids = [f"{set_name}-{i:02d}" for i in range(1, len(chosen) + 1)]
    tasks_dir, gold_path = Path(tasks_dir), Path(gold_path)
    stale = [f"{path} is not built by this review; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise ReviewError("; ".join(stale))
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold = {"source": dict(source), "tasks": {}}
    written = []
    for task_id, entry in zip(ids, chosen):
        kinds = shuffled(["result", "reversed", "altered"], task_id)
        letter = dict(zip(kinds, LETTERS))
        lines = "\n".join(f"- Result {LETTERS[i]}: {entry[kind]}" for i, kind in enumerate(kinds))
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

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_biorxiv.py`
Expected: `46 passed`

Run: `python -m pytest -q`
Expected: `480 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/biorxiv.py tests/test_gold_biorxiv.py
git commit -m "Check the review record and write the bioRxiv task and gold files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 만들기 스크립트

**Files:**
- Create: `scripts/build_biorxiv.py` (실행 권한)
- Create: `tests/test_build_biorxiv_script.py`

**Interfaces:**
- Consumes: Task 1–4의 `biorxiv` 함수, `engine.config.load_setup`과 `build_backend`
- Produces:
  - `python scripts/build_biorxiv.py fetch`: 캐시의 `pool.json`과 색인 `gold/biorxiv/pool.json`을 쓴다.
  - `python scripts/build_biorxiv.py candidates SET --per-category N [--exclude-set OTHER]`: `gold/SET/candidates.json`과 `review_sheet.md`를 쓴다.
  - `python scripts/build_biorxiv.py build SET`: `tasks/SET/*.json`과 `gold/SET/gold.json`을 쓴다.
  - 종료 코드: 성공 0, 실패 1, 인자 오류 2.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_build_biorxiv_script.py`를 만든다.

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_build_biorxiv_script.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'build_biorxiv'` (1 error)

- [ ] **Step 3: 스크립트 쓰기**

`scripts/build_biorxiv.py`를 만들고 `chmod +x scripts/build_biorxiv.py`로 실행 권한을 준다.

```python
#!/usr/bin/env python3
"""Build a bioRxiv result-prediction gold set (bioRxiv design 3, 4).

    python scripts/build_biorxiv.py fetch
        # the pool: ~/.cache/reasonlineage/biorxiv/pool.json, and its index gold/biorxiv/pool.json with the sha256
    python scripts/build_biorxiv.py candidates SET --per-category N [--exclude-set OTHER]
        # DeepSeek splits, rewrites and checks papers: gold/SET/candidates.json and gold/SET/review_sheet.md
    (the user reads review_sheet.md and writes gold/SET/review.json)
    python scripts/build_biorxiv.py build SET
        # tasks/SET/*.json and gold/SET/gold.json, from the saved candidates and review (no model calls)
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
from reasonlineage.gold import biorxiv as bx  # noqa: E402

INDEX = ROOT / "gold" / "biorxiv" / "pool.json"
FULL = bx.CACHE / "pool.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        pool = bx.build_pool(args.cache)
    except bx.SourceError as exc:
        print(f"cannot read bioRxiv: {exc}", file=sys.stderr)
        return 1
    data = bx.pool_bytes(pool)
    args.full.parent.mkdir(parents=True, exist_ok=True)
    args.full.write_bytes(data)
    counts = collections.Counter(p["category"] for p in pool)
    write_json(args.index, {"api": bx.API, "window": [bx.START, bx.END], "categories": list(bx.CATEGORIES),
                            "full_pool": str(args.full), "sha256": hashlib.sha256(data).hexdigest(),
                            "counts": {c: counts[c] for c in bx.CATEGORIES},
                            "papers": [[p["doi"], p["category"], p["date"]] for p in pool]})
    print(f"{len(pool)} papers: " + ", ".join(f"{c} {counts[c]}" for c in bx.CATEGORIES))
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    gold_dir = args.gold_root / args.set
    try:
        index = read_json(args.index)
        pool = bx.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, bx.SourceError) as exc:
        print(f"cannot read the pool ({exc}); run `fetch` first", file=sys.stderr)
        return 1
    previous = read_json(gold_dir / "candidates.json")["papers"] if (gold_dir / "candidates.json").exists() else []
    exclude: set[str] = set()
    if args.exclude_set:
        exclude |= {e["doi"] for e in read_json(args.gold_root / args.exclude_set / "candidates.json")["papers"]}
    if (gold_dir / "review.json").exists():
        exclude |= {d["doi"] for d in read_json(gold_dir / "review.json").get("drop", [])}
    member = load_setup(args.config).local_checkers["deepseek"]
    try:
        found = asyncio.run(bx.candidates(args.set, pool, args.per_category, build_backend(member, 6), member,
                                          exclude=exclude, previous=previous))
    except bx.SourceError as exc:
        print(f"cannot fill {args.set}: {exc}", file=sys.stderr)
        return 1
    source = {"api": bx.API, "window": [bx.START, bx.END], "pool_sha256": index["sha256"], "writer": member.model,
              "set": args.set, "per_category": args.per_category, "exclude_set": args.exclude_set}
    write_json(gold_dir / "candidates.json", {"source": source, "papers": found})
    dropped = {d["doi"] for d in read_json(gold_dir / "review.json").get("drop", [])} if (gold_dir / "review.json").exists() else set()
    sample = bx.review_sample(found, dropped)
    (gold_dir / "review_sheet.md").write_text(bx.review_sheet(found, sample), encoding="utf-8")
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
        written = bx.build(args.set, saved["papers"], review, saved["source"]["per_category"], saved["source"],
                           args.tasks_root / args.set, gold_dir / "gold.json")
    except bx.ReviewError as exc:
        print(f"review.json breaks the rules: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_root / args.set}")
    return 0


def set_name(text: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", text):
        raise argparse.ArgumentTypeError("the set name takes lowercase letters, digits and single hyphens")
    return text


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--gold-root", type=Path, default=ROOT / "gold")
    parser.add_argument("--tasks-root", type=Path, default=ROOT / "tasks")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--cache", type=Path, default=bx.CACHE)
    fetch.add_argument("--full", type=Path, default=FULL)
    cand = sub.add_parser("candidates")
    cand.add_argument("set", type=set_name)
    cand.add_argument("--per-category", type=positive, required=True)
    cand.add_argument("--exclude-set", type=set_name)
    cand.add_argument("--config", type=Path, default=ROOT / "configs" / "main.json")
    build = sub.add_parser("build")
    build.add_argument("set", type=set_name)
    args = parser.parse_args(argv)
    return {"fetch": cmd_fetch, "candidates": cmd_candidates, "build": cmd_build}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_build_biorxiv_script.py`
Expected: `7 passed`

Run: `python -m pytest -q`
Expected: `487 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add scripts/build_biorxiv.py tests/test_build_biorxiv_script.py
git commit -m "Add the script that builds a bioRxiv gold set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 1단계 분석 보고서

**Files:**
- Modify: `src/reasonlineage/diagnose/gold.py` (`level1` 앞, `level1` 안, 파일 끝)
- Modify: `src/reasonlineage/cli.py` (import, `gold` 인자, `cmd_gold`)
- Modify: `scripts/run_gold.sh` (머리 주석, 마지막 명령)
- Modify: `tests/test_gold_diagnose.py`, `tests/test_cli.py`, `tests/test_gold_scripts.py`

**Interfaces:**
- Consumes: `diagnose.gold`의 `level1`, `score_run` 결과(`status == "scored"`인 실행)
- Produces:
  - `author_judge(runs) -> dict[author, dict[judge, mean score]]`
  - `format_analysis(runs) -> str` (Markdown)
  - `reasonlineage gold … --analysis PATH`
  - `run_gold.sh`가 `OUT/analysis.md`를 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_diagnose.py`의 import 줄을 바꾼다.

```python
# 이 줄을
from reasonlineage.diagnose.gold import borda, correctness, level1, level2, score_run, summarize
# 이렇게
from reasonlineage.diagnose.gold import (author_judge, borda, correctness, format_analysis, level1, level2,
                                         score_run, summarize)
```

`tests/test_gold_diagnose.py` 끝에 더한다.

```python
def test_author_judge_averages_each_judges_scores_of_each_author(tmp_path):
    runs = scored(tmp_path, [aligned(), aligned((0.6, 0.6, 0.4, 0.3))])
    table = author_judge(runs)
    assert table["opus"] == {"glm": 0.7, "gpt": 0.7, "grok": 0.7}  # judged 0.8 and 0.6; never by itself
    assert set(table) == set(PANEL)


def test_the_analysis_gives_the_verdict_the_tables_and_every_task(tmp_path):
    runs = scored(tmp_path, [aligned()] * 5)
    text = format_analysis(runs)
    assert "**Verdict: signal.**" in text and "20 answers in 5 tasks" in text
    assert "| opus | 1.00 |" in text and "| Author \\ Judge | glm | gpt | grok | opus |" in text
    assert "| opus | 0.800 | 0.800 | 0.800 | — |" in text
    assert "- **t1** (truth A): glm: C ✗ 0.300; gpt: B ½ 0.600; grok: B ✗ 0.400; opus: A ✓ 0.800" in text
```

`tests/test_cli.py`의 `def test_gold_needs_a_readable_gold_file(tmp_path, capsys):` 바로 앞에 넣는다.

```python
def test_gold_writes_the_level1_analysis(tmp_path):
    task, setup = write_files(tmp_path)
    main(["run", task, "--config", setup, "--seed", "1", "--generations", "0", "--out", str(tmp_path / "runs")], World().services)
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"tasks": {"ipf": {"approved": ["metformin"], "failed": ["imatinib", "sildenafil"]}}}))
    analysis = tmp_path / "analysis.md"
    paths = [str(p) for p in sorted((tmp_path / "runs").iterdir())]
    assert main(["gold", "--gold", str(gold), *paths, "--analysis", str(analysis)], World().services) == 0
    text = analysis.read_text()
    assert text.startswith("# Level 1 analysis") and "**Verdict:" in text and "## Mean judge score by author" in text
```

`tests/test_gold_scripts.py`의 `test_run_script_skips_finished_tasks_and_runs_this_checkouts_code`에서 `assert f"--gold {root}/gold/repodb-dev/gold.json" in calls[1][1]` 줄 바로 뒤에 넣는다.

```python
    assert f"--analysis {tmp_path}/out/analysis.md" in calls[1][1]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_diagnose.py tests/test_cli.py tests/test_gold_scripts.py`
Expected: FAIL, `ImportError: cannot import name 'author_judge' from 'reasonlineage.diagnose.gold'` (1 error)

- [ ] **Step 3: 코드 쓰기**

`src/reasonlineage/diagnose/gold.py`의 `def level1(` 바로 앞에 넣는다.

```python
def _counted(runs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The run each task counts with: its earliest run folder by name (gold design 6.2)."""
    kept: dict[str, Mapping[str, Any]] = {}
    for run in sorted(runs, key=lambda r: r["run"]):
        kept.setdefault(run["task"], run)
    return list(kept.values())
```

`level1` 안의 다섯 줄을 바꾼다.

```python
# 이 줄들을
    kept: dict[str, Mapping[str, Any]] = {}
    for run in sorted(runs, key=lambda r: r["run"]):
        kept.setdefault(run["task"], run)
    set_aside = sorted(run["run"] for run in runs if kept[run["task"]] is not run)
    runs = list(kept.values())
# 이렇게
    counted = _counted(runs)
    set_aside = sorted(run["run"] for run in runs if run not in counted)
    runs = counted
```

파일 끝(`format_report`의 `return "\n".join(lines)` 뒤)에 더한다.

```python
def author_judge(runs: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """The mean weighted score each judge gave each author's generation-0 answers, over the runs level 1 counts."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for run in _counted(runs):
        for answer in run["answers"]:
            if answer["generation"] == 0:
                for judge, score in answer["judges"].items():
                    cells[(answer["author"], judge)].append(score)
    table: dict[str, dict[str, float]] = defaultdict(dict)
    for (author, judge), values in sorted(cells.items()):
        table[author][judge] = sum(values) / len(values)
    return dict(table)


_MARK = {1.0: "✓", 0.5: "½", 0.0: "✗"}


def format_analysis(runs: Sequence[Mapping[str, Any]]) -> str:
    """Level 1 as a Markdown report: the verdict, correctness by author, concordance by judge, the judge-by-author
    score table and every task's generation-0 answers. `runs` are scored runs (`score_run`)."""
    one = level1(runs)
    rate = "n/a" if one["concordance"] is None else f"{one['concordance']:.2f}"
    p = "" if one["sign_test_p"] is None else f", sign test p = {one['sign_test_p']:.3g}"
    rules = one["rules"]
    lines = ["# Level 1 analysis", "",
             f"**Verdict: {one['verdict']}.** {one['answers']} answers in {one['tasks']} tasks: "
             f"{one['share_correct']:.0%} fully correct, {one['pairs']} pairs with different correctness, "
             f"concordance {rate}{p}.",
             f"Rules fixed before the run: ceiling {rules['ceiling']:.0%}, at least {rules['min_pairs']} pairs, "
             f"signal at concordance {rules['signal']:.2f}.", "",
             "## Correctness by author", "", "| Author | Mean correctness |", "|---|---|"]
    lines += [f"| {m} | {v:.2f} |" for m, v in one["by_model"].items()]
    lines += ["", "## Concordance by judge", "", "| Judge | Pairs | Concordance |", "|---|---|---|"]
    lines += [f"| {j} | {v['pairs']} | {'n/a' if v['concordance'] is None else format(v['concordance'], '.2f')} |"
              for j, v in one["by_judge"].items()]
    table = author_judge(runs)
    judges = sorted({j for row in table.values() for j in row})
    lines += ["", "## Mean judge score by author", "",
              "Rows: the answer's author. Columns: the judge. Generation 0, weighted rubric score; "
              "\"—\" where the judge did not score that author (recusal).", "",
              "| Author \\ Judge | " + " | ".join(judges) + " |", "|---|" + "---|" * len(judges)]
    lines += [f"| {a} | " + " | ".join(f"{row[j]:.3f}" if j in row else "—" for j in judges) + " |"
              for a, row in table.items()]
    lines += ["", "## Tasks", "", "Each cell: the author's top pick, its correctness (✓ 1, ½ 0.5, ✗ 0) and the "
              "answer's fitness.", ""]
    for run in sorted(_counted(runs), key=lambda r: r["task"]):
        cells = [f"{a['author']}: {a['ranking'][0] if a['ranking'] else '-'} "
                 f"{_MARK.get(a['correctness'], '?')} {a['fitness'] if a['fitness'] is None else format(a['fitness'], '.3f')}"
                 for a in sorted(run["answers"], key=lambda a: a["author"]) if a["generation"] == 0]
        lines.append(f"- **{run['task']}** (truth {', '.join(run['truth']['approved'])}): " + "; ".join(cells))
    return "\n".join(lines) + "\n"
```

`src/reasonlineage/cli.py`를 세 군데 고친다.

```python
# import 줄을
from .diagnose.gold import format_report, score_run, summarize
# 이렇게
from .diagnose.gold import format_analysis, format_report, score_run, summarize

# gold.add_argument("--out", …) 줄 바로 뒤에
    gold.add_argument("--analysis", help="also write the level-1 analysis to this Markdown file")

# cmd_gold에서 `if args.out:` 블록 바로 뒤, `return 0` 앞에
    if args.analysis:
        scored = [run for run in runs if run["status"] == "scored"]
        Path(args.analysis).write_text(format_analysis(scored) if scored else "# Level 1 analysis\n\nNo scored runs.\n",
                                       encoding="utf-8")
```

`scripts/run_gold.sh`를 두 군데 고친다.

```bash
# 머리 주석의 이 두 줄을
# a time, then the gold summary. A task that already has a finished run in OUT is skipped. A task
# whose run stopped halfway stops the script: resume that run first, then run the script again.
# 이렇게
# a time, then the gold summary (report.json) and the level-1 analysis (analysis.md). A task that already
# has a finished run in OUT is skipped. A task whose run stopped halfway stops the script: resume that run
# first, then run the script again.

# 마지막 명령을
python -m reasonlineage gold --gold "$ROOT/gold/$SET/gold.json" "$OUT"/*/ --out "$OUT/report.json"
# 이렇게
python -m reasonlineage gold --gold "$ROOT/gold/$SET/gold.json" "$OUT"/*/ --out "$OUT/report.json" \
  --analysis "$OUT/analysis.md"
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_diagnose.py tests/test_cli.py tests/test_gold_scripts.py`
Expected: `51 passed`

Run: `python -m pytest -q`
Expected: `490 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/diagnose/gold.py src/reasonlineage/cli.py scripts/run_gold.sh tests/test_gold_diagnose.py tests/test_cli.py tests/test_gold_scripts.py
git commit -m "Write a level-1 analysis report next to the gold summary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 최종 검토 (모델 호출 전에)**

executing-plans의 최종 검토를 지금 한다.
- 대상은 `git merge-base main HEAD`부터 HEAD까지가 아니라, 이 계획의 커밋(설계 문서 커밋 302652e 이후)이다.
- 검토자는 가장 강한 모델의 새 검토자다. 그 판정에 따라 Critical·Important는 실패하는 테스트부터 써서 고친 뒤 Task 7로 간다.

---

### Task 7: 목록 받기와 파일럿 후보 (DeepSeek, 사람 검토에서 멈춤)

**Files:**
- Create: `gold/biorxiv/pool.json`(색인), `gold/biorxiv-pilot/candidates.json`, `gold/biorxiv-pilot/review_sheet.md`

**Interfaces:**
- Consumes: Task 5의 스크립트, cp088의 DeepSeek
- Produces: 사용자가 쓸 `gold/biorxiv-pilot/review.json`

- [ ] **Step 1: 목록 받기**

```bash
python scripts/build_biorxiv.py fetch
```

Expected: `4… papers: pharmacology_and_toxicology …, cancer_biology …, immunology …, neuroscience …, cell_biology …`
- 2026-10-02 시제품에서는 4,792편이었다. 같은 기간이라 거의 같아야 한다.
- 캐시가 있으면 바로 끝나고, 없으면 10분쯤 걸린다.

- [ ] **Step 2: 파일럿 후보 만들기**

```bash
python scripts/build_biorxiv.py candidates biorxiv-pilot --per-category 1
```

Expected: `5 kept, N dropped; review these: <DOI 5개>`. 5분 안팎 걸린다.
- `cannot fill`이 나오면 그 분야의 사유들(`candidates.json`의 `reason`)을 보고 사용자와 정한다.

- [ ] **Step 3: 커밋하고 사용자 검토 요청**

```bash
git add gold/biorxiv/pool.json gold/biorxiv-pilot/candidates.json gold/biorxiv-pilot/review_sheet.md
git commit -m "Add the bioRxiv pool index and the pilot candidates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

사용자에게 `gold/biorxiv-pilot/review_sheet.md`를 검토해 달라고 하고 **멈춘다**.
- 기준(설계 4.6): 두 변조문이 그럴듯하면서도 진짜와 확실히 다른 결론인가, 맥락에 결과가 새지 않았는가.
- 사용자가 답하면 그 판단으로 `gold/biorxiv-pilot/review.json`을 쓴다: `{"keep": [doi…], "drop": [{"doi": …, "why": …}]}`.
- 버린 논문이 있으면 Step 2를 다시 돌린다(앞 결과를 다시 쓰고, 버린 논문 대신 다음 논문을 처리한다). 새로 나온 표본만 다시 검토를 요청한다.

---

### Task 8: 파일럿 과제 만들기, 실행, 규칙 적용

**Files:**
- Create: `tasks/biorxiv-pilot/*.json`, `gold/biorxiv-pilot/gold.json`, `gold/biorxiv-pilot/review.json`
- Create (커밋하지 않음): `.superpowers/sdd/2026-10-02-gold-biorxiv/run_set.sh`

**Interfaces:**
- Consumes: Task 7의 검토 기록, `scripts/run_gold.sh`
- Produces: `runs/gold-biorxiv-pilot/report.json`, `analysis.md`, 그리고 다음 단계 결정(본 세트 / 멈춤)

- [ ] **Step 1: 과제 만들기와 커밋**

```bash
python scripts/build_biorxiv.py build biorxiv-pilot
git add gold/biorxiv-pilot/review.json gold/biorxiv-pilot/gold.json tasks/biorxiv-pilot
git commit -m "Build the bioRxiv pilot set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `5 task files in …/tasks/biorxiv-pilot`

- [ ] **Step 2: 실행 스크립트 만들기**

`.superpowers/sdd/2026-10-02-gold-biorxiv/run_set.sh`:

```bash
#!/usr/bin/env bash
# Run one gold set to the end with scripts/run_gold.sh. A stopped or interrupted run (header but no result) is
# resumed after 5 minutes, at most 3 times; a fourth stop ends the script.
set -u
SET="$1"
cd /common/jungj2/project/ReasonLineage
export PYTHONPATH=src
resumes=0
while true; do
  for d in runs/gold-$SET/*/; do
    if [ -f "$d/header.json" ] && [ ! -f "$d/result.json" ]; then
      resumes=$((resumes + 1))
      if [ "$resumes" -gt 3 ]; then echo "== $(date '+%F %T') stopped: more than 3 resumes"; exit 1; fi
      echo "== $(date '+%F %T') resume $d ($resumes of 3, after 5 minutes)"
      sleep 300
      python -m reasonlineage resume "$d" || echo "== $(date '+%F %T') resume of $d stopped again"
    fi
  done
  if scripts/run_gold.sh "$SET"; then break; fi
  echo "== $(date '+%F %T') a run stopped"
done
echo "== $(date '+%F %T') done"
```

- [ ] **Step 3: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-biorxiv
setsid nohup bash $W/run_set.sh biorxiv-pilot > $W/pilot.log 2>&1 < /dev/null &
```

- 대기는 백그라운드 명령으로 한다: `for i in $(seq 1 200); do kill -0 <PID> 2>/dev/null || break; sleep 30; done; tail -12 $W/pilot.log`
- 100분마다 다시 건다. 끝나면 `pilot.log` 마지막 줄이 `done` 또는 `stopped`다.
- `stopped`면 마지막 오류를 systematic-debugging으로 본다.

- [ ] **Step 4: 파일럿 규칙 적용**

```bash
python -c "import json; l=json.load(open('runs/gold-biorxiv-pilot/report.json'))['level1']; s=l['share_correct']; print(round(s,3), l['pairs'], '->', 'ceiling: stop' if s >= 0.8 - 1e-9 else 'chance: stop' if s <= 0.375 + 1e-9 else 'go to the main set')"
```

Expected: 비율, 쌍 수, 다음 단계가 한 줄로 나온다.
- `stop`이면 사용자에게 한 줄 결론과 `runs/gold-biorxiv-pilot/analysis.md`의 요점을 알리고 멈춘다.
- `go`면 진행 기록에 적고 Task 9로 간다.

---

### Task 9: 본 세트 후보 (DeepSeek, 사람 검토에서 멈춤)

**Files:**
- Create: `gold/biorxiv-v1/candidates.json`, `gold/biorxiv-v1/review_sheet.md`

**Interfaces:**
- Consumes: Task 7의 목록 색인과 파일럿 후보
- Produces: 사용자가 쓸 `gold/biorxiv-v1/review.json`

- [ ] **Step 1: 후보 만들기**

```bash
python scripts/build_biorxiv.py candidates biorxiv-v1 --per-category 4 --exclude-set biorxiv-pilot
```

Expected: `20 kept, N dropped; review these: <DOI 5개>`. 20–40분 걸린다.

- [ ] **Step 2: 커밋하고 사용자 검토 요청**

```bash
git add gold/biorxiv-v1/candidates.json gold/biorxiv-v1/review_sheet.md
git commit -m "Add the bioRxiv main-set candidates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

사용자에게 `gold/biorxiv-v1/review_sheet.md`의 표본 5개를 검토해 달라고 하고 **멈춘다**. 답을 받으면 Task 7 Step 3과 같은 방식으로 `review.json`을 쓴다. 버린 논문이 있으면 Step 1을 다시 돌리고, 새 표본만 다시 검토한다.

---

### Task 10: 본 세트 만들기, 실행, 분석 보고

**Files:**
- Create: `tasks/biorxiv-v1/*.json`, `gold/biorxiv-v1/gold.json`, `gold/biorxiv-v1/review.json`

**Interfaces:**
- Consumes: Task 9의 검토 기록, Task 8의 `run_set.sh`
- Produces: `runs/gold-biorxiv-v1/report.json`과 `analysis.md`, 사용자에게 보내는 결론

- [ ] **Step 1: 과제 만들기와 커밋**

```bash
python scripts/build_biorxiv.py build biorxiv-v1
git add gold/biorxiv-v1/review.json gold/biorxiv-v1/gold.json tasks/biorxiv-v1
git commit -m "Build the bioRxiv main set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `20 task files in …/tasks/biorxiv-v1`

- [ ] **Step 2: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-biorxiv
setsid nohup bash $W/run_set.sh biorxiv-v1 > $W/main.log 2>&1 < /dev/null &
```

Task 8 Step 3과 같은 방식으로 기다린다. 5–10시간 걸린다.

- [ ] **Step 3: 분석 보고**

`runs/gold-biorxiv-v1/analysis.md`를 읽고 사용자에게 알린다.
- 한 줄 결론으로 시작한다: 신호 / 신호 없음 / 보류(천장 또는 쌍 부족), 그리고 왜인지.
- 이어서 근거 수치를 두세 줄로 적는다: 정답률, 쌍 수, 일치도, 심사위원·저자별로 눈에 띄는 점.
- 보고서 경로를 링크한다.
- `signal`이면 2단계 기준을 먼저 정하자고 제안한다(설계 10).
- 메모리에 결과를 남긴다.

---

## 추가: 첫 파일럿이 천장일 때 (2026-10-02, 사용자 결정)

첫 파일럿은 0.95(19/20)로 천장이었다. 모델들은 바꾼 결과가 배경과 모순되는 점을 근거로 지웠다. 사용자가 설계 ①을 골랐다. 바꾸기 지시에 모순 금지를 넣고, 맥락을 보여 주는 두 번째 거르기를 더하고, 새 파일럿을 돌린다.

- **코드 (커밋 후 테스트 509개 통과):**
  - `ALTER_SYSTEM`에 모순 금지 문장을 넣었다.
  - `tell_request(member, passages, context=None)`이 맥락을 받는다.
  - `make_candidate`가 맥락 거르기에서 3번 모두 진짜를 고르면 버린다(`tell_context`).
  - `build_biorxiv.py candidates`의 `--exclude-set`은 여러 번 쓸 수 있다.
  - 테스트: `test_a_paper_whose_real_result_follows_from_the_background_is_dropped`, `test_the_rewrites_must_not_contradict_the_background_and_the_check_shows_it`, `test_candidates_step_skips_the_papers_of_several_sets`.
- **Task 7·8을 다시 한다.** 세트 이름은 `biorxiv-pilot2`이고, 첫 파일럿 논문을 뺀다.
  - `python scripts/build_biorxiv.py candidates biorxiv-pilot2 --per-category 1 --exclude-set biorxiv-pilot`
  - 사용자 검토에서 멈춘다.
  - `build biorxiv-pilot2`를 하고, `run_set.sh biorxiv-pilot2`로 돌리고, 같은 파일럿 규칙을 적용한다.
- **Task 9의 후보 명령**은 `--exclude-set biorxiv-pilot --exclude-set biorxiv-pilot2`를 쓴다.

