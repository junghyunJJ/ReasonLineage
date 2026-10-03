# 기후 편차 정답지 (C 세트) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026년 7·8월에 미국 각 주의 날씨가 평년보다 얼마나 벗어났는지를 묻는 과제 20개로 1단계를 재고 분석 보고서를 낸다. 정답은 모든 모델의 학습 컷오프 뒤에 공개된 실제 관측값이라서, 프롬프트에도 기억에도 없다.

**Architecture:**
- 새 모듈 `src/reasonlineage/gold/weather.py` 하나가 NCEI에서 편차를 받고, 본토 48개 주만 남기고, 9개 기후 지역 규칙과 구간으로 삼중항을 고르고, 과제·정답·수치 파일을 쓴다.
- 난이도는 계산량이 아니라 **1~2위 편차 차이**로 만든다. 세 주는 서로 다른 기후 지역에서 뽑아, 인접한 주끼리 비슷한 편차로 운에 맡겨지는 일을 막는다.
- 스크립트 `scripts/build_weather.py`가 목록을 받고 세트를 만든다. 실행과 판정은 기존 `scripts/run_gold.sh`와 `reasonlineage gold --analysis`를 그대로 쓴다.
- **새 파일만 추가한다.** 기존 코드를 건드리지 않으므로 다른 세트의 실행 중에도 안전하다.

**Tech Stack:** Python 3.11 이상, 표준 라이브러리만(hashlib, itertools, json, time, urllib), pytest.

**Spec:** `specs/2026-10-03-gold-weather-design.md` (판정 규칙은 `specs/2026-09-30-gold-dev-design.md` 6.1–6.2)

**미리 확인한 것 (2026-10-03):**
- 코드를 임시 복사본에서 모두 짜고, 실제로 받아 둔 NCEI 목록(네 묶음, 주 49곳)으로 돌려 봤다. 지역 규칙을 적용한 뒤에도 공급이 넉넉하다: 7월 기온 easy 3,699 / medium 3,234 / hard 2,784, 8월 강수 easy 3,884 / medium 2,699 / hard 2,331 삼중항이다.
- 보정 세트 3개와 20과제 세트를 실제 목록으로 만들어 보니, 지표가 10:10, 월이 10:10으로 나뉘고 한 주가 최대 3번까지만 나온다. 과제 문구에 편차 수치가 들어가지 않는다.
- 0.1 정밀도의 뺄셈에서 부동소수 오차가 나와 구간 경계가 흔들렸다(5.3 - 3.3 = 2.0000000000000004). 그래서 1~2위 차이는 `margin()`에서 반올림한 값만 쓴다.
- `gold-weather` 브랜치의 새 복사본에 Task 1–4를 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED는 아래 Expected처럼 실패했고 GREEN은 통과했다. 전체 테스트는 560 → 568 → 587 → 596 → 605 passed, 3 deselected다.

## Global Constraints

**작업 환경**
- Python 3.11 이상. 엔진의 `dependencies = []`는 그대로 두고, 새 코드는 표준 라이브러리만 쓴다.
- 작업은 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 브랜치 `gold-weather`(`gold-basket` 위)에서 한다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령은 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`를 붙인다.

**보안과 개인정보**
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다.
- 사용자의 이메일이나 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다. NCEI 요청에는 연락처를 넣지 않는다(넣지 않아도 응답한다).

**실행과 멈춤**
- 실행(모델 호출)은 미리 승인받았다. 멈춰 묻는 곳은 두 곳이다: 보정 규칙에 걸릴 때(Task 5 Step 5)와 본 세트를 돌리기 전 과제 하나를 보여 줄 때(Task 6 Step 2, 확인만 받는다).
- **다른 세트의 실행이 돌고 있으면 기다린다.** 같은 CLI를 동시에 쓰면 서로 느려지고, 측정 중인 실행이 더 중요하다. `pgrep -f "reasonlineage (run|resume)"`로 확인한다.
- 긴 실행은 `setsid nohup`으로 분리해서 돌린다. 백그라운드 작업은 2시간에 끊긴다.
- 멈춘 실행은 5분 뒤 이어 돌리고, 최대 3번까지만 한다.
- 제공자가 거부하면 과제를 버리기 전에 이미 정상으로 돌아간 과제로 대조 확인부터 한다. 주 이름과 날씨만 나오는 과제라서 생의학 거부와 같은 일이 생길 이유는 없지만, 규칙은 그대로 둔다.
- 생물학적 위험이나 안전 관련 거부 신호가 나오면 그 항목을 교체하고 다시 묻지 않는다.

**고정한 값**
- 구간은 1~2위 편차 차이로 정한다: 기온 easy 2.0°F 이상 / medium 1.0 이상 2.0 미만 / hard 0.4 이상 1.0 미만, 강수 easy 1.5인치 이상 / medium 0.7 이상 1.5 미만 / hard 0.3 이상 0.7 미만.
- 세 주는 서로 다른 기후 지역이고, 세 편차가 서로 다르다. 한 주는 한 세트에서 최대 3번 나온다.
- 보정 구간 고르기(실행 전에 고정): 정답 비율이 0.375–0.75인 구간 중 0.6에 가장 가까운 구간. 같으면 더 어려운 구간. 세 구간이 모두 0.75를 넘거나 모두 0.375 미만이면 멈추고 사용자와 정한다.
- **3지선다라 우연이 0.333이다. 이 세트는 천장보다 바닥이 더 큰 위험이다.** 모든 구간이 0.375 미만이면 모델이 추정할 수 없는 문제라는 뜻이고, 과제를 어렵게 만드는 쪽으로 더 가지 않는다.
- 1단계 판정 기준은 바꾸지 않는다: 천장 80%, 쌍 10개, 일치율 0.70, 적합도 동점 0.5.
- **판정은 세트마다 따로 한다.** 다른 세트와 합친 수치는 보고서의 보조 수치로만 적는다. 지표별·월별 수치도 보조다(10과제 부분집합은 쌍이 모자라기 쉽다).
- 쌍이 10개에 못 미치면 같은 구간에서 과제 10개를 더 만들어 이어 붙인다(설계 5.2에서 미리 정해 둔 것이다).
- 결과를 본 뒤 구간, 과제, 판정 기준을 바꾸지 않는다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 테스트는 그 코드를 맡은 Task에 들어 있다.
- **과제 문구에 편차 수치가 새면 안 된다.** 수치가 보이면 추정이 아니라 읽기가 된다(Task 3 `test_the_question_leaks_no_departure_figure`).
- **구간 경계가 부동소수 오차로 흔들리면 안 된다.** 0.1 정밀도의 뺄셈은 2.0을 2.0000000000000004로 만들고, 그러면 easy 과제가 medium에 들어간다(Task 2 `test_a_gap_falls_in_one_band_only`).
- **주 이름을 추측하면 정답이 조용히 틀린다.** 이름은 응답의 `description.title`에서만 읽는다(Task 1 `test_reading_takes_the_state_name_from_the_reply`, `test_fetch_pool_keeps_the_contiguous_states_with_a_departure`).
- **편차가 같은 두 주가 한 과제에 들어가면 정답이 임의가 된다.** 0.1 정밀도라서 동점이 실제로 생긴다(Task 2 `test_usable_refuses_a_tie`).
- **이전 생성이 남긴 과제 파일이 섞이면 안 된다.** `run_gold.sh`는 폴더의 모든 파일을 돌리므로, 정답 없는 과제가 조용히 실행된다(Task 3 `test_build_stops_when_the_task_folder_holds_a_file_it_does_not_build`).

## File Structure

| 파일 | 하는 일 | Task |
|---|---|---|
| `src/reasonlineage/gold/weather.py` (새) | NCEI 받기, 주 거르기, 기후 지역, 삼중항 고르기, 과제·정답·수치 파일 | 1–3 |
| `tests/test_gold_weather.py` (새) | 모듈 테스트(NCEI·모델 호출 없음) | 1–3 |
| `scripts/build_weather.py` (새) | `fetch` → `build SET --band … --tasks N` | 4 |
| `tests/test_build_weather_script.py` (새) | 스크립트 테스트 | 4 |
| `gold/weather/pool.json` | 목록 색인(주·월·지표·편차)과 전체 목록의 sha256 | 5 |
| `tasks/weather-calib-*/`, `gold/weather-calib-*/` | 보정 세트 | 5 |
| `tasks/weather-v1/`, `gold/weather-v1/` | 본 세트 | 6 |
| `runs/gold-weather-v1/report.json`, `analysis.md` | 판정과 분석 | 6–7 |

바꾸지 않는 것: 엔진, 프로토콜, `scripts/run_gold.sh`, `reasonlineage gold`, 다른 세트의 파일.

---

### Task 1: 목록 받기와 기후 지역

**Files:**
- Create: `src/reasonlineage/gold/weather.py`
- Create: `tests/test_gold_weather.py`

**Interfaces:**
- Consumes: `reasonlineage.gold.build.shuffled`(Task 3에서 쓴다), 표준 라이브러리만.
- Produces: `SourceError`, `API`, `STATE_IDS`, `MONTHS`, `MONTH_NAMES`, `MEASURES`, `CACHE`, `REGIONS`, `REGION_OF`,
  `_get(url, tries=4, wait_s=5.0) -> dict`, `reading(reply, month) -> tuple[str, float] | None`,
  `fetch_pool(cache=CACHE, get=_get, state_ids=tuple(STATE_IDS)) -> dict[str, dict[str, float]]`,
  `pool_bytes(pool) -> bytes`, `load_pool(path, sha256) -> dict[str, dict[str, float]]`.
  목록의 열쇠는 `"<월>:<지표>"`(예: `"7:tavg"`)이고 값은 `{주 이름: 편차}`다. Task 2, 3, 4가 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_weather.py`를 만든다.

```python
"""The climate-departure gold set: the pool, the regions, the bands, and the files (weather design 8).

No test calls NCEI or a model. The replies are the shape of a real one, saved from Alabama's August 2026 reading.
"""

import pytest

from reasonlineage.gold import weather as w

# ids 1-4 of NCEI's alphabetical statewide numbering, plus Alaska, which no climate region holds.
NAMES = {1: "Alabama", 2: "Arizona", 3: "Arkansas", 4: "California", 50: "Alaska"}
TAVG = {1: 2.4, 2: 6.1, 3: 4.1, 4: 5.3, 50: 1.2}
PCP = {1: 1.1, 2: -0.4, 3: 0.2, 4: 0.8, 50: 0.3}


def reply(state: str, month: int, measure: str, departure: float | None) -> dict:
    kind = "Average Temperature" if measure == "tavg" else "Precipitation"
    body = {"description": {"title": f"{state} {w.MONTH_NAMES[month]} {kind}",
                            "units": "Degrees Fahrenheit" if measure == "tavg" else "Inches",
                            "base_period": "1901-2000", "base_period_average": 79.3},
            "data": {f"2026{month:02d}": {"value": 81.7}}}
    if departure is not None:
        body["data"][f"2026{month:02d}"]["departure"] = departure
    return body


def fake_get(missing: tuple[int, ...] = ()) -> tuple:
    """A `get` over the four buckets, and the list of urls it was asked for."""
    asked: list[str] = []

    def get(url: str) -> dict:
        asked.append(url)
        state, measure, _, month_text = url.split("time-series/")[1].split("/")[:4]
        state_id, month = int(state), int(month_text)
        table = TAVG if measure == "tavg" else PCP
        value = None if state_id in missing else table[state_id] + (0.5 if month == 7 else 0.0)
        return reply(NAMES[state_id], month, measure, value)

    return get, asked


def pool(**buckets: dict[str, float]) -> dict[str, dict[str, float]]:
    """A pool with the same values in every bucket unless a bucket is given by name, e.g. pool(**{"7:tavg": {...}})."""
    base = {"Alabama": 2.4, "Arizona": 6.1, "Arkansas": 4.1, "California": 5.3}
    return {key: dict(buckets.get(key, base)) for key in ("7:tavg", "7:pcp", "8:tavg", "8:pcp")}


# --- 4.1 the pool ---

def test_reading_takes_the_state_name_from_the_reply():
    assert w.reading(reply("North Dakota", 8, "tavg", 1.7), 8) == ("North Dakota", 1.7)


def test_reading_skips_a_month_with_no_departure():
    assert w.reading(reply("Ohio", 7, "pcp", None), 7) is None


def test_fetch_pool_keeps_the_contiguous_states_with_a_departure(tmp_path):
    get, asked = fake_get(missing=(3,))
    found = w.fetch_pool(tmp_path, get, state_ids=(1, 2, 3, 4, 50))
    assert sorted(found) == ["7:pcp", "7:tavg", "8:pcp", "8:tavg"]
    assert found["8:tavg"] == {"Alabama": 2.4, "Arizona": 6.1, "California": 5.3}  # no Arkansas, no Alaska
    assert found["7:tavg"]["Alabama"] == pytest.approx(2.9)  # July's own reading, not August's
    assert len(asked) == 20


def test_fetch_pool_reads_the_cache_instead_of_asking_again(tmp_path):
    get, asked = fake_get()
    w.fetch_pool(tmp_path, get, state_ids=(1, 2))
    again, asked_again = fake_get()
    found = w.fetch_pool(tmp_path, again, state_ids=(1, 2))
    assert asked_again == []
    assert found["8:tavg"] == {"Alabama": 2.4, "Arizona": 6.1}
    assert len(asked) == 8


def test_get_tries_again_after_a_failure(monkeypatch):
    calls = []

    def flaky(url, timeout=None):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("connection reset")
        raise _Done()

    class _Done(Exception):
        pass

    monkeypatch.setattr(w.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(w.time, "sleep", lambda seconds: None)
    with pytest.raises(_Done):
        w._get("https://example.invalid/x")
    assert len(calls) == 3


def test_fetch_pool_says_which_reading_it_could_not_get(tmp_path):
    def get(url):
        raise OSError("503")

    with pytest.raises(w.SourceError) as exc:
        w.fetch_pool(tmp_path, get, state_ids=(1,))
    assert "/1/tavg/1/7/" in str(exc.value)


def test_load_pool_refuses_a_file_that_changed(tmp_path):
    path = tmp_path / "pool.json"
    path.write_bytes(w.pool_bytes(pool()))
    with pytest.raises(w.SourceError) as exc:
        w.load_pool(path, "0" * 64)
    assert "fetch" in str(exc.value)


# --- 4.2 the regions ---

def test_the_regions_hold_the_48_contiguous_states_once_each():
    named = [state for states in w.REGIONS.values() for state in states]
    assert len(named) == 48
    assert len(set(named)) == 48
    assert "Alaska" not in named and "Hawaii" not in named
    assert w.REGION_OF["Wyoming"] == "Northern Rockies and Plains"
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `1 error`, `ImportError: cannot import name 'weather' from 'reasonlineage.gold'`

- [ ] **Step 3: 모듈 쓰기**

`src/reasonlineage/gold/weather.py`를 만든다.

```python
"""Climate-departure gold set (weather design 4).

Each task names three states and asks whose month departed furthest above its own 1901-2000 normal. The answer is
what the weather actually did in July or August 2026, first published after every panel model's training cutoff, so
it cannot be computed from the prompt or recalled — the failure that put three earlier sets at the ceiling.
"""

import hashlib
import itertools
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .build import shuffled


class SourceError(RuntimeError):
    """NCEI could not be read, the saved pool is not the recorded one, or a band ran out of triples."""


API = ("https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/statewide/time-series/"
       "{state}/{measure}/1/{month}/2026-2026.json?base_prd=true&begbaseyear=1901&endbaseyear=2000")
STATE_IDS = range(1, 51)  # NCEI's statewide numbers, alphabetical
MONTHS = (7, 8)
MONTH_NAMES = {7: "July", 8: "August"}
MEASURES = ("tavg", "pcp")
CACHE = Path.home() / ".cache" / "reasonlineage" / "weather"
# Alaska is left out: it belongs to none of the nine contiguous climate regions (design 4.1).
REGIONS: dict[str, tuple[str, ...]] = {
    "Northeast": ("Connecticut", "Delaware", "Maine", "Maryland", "Massachusetts", "New Hampshire", "New Jersey",
                  "New York", "Pennsylvania", "Rhode Island", "Vermont"),
    "Upper Midwest": ("Iowa", "Michigan", "Minnesota", "Wisconsin"),
    "Ohio Valley": ("Illinois", "Indiana", "Kentucky", "Missouri", "Ohio", "Tennessee", "West Virginia"),
    "Southeast": ("Alabama", "Florida", "Georgia", "North Carolina", "South Carolina", "Virginia"),
    "Northern Rockies and Plains": ("Montana", "Nebraska", "North Dakota", "South Dakota", "Wyoming"),
    "South": ("Arkansas", "Kansas", "Louisiana", "Mississippi", "Oklahoma", "Texas"),
    "Southwest": ("Arizona", "Colorado", "New Mexico", "Utah"),
    "Northwest": ("Idaho", "Oregon", "Washington"),
    "West": ("California", "Nevada"),
}
REGION_OF = {state: region for region, states in REGIONS.items() for state in states}
# --- 4.1 the pool ---

def _get(url: str, tries: int = 4, wait_s: float = 5.0) -> dict[str, Any]:
    """One API reply, tried again after a pause; nothing in the request identifies anyone."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                reply = json.load(response)
            time.sleep(0.2)
            return reply
        except (OSError, ValueError):
            if attempt == tries:
                raise
            time.sleep(wait_s * attempt)
    raise AssertionError("unreachable")


def reading(reply: Mapping[str, Any], month: int) -> tuple[str, float] | None:
    """The state's name and its departure from normal, or None when the month has no departure.

    The name comes from the reply, so no state is ever named by guesswork (design 4.1).
    """
    title = (reply.get("description") or {}).get("title") or ""
    state = title.split(f" {MONTH_NAMES[month]} ")[0].strip()
    record = (reply.get("data") or {}).get(f"2026{month:02d}") or {}
    departure = record.get("departure")
    if not state or departure is None:
        return None
    return state, float(departure)


def fetch_pool(cache: Path = CACHE, get: Callable[[str], dict] = _get,
               state_ids: Sequence[int] = tuple(STATE_IDS)) -> dict[str, dict[str, float]]:
    """Every contiguous state's departure for each month and measure, as {"<month>:<measure>": {state: value}}."""
    pool: dict[str, dict[str, float]] = {}
    for month in MONTHS:
        for measure in MEASURES:
            found: dict[str, float] = {}
            for state_id in state_ids:
                path = Path(cache) / f"{month}-{measure}-{state_id}.json"
                if path.exists():
                    reply = json.loads(path.read_text(encoding="utf-8"))
                else:
                    url = API.format(state=state_id, measure=measure, month=month)
                    try:
                        reply = get(url)
                    except (OSError, ValueError) as exc:
                        raise SourceError(f"could not fetch {url}: {exc}") from None
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(reply), encoding="utf-8")
                read = reading(reply, month)
                if read is not None and read[0] in REGION_OF:
                    found[read[0]] = read[1]
            pool[f"{month}:{measure}"] = dict(sorted(found.items()))
    return pool


def pool_bytes(pool: Mapping[str, Mapping[str, float]]) -> bytes:
    return (json.dumps(pool, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def load_pool(path: str | Path, sha256: str) -> dict[str, dict[str, float]]:
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SourceError(f"{path} has sha256 {digest}, not the recorded {sha256}; run `fetch` again")
    return json.loads(data)
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `8 passed`

Run: `python -m pytest -q`
Expected: `568 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/weather.py tests/test_gold_weather.py
git commit -m "Read the NCEI climate departures for the weather gold set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: 구간과 삼중항 고르기

**Files:**
- Modify: `src/reasonlineage/gold/weather.py` (상수 추가, 새 절 추가)
- Modify: `tests/test_gold_weather.py` (테스트와 붙임장치 추가)

**Interfaces:**
- Consumes: Task 1의 `REGION_OF`, `MONTHS`, `MEASURES`, `SourceError`, 목록 형식.
- Produces: `BANDS`, `BAND_NAMES = ("easy", "medium", "hard")`, `MAX_PER_STATE = 3`,
  `margin(triple, values) -> float`, `usable(triple, values, band) -> bool`,
  `choose(set_name, pool, band, count, exclude=()) -> list[dict]`.
  `choose`가 돌려주는 항목은 `{"month", "measure", "states", "departures", "regions", "margin"}`이고 Task 3이 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_weather.py`의 4.1 절 뒤, `# --- 4.2 the regions ---` 절 다음에 이어 붙인다.

```python
# --- 4.3 the triples ---

def test_usable_refuses_two_states_from_one_region():
    values = {"Oregon": 4.0, "Washington": 1.0, "Idaho": 0.5}  # all Northwest
    assert not w.usable(("Oregon", "Washington", "Idaho"), values, w.BANDS["tavg"]["easy"])


def test_usable_refuses_a_tie():
    values = {"Oregon": 4.0, "Texas": 4.0, "Maine": 1.0}
    assert not w.usable(("Oregon", "Texas", "Maine"), values, w.BANDS["tavg"]["easy"])
    assert not w.usable(("Oregon", "Texas", "Maine"), values, w.BANDS["tavg"]["medium"])


@pytest.mark.parametrize("measure, gap, band", [
    ("tavg", 2.0, "easy"), ("tavg", 1.9, "medium"), ("tavg", 1.0, "medium"),
    ("tavg", 0.9, "hard"), ("tavg", 0.4, "hard"), ("tavg", 0.3, None),
    ("pcp", 1.5, "easy"), ("pcp", 1.4, "medium"), ("pcp", 0.7, "medium"),
    ("pcp", 0.6, "hard"), ("pcp", 0.3, "hard"), ("pcp", 0.2, None),
])
def test_a_gap_falls_in_one_band_only(measure, gap, band):
    values = {"Oregon": 5.0 + gap, "Texas": 5.0, "Maine": 0.0}
    triple = ("Oregon", "Texas", "Maine")
    assert w.margin(triple, values) == gap
    held = [name for name in w.BAND_NAMES if w.usable(triple, values, w.BANDS[measure][name])]
    assert held == ([band] if band else [])


def test_choose_alternates_the_measure_and_the_month():
    chosen = w.choose("weather-v1", _wide_pool(), "hard", 8)
    assert [(c["measure"], c["month"]) for c in chosen] == [
        ("tavg", 7), ("pcp", 7), ("tavg", 8), ("pcp", 8)] * 2


def test_choose_keeps_every_state_under_the_reuse_cap():
    chosen = w.choose("weather-v1", _wide_pool(), "medium", 20)
    counts: dict[str, int] = {}
    for task in chosen:
        for state in task["states"]:
            counts[state] = counts.get(state, 0) + 1
    assert counts and max(counts.values()) <= w.MAX_PER_STATE


def test_choose_leaves_out_the_triples_it_is_given():
    first = w.choose("weather-v1", _wide_pool(), "easy", 4)
    used = [sorted(task["states"]) for task in first]
    again = w.choose("weather-v1", _wide_pool(), "easy", 4, exclude=used)
    assert all(sorted(task["states"]) not in used for task in again)


def test_choose_says_how_far_it_got_when_a_band_runs_out():
    with pytest.raises(w.SourceError) as exc:
        w.choose("weather-v1", pool(), "easy", 4)
    assert "only 1 of 4" in str(exc.value) and "easy" in str(exc.value)


def test_choose_reports_a_pool_without_the_bucket():
    thin = {key: values for key, values in _wide_pool().items() if key != "8:pcp"}
    with pytest.raises(w.SourceError) as exc:
        w.choose("weather-v1", thin, "easy", 4)
    assert "8:pcp" in str(exc.value)
```

같은 파일 끝에 붙임장치를 붙인다.

```python
# --- fixtures ---

def _wide_pool() -> dict[str, dict[str, float]]:
    """All 48 states, with 0.1-precision departures whose gaps land in every band, shifted per bucket."""
    states = sorted(w.REGION_OF)
    built = {}
    for shift, key in enumerate(("7:tavg", "7:pcp", "8:tavg", "8:pcp")):
        order = states[shift:] + states[:shift]
        built[key] = {state: round(0.5 * i + 0.1 * (i % 4), 1) for i, state in enumerate(order)}
    return built
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `19 failed, 8 passed`, `AttributeError: module 'reasonlineage.gold.weather' has no attribute 'choose'`

- [ ] **Step 3: 구간과 고르기를 쓰기**

`src/reasonlineage/gold/weather.py`의 `REGION_OF` 다음에 상수를 넣는다.

```python
# (low, high) departure between the first and second place, by measure and band (design 4.3).
BANDS: dict[str, dict[str, tuple[float, float]]] = {
    "tavg": {"easy": (2.0, 1e9), "medium": (1.0, 2.0), "hard": (0.4, 1.0)},
    "pcp": {"easy": (1.5, 1e9), "medium": (0.7, 1.5), "hard": (0.3, 0.7)},
}
BAND_NAMES = ("easy", "medium", "hard")
MAX_PER_STATE = 3  # how often one state may appear in a set
```

4.1 절 뒤에 절을 하나 더 넣는다.

```python
# --- 4.3 choosing the triples ---

def margin(triple: Sequence[str], values: Mapping[str, float]) -> float:
    """The gap between first and second place, rounded away from the float error of a 0.1-precision subtraction."""
    first, second, _ = sorted((values[state] for state in triple), reverse=True)
    return round(first - second, 4)


def usable(triple: Sequence[str], values: Mapping[str, float], band: tuple[float, float]) -> bool:
    """Three states from three regions whose first-to-second gap falls in the band (design 4.3)."""
    if len({REGION_OF[state] for state in triple}) < 3:
        return False
    first, second, third = sorted((values[state] for state in triple), reverse=True)
    if first == second or second == third:
        return False
    low, high = band
    return low <= margin(triple, values) < high


def choose(set_name: str, pool: Mapping[str, Mapping[str, float]], band: str, count: int,
           exclude: Sequence[Sequence[str]] = ()) -> list[dict[str, Any]]:
    """`count` triples, alternating measure and month, each state used at most MAX_PER_STATE times.

    The order of the keys and of the candidate triples is fixed by the set name, so the same set is rebuilt
    identically (design 4.3, 4.4).
    """
    taken = {frozenset(triple) for triple in exclude}
    used: dict[str, int] = {}
    chosen: list[dict[str, Any]] = []
    for index in range(count):
        # measure alternates every task, month every two tasks: tavg/7, pcp/7, tavg/8, pcp/8, tavg/7, ...
        measure = MEASURES[index % len(MEASURES)]
        month = MONTHS[(index // len(MEASURES)) % len(MONTHS)]
        key = f"{month}:{measure}"
        if key not in pool:
            raise SourceError(f"the pool has no {key}; run `fetch` again")
        values = pool[key]
        limits = BANDS[measure][band]
        order = shuffled(["|".join(t) for t in itertools.combinations(sorted(values), 3)], f"{set_name}:{key}:{index}")
        for packed in order:
            triple = tuple(packed.split("|"))
            if frozenset(triple) in taken or not usable(triple, values, limits):
                continue
            if any(used.get(state, 0) >= MAX_PER_STATE for state in triple):
                continue
            taken.add(frozenset(triple))
            for state in triple:
                used[state] = used.get(state, 0) + 1
            chosen.append({"month": month, "measure": measure, "states": list(triple),
                           "departures": {state: values[state] for state in triple},
                           "regions": {state: REGION_OF[state] for state in triple},
                           "margin": margin(triple, values)})
            break
        else:
            raise SourceError(f"{set_name}: only {len(chosen)} of {count} tasks could be built; {key} band "
                              f"{band!r} ran out of triples (a state may appear at most {MAX_PER_STATE} times)")
    return chosen
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `27 passed`

Run: `python -m pytest -q`
Expected: `587 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/weather.py tests/test_gold_weather.py
git commit -m "Pick the state triples by band and climate region

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 과제 문구와 파일 쓰기

**Files:**
- Modify: `src/reasonlineage/gold/weather.py` (상수 추가, 새 절 추가)
- Modify: `tests/test_gold_weather.py` (import 두 줄, 테스트, 붙임장치 추가)

**Interfaces:**
- Consumes: Task 2의 `choose`, `margin`; Task 1의 목록 형식; `reasonlineage.gold.build.shuffled`;
  `reasonlineage.engine.config.load_task`(테스트에서만).
- Produces: `MEASURE_WORDS`, `QUESTION`, `question(task, order) -> str`, `make_task(set_name, index, chosen) -> dict`,
  `build(set_name, band, count, pool, source, tasks_dir, gold_dir, exclude=()) -> list[Path]`,
  `triples_of(gold_dir) -> list[list[str]]`. Task 4가 `build`와 `triples_of`를 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_weather.py`의 맨 위 import에 두 줄을 더한다. `import pytest` 위에 `import json`과 빈 줄, `from reasonlineage.gold import weather as w` 위에 `from reasonlineage.engine.config import load_task`가 오게 한다.

```python
import json

import pytest

from reasonlineage.engine.config import load_task
from reasonlineage.gold import weather as w
```

`# --- fixtures ---` 절 **앞에** 테스트를 넣는다.

```python
# --- 4.4 the task and the files ---

def test_the_question_states_the_normal_and_asks_for_the_departure():
    made = w.make_task("weather-v1", 0, _one())
    text = made["task"]["question"]
    assert "1901-2000" in text and "furthest above" in text
    assert "July 2026" in text
    assert sorted(made["task"]["candidates"]) == ["California", "Maine", "Texas"]


def test_the_question_leaks_no_departure_figure():
    made = w.make_task("weather-v1", 0, _one())
    text = made["task"]["question"]
    for value in _one()["departures"].values():
        assert str(value) not in text
    assert "normal" in text and "Northwest" not in text  # the regions stay out of the task


def test_the_gold_names_the_largest_departure():
    made = w.make_task("weather-v1", 0, _one())
    assert made["gold"] == {"approved": ["California"], "failed": ["Maine", "Texas"]}
    assert made["record"]["margin"] == 2.0
    assert made["record"]["regions"]["Maine"] == "Northeast"


def test_build_writes_the_tasks_the_gold_and_the_record(tmp_path):
    written = w.build("weather-v1", "easy", 4, _wide_pool(), {"api": w.API, "pool_sha256": "abc"},
                      tmp_path / "tasks", tmp_path / "gold")
    assert [path.name for path in written] == [f"weather-v1-0{i}.json" for i in range(1, 5)]
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text(encoding="utf-8"))
    record = json.loads((tmp_path / "gold" / "generation.json").read_text(encoding="utf-8"))
    assert gold["source"] == {"api": w.API, "pool_sha256": "abc", "set": "weather-v1", "band": "easy"}
    assert sorted(gold["tasks"]) == sorted(record["tasks"]) == [f"weather-v1-0{i}" for i in range(1, 5)]
    for task_id, truth in gold["tasks"].items():
        assert len(truth["approved"]) == 1 and len(truth["failed"]) == 2
        assert truth["approved"][0] == record["tasks"][task_id]["winner"]


def test_a_built_task_loads_in_the_engine_with_the_gold_candidates(tmp_path):
    w.build("weather-v1", "medium", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text(encoding="utf-8"))
    for path in sorted((tmp_path / "tasks").glob("*.json")):
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}  # what score_run checks
        assert task.category == "analytical"


def test_the_same_set_name_builds_the_same_files_and_another_name_does_not(tmp_path):
    w.build("weather-v1", "hard", 4, _wide_pool(), {}, tmp_path / "a", tmp_path / "ga")
    w.build("weather-v1", "hard", 4, _wide_pool(), {}, tmp_path / "b", tmp_path / "gb")
    w.build("weather-v2", "hard", 4, _wide_pool(), {}, tmp_path / "c", tmp_path / "gc")
    first = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "a").glob("*.json"))]
    same = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "b").glob("*.json"))]
    other = [path.read_text(encoding="utf-8") for path in sorted((tmp_path / "c").glob("*.json"))]
    assert first == same
    assert first != other


def test_build_stops_when_the_task_folder_holds_a_file_it_does_not_build(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "weather-v1-09.json").write_text("{}", encoding="utf-8")
    with pytest.raises(w.SourceError) as exc:
        w.build("weather-v1", "easy", 4, _wide_pool(), {}, tasks, tmp_path / "gold")
    assert "weather-v1-09.json" in str(exc.value)
    assert not (tmp_path / "gold").exists()


def test_build_refuses_an_unknown_band(tmp_path):
    with pytest.raises(w.SourceError) as exc:
        w.build("weather-v1", "medium-hard", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    assert "easy, medium, hard" in str(exc.value)


def test_triples_of_reads_back_what_a_set_used(tmp_path):
    w.build("weather-v1", "easy", 2, _wide_pool(), {}, tmp_path / "tasks", tmp_path / "gold")
    used = w.triples_of(tmp_path / "gold")
    assert len(used) == 2 and all(len(triple) == 3 for triple in used)
    assert w.triples_of(tmp_path / "nothing") == []
```

파일 맨 끝에 붙임장치를 붙인다.

```python
def _one() -> dict:
    return {"month": 7, "measure": "tavg", "states": ["California", "Texas", "Maine"],
            "departures": {"California": 5.3, "Texas": 3.3, "Maine": 1.1},
            "regions": {"California": "West", "Texas": "South", "Maine": "Northeast"}, "margin": 2.0}
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `9 failed, 27 passed`, `AttributeError: module 'reasonlineage.gold.weather' has no attribute 'build'`

- [ ] **Step 3: 과제와 파일 쓰기**

`src/reasonlineage/gold/weather.py`의 `MAX_PER_STATE` 다음에 상수를 넣는다.

```python
MEASURE_WORDS = {"tavg": "average temperature was furthest above",
                 "pcp": "precipitation was furthest above"}
QUESTION = (
    "In {month} 2026, how did each of these three states compare with its own long-term normal? The normal is "
    "that state's 1901-2000 average for the same month. You have no tools and no web access: reason from what "
    "you know about regional climate and the patterns of that summer.\n\n"
    "Candidates: {candidates}\n\n"
    "Which state's {month} 2026 {measure} its 1901-2000 normal? Rank the three, and give the reasoning that "
    "decides the order, the key evidence, and one observation that would confirm your top pick.")
```

파일 끝에 절을 하나 더 넣는다.

```python
# --- 4.4 the task and the files ---

def question(task: Mapping[str, Any], order: Sequence[str]) -> str:
    return QUESTION.format(month=MONTH_NAMES[task["month"]], candidates=", ".join(order),
                           measure=MEASURE_WORDS[task["measure"]])


def make_task(set_name: str, index: int, chosen: Mapping[str, Any]) -> dict[str, Any]:
    """One task's file body, gold entry and record."""
    task_id = f"{set_name}-{index + 1:02d}"
    order = shuffled(list(chosen["states"]), task_id)
    winner = max(chosen["states"], key=lambda state: chosen["departures"][state])
    body = {"id": task_id, "question": question(chosen, order), "candidates": order,
            "category": "analytical", "data_sensitivity": "public"}
    gold = {"approved": [winner], "failed": sorted(state for state in chosen["states"] if state != winner)}
    record = {"month": chosen["month"], "measure": chosen["measure"], "departures": chosen["departures"],
              "regions": chosen["regions"], "margin": chosen["margin"], "winner": winner}
    return {"task": body, "gold": gold, "record": record}


def build(set_name: str, band: str, count: int, pool: Mapping[str, Mapping[str, float]], source: Mapping[str, Any],
          tasks_dir: str | Path, gold_dir: str | Path, exclude: Sequence[Sequence[str]] = ()) -> list[Path]:
    """Write the task files, gold.json and generation.json; nothing is written if a band runs out."""
    if band not in BAND_NAMES:
        raise SourceError(f"unknown band {band!r}; use one of {', '.join(BAND_NAMES)}")
    tasks_dir, gold_dir = Path(tasks_dir), Path(gold_dir)
    ids = [f"{set_name}-{i + 1:02d}" for i in range(count)]
    stale = [f"{path} is not built by this set; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise SourceError("; ".join(stale))
    made = [make_task(set_name, i, chosen) for i, chosen in enumerate(choose(set_name, pool, band, count, exclude))]
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in made:
        path = tasks_dir / f"{task['task']['id']}.json"
        path.write_text(json.dumps(task["task"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    head = dict(source) | {"set": set_name, "band": band}
    for name, body in (("gold.json", {"source": head, "tasks": {t["task"]["id"]: t["gold"] for t in made}}),
                       ("generation.json", {"source": head, "tasks": {t["task"]["id"]: t["record"] for t in made}})):
        (gold_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written


def triples_of(gold_dir: str | Path) -> list[list[str]]:
    """The triples a built set used, for the next set to exclude."""
    path = Path(gold_dir) / "generation.json"
    if not path.exists():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    return [sorted(task["departures"]) for task in record["tasks"].values()]
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_gold_weather.py -q`
Expected: `36 passed`

Run: `python -m pytest -q`
Expected: `596 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/weather.py tests/test_gold_weather.py
git commit -m "Write the weather task, gold and record files

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 빌드 스크립트

**Files:**
- Create: `scripts/build_weather.py`
- Create: `tests/test_build_weather_script.py`

**Interfaces:**
- Consumes: Task 1–3의 `weather` 모듈 전체.
- Produces: 명령 두 개. `fetch`는 `~/.cache/reasonlineage/weather/pool.json`과 색인 `gold/weather/pool.json`을 쓴다.
  `build SET --band easy|medium|hard --tasks N [--exclude-set OTHER ...]`는 `tasks/SET/`과 `gold/SET/`을 쓴다.
  Task 5, 6이 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_build_weather_script.py`를 만든다.

```python
"""The weather set build script (weather design 3, 7). No test calls NCEI."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_weather.py"
sys.path.insert(0, str(ROOT / "src"))

from reasonlineage.gold import weather as wx  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def write_pool(tmp_path: Path) -> Path:
    """A saved pool and the index that points at it, as `fetch` leaves them."""
    states = sorted(wx.REGION_OF)
    pool = {}
    for shift, key in enumerate(("7:tavg", "7:pcp", "8:tavg", "8:pcp")):
        order = states[shift:] + states[:shift]
        pool[key] = {state: round(0.5 * i + 0.1 * (i % 4), 1) for i, state in enumerate(order)}
    data = wx.pool_bytes(pool)
    full = tmp_path / "pool-full.json"
    full.write_bytes(data)
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"api": wx.API, "months": list(wx.MONTHS), "measures": list(wx.MEASURES),
                                 "full_pool": str(full), "sha256": hashlib.sha256(data).hexdigest(),
                                 "readings": pool}), encoding="utf-8")
    return index


def test_the_script_builds_a_set(tmp_path):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "medium", "--tasks", 2)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""
    assert sorted(p.name for p in (tmp_path / "tasks" / "weather-test").iterdir()) == \
        ["weather-test-01.json", "weather-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold" / "weather-test").iterdir()) == ["generation.json", "gold.json"]
    gold = json.loads((tmp_path / "gold" / "weather-test" / "gold.json").read_text(encoding="utf-8"))
    assert gold["source"]["pool_sha256"] == json.loads(index.read_text(encoding="utf-8"))["sha256"]


def test_another_sets_triples_can_be_left_out(tmp_path):
    index = write_pool(tmp_path)
    common = ["--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks"]
    assert run(*common, "build", "weather-calib", "--band", "easy", "--tasks", 2).returncode == 0
    result = run(*common, "build", "weather-main", "--band", "easy", "--tasks", 2, "--exclude-set", "weather-calib")
    assert result.returncode == 0, result.stderr
    first = wx.triples_of(tmp_path / "gold" / "weather-calib")
    assert all(triple not in first for triple in wx.triples_of(tmp_path / "gold" / "weather-main"))


def test_a_missing_pool_says_to_fetch_first(tmp_path):
    result = run("--index", tmp_path / "none.json", "--gold-root", tmp_path / "gold",
                 "--tasks-root", tmp_path / "tasks", "build", "weather-test", "--band", "easy", "--tasks", 2)
    assert result.returncode == 1 and "run `fetch` first" in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_changed_pool_file_says_to_fetch_again(tmp_path):
    index = write_pool(tmp_path)
    (tmp_path / "pool-full.json").write_bytes(b'{"7:tavg": {}}\n')
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "easy", "--tasks", 2)
    assert result.returncode == 1 and "run `fetch` again" in result.stderr


@pytest.mark.parametrize("args, message", [
    (("build", "weather-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("build", "Weather_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("build", "weather-test", "--band", "easy", "--tasks", 0), "must be at least 1"),
    (("build", "weather-test", "--tasks", 2), "the following arguments are required: --band"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks", *args)
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_band_that_runs_out_stops_the_build(tmp_path):
    index = write_pool(tmp_path)
    result = run("--index", index, "--gold-root", tmp_path / "gold", "--tasks-root", tmp_path / "tasks",
                 "build", "weather-test", "--band", "easy", "--tasks", 400)
    assert result.returncode == 1 and "cannot build weather-test: " in result.stderr
    assert "ran out of triples" in result.stderr
    assert not (tmp_path / "gold" / "weather-test").exists()
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_build_weather_script.py -q`
Expected: `9 failed`, `AssertionError: … can't open file '…/scripts/build_weather.py': [Errno 2] No such file or directory`

- [ ] **Step 3: 스크립트 쓰기**

`scripts/build_weather.py`를 만들고 실행 권한을 준다(`chmod +x scripts/build_weather.py`).

```python
#!/usr/bin/env python3
"""Build a climate-departure gold set (weather design 3, 4).

    python scripts/build_weather.py fetch
        # the pool: ~/.cache/reasonlineage/weather/pool.json, and its index gold/weather/pool.json with the sha256
    python scripts/build_weather.py build SET --band easy|medium|hard --tasks N [--exclude-set OTHER ...]
        # tasks/SET/*.json, gold/SET/gold.json and gold/SET/generation.json (no model calls)
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

from reasonlineage.gold import weather as wx  # noqa: E402

INDEX = ROOT / "gold" / "weather" / "pool.json"
FULL = wx.CACHE / "pool.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        pool = wx.fetch_pool(args.cache)
    except wx.SourceError as exc:
        print(f"cannot read NCEI: {exc}", file=sys.stderr)
        return 1
    data = wx.pool_bytes(pool)
    args.full.parent.mkdir(parents=True, exist_ok=True)
    args.full.write_bytes(data)
    write_json(args.index, {"api": wx.API, "months": list(wx.MONTHS), "measures": list(wx.MEASURES),
                            "full_pool": str(args.full), "sha256": hashlib.sha256(data).hexdigest(),
                            "readings": pool})
    print("; ".join(f"{key} {len(values)} states" for key, values in sorted(pool.items())))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    try:
        index = read_json(args.index)
        pool = wx.load_pool(index["full_pool"], index["sha256"])
    except (OSError, KeyError, wx.SourceError) as exc:
        print(f"cannot read the pool ({exc}); run `fetch` first", file=sys.stderr)
        return 1
    exclude = [triple for other in args.exclude_set for triple in wx.triples_of(args.gold_root / other)]
    source = {"api": index["api"], "months": index["months"], "measures": index["measures"],
              "pool_sha256": index["sha256"], "exclude_sets": args.exclude_set}
    try:
        written = wx.build(args.set, args.band, args.tasks, pool, source,
                           args.tasks_root / args.set, args.gold_root / args.set, exclude=exclude)
    except wx.SourceError as exc:
        print(f"cannot build {args.set}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {args.tasks_root / args.set}; "
          f"gold.json and generation.json in {args.gold_root / args.set}")
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
    fetch.add_argument("--cache", type=Path, default=wx.CACHE)
    fetch.add_argument("--full", type=Path, default=FULL)
    build = sub.add_parser("build")
    build.add_argument("set", type=set_name)
    build.add_argument("--band", required=True, choices=wx.BAND_NAMES)
    build.add_argument("--tasks", required=True, type=positive)
    build.add_argument("--exclude-set", type=set_name, action="append", default=[],
                       help="do not reuse that set's triples; repeat for several sets")
    args = parser.parse_args(argv)
    return {"fetch": cmd_fetch, "build": cmd_build}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_build_weather_script.py -q`
Expected: `9 passed`

Run: `python -m pytest -q`
Expected: `605 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
chmod +x scripts/build_weather.py
git add scripts/build_weather.py tests/test_build_weather_script.py
git commit -m "Add the script that builds a weather gold set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: 목록 받기, 보정 세트, 보정 실행

**Files:**
- Create: `gold/weather/pool.json` (색인), `~/.cache/reasonlineage/weather/*.json` (커밋하지 않음)
- Create: `tasks/weather-calib-{easy,medium,hard}/*.json`, `gold/weather-calib-{easy,medium,hard}/gold.json`, `generation.json`
- Create (커밋하지 않음): `.superpowers/sdd/2026-10-03-gold-weather/run_set.sh`

**Interfaces:**
- Consumes: Task 4의 스크립트, `scripts/run_gold.sh`
- Produces: 고른 구간 하나(`easy`, `medium`, `hard`) 또는 "멈춤". Task 6이 쓴다.

- [ ] **Step 1: 목록 받기**

```bash
python scripts/build_weather.py fetch
```

Expected: `7:pcp 48 states; 7:tavg 48 states; 8:pcp 48 states; 8:tavg 48 states`
- 요청 200번에 1~2분이다. 받은 응답은 캐시에 남아서 다시 돌리면 요청하지 않는다.
- 어느 주·월·지표를 못 받았다고 멈추면, 한 번 더 돌린다(캐시가 받은 것은 건너뛴다). 그래도 안 되면 그 메시지를 사용자에게 알리고 멈춘다.

- [ ] **Step 2: 세 보정 세트 만들기**

```bash
for b in easy medium hard; do python scripts/build_weather.py build weather-calib-$b --band $b --tasks 2; done
```

Expected: 세 줄 모두 `2 task files in …/tasks/weather-calib-<구간>; gold.json and generation.json in …/gold/weather-calib-<구간>`

- [ ] **Step 3: 구간 조건을 확인하고 커밋**

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "src")
from reasonlineage.gold import weather as wx
for band in wx.BAND_NAMES:
    record = json.load(open(f"gold/weather-calib-{band}/generation.json"))
    for task_id, task in record["tasks"].items():
        low, high = wx.BANDS[task["measure"]][band]
        regions = set(task["regions"].values())
        assert low <= task["margin"] < high, (task_id, task["margin"])
        assert len(regions) == 3 and len(set(task["departures"].values())) == 3, (task_id, regions)
        print(task_id, task["measure"], task["month"], "margin", task["margin"], task["winner"], sorted(regions))
PY
git add gold/weather/pool.json tasks/weather-calib-* gold/weather-calib-*
for b in easy medium hard; do python scripts/build_weather.py build weather-calib-$b --band $b --tasks 2 >/dev/null; done
git diff --exit-code --stat -- tasks gold && echo same
git commit -m "Add the three calibration sets of the weather gold set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: 과제 6줄이 assert 오류 없이 나오고, 다시 만든 파일이 같아서 `same`이 찍힌다.

- [ ] **Step 4: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-03-gold-weather
mkdir -p $W
cp .superpowers/sdd/2026-10-02-gold-basket/run_set.sh $W/run_set.sh
pgrep -f "reasonlineage (run|resume)" && echo "another run is going; wait for it" || true
for b in easy medium hard; do setsid nohup bash $W/run_set.sh weather-calib-$b >> $W/calib.log 2>&1 < /dev/null; done &
```

- 다른 세트의 실행이 돌고 있으면 끝나기를 기다린다(Global Constraints).
- 대기는 백그라운드 명령으로 한다: `for i in $(seq 1 200); do pgrep -f "run_set.sh weather-calib" >/dev/null || break; sleep 30; done; tail -20 $W/calib.log`
- 계산이 없어서 답이 짧다. 과제당 5–8분, 6과제로 45분쯤이다.

- [ ] **Step 5: 규칙대로 구간 고르기**

```bash
python - <<'PY'
import json
order = ["easy", "medium", "hard"]
share = {b: json.load(open(f"runs/gold-weather-calib-{b}/report.json"))["level1"]["share_correct"] for b in order}
ok = [b for b in order if 0.375 <= share[b] <= 0.75]
pick = min(ok, key=lambda b: (abs(share[b] - 0.6), -order.index(b))) if ok else None
print(share, "->", pick or "stop: no band in 0.375-0.75")
PY
```

Expected: 구간별 비율과 고른 구간이 한 줄로 나온다.
- 고른 구간이 없으면 멈추고 사용자와 정한다(설계 5.1). 모두 0.375 미만이면 **더 어렵게 만들지 않는다**. 세 주를 두 주로 줄이거나, 편차가 큰 묶음만 쓰는 쪽을 제안한다.
- 진행 기록에 세 비율과 고른 구간을 적는다.

---

### Task 6: 본 세트와 본 실행

**Files:**
- Create: `tasks/weather-v1/*.json`, `gold/weather-v1/gold.json`, `gold/weather-v1/generation.json`

**Interfaces:**
- Consumes: Task 5의 고른 구간 `BAND`, 실행 스크립트
- Produces: `runs/gold-weather-v1/report.json`과 `analysis.md`. Task 7이 읽는다.

- [ ] **Step 1: 본 세트 만들기와 커밋**

```bash
BAND=<Task 5에서 고른 구간>
python scripts/build_weather.py build weather-v1 --band "$BAND" --tasks 20   --exclude-set weather-calib-easy --exclude-set weather-calib-medium --exclude-set weather-calib-hard
python - <<'PY'
import json, sys
from collections import Counter
sys.path.insert(0, "src")
from reasonlineage.gold import weather as wx
record = json.load(open("gold/weather-v1/generation.json"))
band = record["source"]["band"]
used = Counter()
for task_id, task in record["tasks"].items():
    low, high = wx.BANDS[task["measure"]][band]
    assert low <= task["margin"] < high, (task_id, task["margin"])
    assert len(set(task["regions"].values())) == 3 and len(set(task["departures"].values())) == 3, task_id
    used.update(task["departures"].keys())
print(band, Counter((t["measure"], t["month"]) for t in record["tasks"].values()), "| max reuse", max(used.values()))
PY
git add gold/weather-v1 tasks/weather-v1
git commit -m "Build the weather gold set v1

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: `<구간> Counter({('tavg', 7): 5, ('pcp', 7): 5, ('tavg', 8): 5, ('pcp', 8): 5}) | max reuse 3`
(지표 10:10, 월 10:10, 한 주가 최대 3번)

- [ ] **Step 2: 과제 하나를 사용자에게 보여 주기**

```bash
python -c "import json; print(json.load(open('tasks/weather-v1/weather-v1-01.json'))['question'])"
python -c "
import json; r=json.load(open('gold/weather-v1/generation.json'))['tasks']['weather-v1-01']
print('truth:', r['measure'], r['month'], r['departures'], '| margin', r['margin'], '| winner', r['winner'])"
```

과제 문구와 실제 편차를 보여 주고, 묻는 바가 분명한지 확인받는다. 정답은 NCEI 수치이므로 검토가 아니라 확인이다. 답을 기다리되, 수정 요청이 없으면 Step 3으로 간다.

- [ ] **Step 3: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-03-gold-weather
setsid nohup bash $W/run_set.sh weather-v1 > $W/main.log 2>&1 < /dev/null &
```

Task 5 Step 4와 같은 방식으로 기다린다. 20과제로 약 2.5시간이다.

- [ ] **Step 4: 쌍이 모자라면 과제를 더하기**

```bash
python -c "import json; l=json.load(open('runs/gold-weather-v1/report.json'))['level1']; print(l['verdict'], l['share_correct'], l['pairs'])"
```

- `pairs`가 10개 이상이면 Task 7로 간다.
- 10개 미만이고 천장도 아니면, 같은 구간에서 과제 10개를 더 만들어 이어 붙인다(설계 5.2). Step 1의 명령을 `--tasks 30`으로 다시 돌리면 앞 20과제는 그대로이고 10개가 더 생긴다(같은 세트 이름이면 같은 삼중항이 같은 순서로 나온다). 그다음 같은 실행 스크립트를 다시 돌린다(끝난 과제는 건너뛴다).
- 과제를 더한 뒤에는 Step 1의 확인 명령을 다시 돌려 구간과 재사용 상한을 확인하고 커밋한다.

---

### Task 7: 분석 보고

**Files:**
- Read: `runs/gold-weather-v1/report.json`, `runs/gold-weather-v1/analysis.md`, `gold/weather-v1/generation.json`

**Interfaces:**
- Consumes: Task 6의 실행 결과
- Produces: 사용자에게 보내는 결론과 메모리 기록

- [ ] **Step 1: 지표별·월별로 나눠 세기**

```bash
python - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from reasonlineage.diagnose.gold import level1, score_run
gold = json.load(open("gold/weather-v1/gold.json"))
record = json.load(open("gold/weather-v1/generation.json"))["tasks"]
runs = [score_run(d, gold) for d in sorted(Path("runs/gold-weather-v1").glob("*/")) if (d / "header.json").is_file()]
runs = [r for r in runs if r["status"] == "scored"]
def show(name, keep):
    part = [r for r in runs if keep(record[r["task"]])]
    out = level1(part)
    print(f"{name:>8}: tasks {out['tasks']:>2} share {out['share_correct']:.3f} pairs {out['pairs']:>3} "
          f"concordance {out['concordance']} -> {out['verdict']}")
show("all", lambda t: True)
for measure in ("tavg", "pcp"):
    show(measure, lambda t, m=measure: t["measure"] == m)
for month in (7, 8):
    show(f"month {month}", lambda t, n=month: t["month"] == n)
PY
```

Expected: 다섯 줄. 전체 한 줄과 지표 둘, 월 둘이다.
- 부분집합의 `verdict`는 보조로만 읽는다. 10과제면 쌍이 10개에 못 미쳐 `hold: too few pairs`가 나오기 쉽다. 비교할 값은 `share`와 `concordance`다.

- [ ] **Step 2: 사용자에게 알리기**

`runs/gold-weather-v1/analysis.md`를 읽고 Step 1의 다섯 줄과 함께 알린다.
- 한 줄 결론으로 시작한다: 신호 / 신호 없음 / 보류(천장 또는 쌍 부족), 그리고 왜인지.
- 이어서 근거 수치를 두세 줄로 적는다: 정답률, 쌍 수, 일치도, 심사위원·저자별로 눈에 띄는 점.
- **지표별·월별 차이를 한두 줄로 적는다.** 한쪽 지표만 신호가 나오는 경우를 구분할 수 있어야 한다(설계 6).
- 틀린 답이 어떤 주를 골랐는지 한두 줄로 적는다. `generation.json`의 편차와 지역으로 확인할 수 있다. 특히 "더 더운 남부 주를 골랐지만 평년 대비로는 북부가 더 벗어났다" 같은 흔한 오답을 찾는다(편차를 절대값으로 착각한 경우다).
- **다른 세트의 판정과 나란히 적는다.** 세트마다 따로 판정하고, 합친 수치는 보조로만 적는다.
- 보고서 경로를 링크한다. `signal`이면 2단계 기준을 먼저 정하자고 제안한다. 바닥(모든 구간 0.375 미만)이면 조사 보고서의 예측 축으로 갈지 묻는다.
- 메모리에 결과를 남긴다(`gold-weather-result`), `three-ceilings-one-cause`에 이 세트의 결과를 연결한다.
