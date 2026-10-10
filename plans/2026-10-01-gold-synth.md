# 합성 정답지 (숨은 법칙) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 생물·약리 법칙으로 만든 합성 과제(데이터표 + 후보 모델 3개, 정답은 데이터를 만든 모델)로 1단계("첫 세대 적합도가 정답을 따라가는가")를 잰다. 보정 실행으로 난이도 구간을 고르고, 본 세트 10과제로 판정한다.

**Architecture:** 새 모듈 `src/reasonlineage/gold/synth.py` 하나가 법칙 계열과 모델, 데이터 만들기, 맞춤과 사후확률, 과제·정답·생성 기록 파일 쓰기를 맡는다. 스크립트 `scripts/build_synth.py`가 세트를 만들고, 실행과 판정은 기존 `scripts/run_gold.sh`와 `reasonlineage gold`를 그대로 쓴다. 엔진은 바꾸지 않는다.

**Tech Stack:** Python 3.11 이상, numpy와 scipy(선택 의존성 `gold`, 이 세트를 만들 때만), pytest, bash.

**Spec:** `specs/2026-10-01-gold-synth-design.md` (판정 규칙은 `specs/2026-09-30-gold-dev-design.md` 6.1–6.2)

**미리 확인한 것 (2026-10-01):**
- 이 계획의 코드는 임시 복사본에서 모두 짜고 돌려 봤다. 그다음 `gold-synth` 브랜치의 새 복사본에 Task 1–5를 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED 단계는 아래 Expected처럼 실패했고, GREEN 단계는 통과했다. 전체 테스트는 Task 1–5 뒤에 383 → 405 → 409 → 414 → 420 passed, 3 deselected다.
- 맞춤이 국소 최솟값에 멈추면 정답지가 틀려진다. 그래서 계열마다 거르기를 통과한 데이터 48개를 무작위 재시작 60회와 비교했고, 더 나은 맞춤은 없었다. 0차 소실 모델은 처음에 3개에서 덜 맞았고, 촘촘한 시작 격자로 고쳤다.
- 세트 만들기는 빠르다. 보정 세트는 2과제에 1–2초, 10과제 세트는 구간마다 6–10초 걸렸다. 과제 하나를 채우는 데 1–182회 뽑았다(한도 2,000회).

## Global Constraints

- Python 3.11 이상. 엔진의 `dependencies = []`는 그대로 둔다. numpy(≥1.26)와 scipy(≥1.11)는 선택 의존성 `gold`에만 넣는다. 합성 세트 테스트는 scipy가 없으면 건너뛴다(`pytest.importorskip("scipy")`).
- 작업은 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 브랜치 `gold-synth`에서 한다. 명령은 이 폴더에서 돌린다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령을 직접 부를 때는 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다. 키는 reasonlineage 프로그램만 읽는다.
- 사용자의 이메일이나 다른 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다.
- 모델을 부르는 실행(Task 7, 8)은 사용자에게 먼저 묻는다. Task 1–6은 모델을 부르지 않는다.
- 난이도 구간(정답 모델의 사후확률): easy ≥ 0.999, medium 0.97 이상 0.999 미만, hard 0.90 이상 0.97 미만.
- 보정 구간 고르기(실행 전에 고정): 비율 `share_correct`가 0.375–0.75인 구간 가운데 0.6에 가장 가까운 구간을 고른다. 같으면 더 어려운 구간을 고른다. 세 구간이 모두 0.75를 넘거나 모두 0.375 미만이면 멈추고 사용자와 정한다.
- 1단계 판정 기준은 개발용 세트와 같고 바꾸지 않는다: 천장 80%, 쌍 10개, 일치율 0.70, 적합도 동점 0.5.
- 결과를 본 뒤 구간, 과제, 판정 기준을 바꾸지 않는다.
- 오류 메시지는 무엇이 잘못됐고 무엇을 하면 되는지 말한다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 테스트는 그 코드를 맡은 Task에 들어 있다.
- 같은 세트를 다시 만들면 파일이 바이트까지 같아야 한다. 커밋한 세트를 다시 만들어도 git 변경이 없어야 한다(Task 4 `test_building_the_same_set_again_gives_the_same_bytes`, Task 6 Step 3).
- 질문의 기호(µ, ², ·, −)가 과제 파일을 거쳐 엔진이 읽은 질문에 그대로 남아야 한다(Task 4 `test_the_symbols_in_a_question_survive_the_task_file`).
- 다른 세트의 과제가 있는 폴더(예: 세트 이름을 잘못 줘서 `tasks/repodb-dev`)에 만들면, 아무것도 덮어쓰지 않고 멈춰야 한다(Task 4 `test_build_refuses_files_it_does_not_make_and_writes_nothing`, Task 5 `test_a_stale_task_file_stops_the_build`).
- 맞춤 경고(OptimizeWarning, overflow)가 화면을 채우면 안 된다. 성공한 만들기의 stderr는 비어 있어야 한다(Task 5 `test_the_script_builds_a_set`).
- 후보가 구별되지 않는 데이터(예: 억제 효과가 없는 효소 데이터)는 정답지에 들어가면 안 된다(Task 2 `test_data_that_do_not_tell_the_models_apart_are_not_kept`).

---

### Task 1: 법칙 계열과 후보 모델

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies]`)
- Create: `src/reasonlineage/gold/synth.py`
- Create: `tests/test_gold_synth.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `Model(name: str, formula: str, f: Callable[..., np.ndarray])`
  - `Family(key, context, columns, unit, x, params, models, sample, starts)`
    - `x: np.ndarray`는 모양이 `(n,)`이다. 효소 계열만 `(2, n)`이고, 행은 기질과 억제제다.
    - `sample(rng, i) -> tuple[float, ...]`는 i번째 모델의 참 파라미터다.
    - `starts(x, y) -> list[tuple]`는 맞춤 시작점이다.
  - 모델 함수 12개
    - `hyperbolic`, `sigmoid`, `loglinear`
    - `competitive`, `noncompetitive`, `uncompetitive`
    - `logistic`, `gompertz`, `monomolecular`
    - `first_order`, `zero_order`, `second_order`
  - `DOSE`, `ENZYME`, `GROWTH`, `ELIMINATION`
  - `FAMILIES = (DOSE, ENZYME, GROWTH, ELIMINATION)`

- [ ] **Step 1: 선택 의존성 넣기**

`pyproject.toml`의 `dev = ["pytest>=8"]` 줄 바로 아래에 두 줄을 넣는다.

```toml
# Building the synthetic gold set only (gold synth design 3); the engine needs none.
gold = ["numpy>=1.26", "scipy>=1.11"]
```

- [ ] **Step 2: 실패하는 테스트 쓰기**

`tests/test_gold_synth.py`를 만든다.

```python
"""The synthetic hidden-law gold set (gold synth design 4): models, fits, bands, tasks and files."""

import numpy as np
import pytest

pytest.importorskip("scipy")  # the gold extra; the base suite runs without it (design 8)

from reasonlineage.gold import synth  # noqa: E402


def test_each_family_has_three_models_with_their_own_names():
    names = [m.name for f in synth.FAMILIES for m in f.models]
    assert [f.key for f in synth.FAMILIES] == ["dose", "enzyme", "growth", "elimination"]
    assert all(len(f.models) == 3 for f in synth.FAMILIES) and len(set(names)) == 12


@pytest.mark.parametrize("f, args, expected", [
    (synth.hyperbolic, (1.0, 80, 1.0), 40.0),
    (synth.sigmoid, (2.0, 80, 1.0), 64.0),
    (synth.loglinear, (np.e, 10, 1.0), 10.0),
    (synth.competitive, ((20.0, 10.0), 20, 10, 10), 10.0),
    (synth.noncompetitive, ((20.0, 10.0), 20, 10, 10), 400 / 60),
    (synth.uncompetitive, ((20.0, 10.0), 20, 10, 10), 8.0),
    (synth.logistic, (np.log(9) / 0.3, 0.1, 0.3, 1.0), 0.5),
    (synth.gompertz, (0.0, 0.1, 0.3, 1.0), 0.1),
    (synth.monomolecular, (np.log(2) / 0.2, 0.0001, 0.2, 1.0), 0.50005),
    (synth.first_order, (np.log(2) / 0.5, 10, 0.5), 5.0),
    (synth.zero_order, (30.0, 10, 0.5), 0.0),
    (synth.second_order, (0.5, 10, 0.2), 5.0),
])
def test_each_model_gives_its_textbook_value(f, args, expected):
    x, *params = args
    assert float(f(np.asarray(x, dtype=float), *params)) == pytest.approx(expected)
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: FAIL, `ImportError: cannot import name 'synth' from 'reasonlineage.gold'` (1 error)

- [ ] **Step 4: 모듈 쓰기**

`src/reasonlineage/gold/synth.py`를 만든다.

```python
"""Synthetic hidden-law gold set (gold synth design).

Each task shows noisy data drawn from one of three candidate biological models and asks which model made them.
The data are drawn afresh, so the answer is written nowhere. A task is kept only when the data support the true
model: its posterior among the three candidates, fitted to the data the models see, lies in the chosen band.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class Model:
    name: str
    formula: str
    f: Callable[..., np.ndarray]


@dataclass(frozen=True)
class Family:
    key: str
    context: str
    columns: tuple[str, ...]  # table headers: the x columns, then the measured value
    unit: str  # unit of the measured value, for the error SD
    x: np.ndarray  # shape (n,) or (columns - 1, n)
    params: tuple[str, ...]
    models: tuple[Model, Model, Model]
    sample: Callable[[np.random.Generator, int], tuple[float, ...]]  # true parameters for model i
    starts: Callable[[np.ndarray, np.ndarray], list[tuple[float, ...]]]  # fit starting points from the data


# --- dose-response: drug concentration (µM) -> effect (% of maximum) ---

def hyperbolic(c, emax, ec50):
    return emax * c / (ec50 + c)


def sigmoid(c, emax, ec50):
    return emax * c**2 / (ec50**2 + c**2)


def loglinear(c, m, c0):
    return m * np.log(c / c0)


def _dose_sample(rng, i):
    top = rng.uniform(60, 100)
    if i < 2:
        return top, float(np.exp(rng.uniform(np.log(0.1), np.log(10))))
    c0 = float(np.exp(rng.uniform(np.log(0.001), np.log(0.008))))
    return top / np.log(100 / c0), c0


def _dose_starts(x, y):
    top = max(float(y.max()), 1e-3)
    sat = [(top * k, float(e)) for k in (1.0, 1.5) for e in (0.1, 1.0, 10.0)]
    lin = [(top / np.log(x.max() / c0), c0) for c0 in (1e-4, 1e-3, 5e-3)]
    return sat + lin


DOSE = Family(
    key="dose",
    context="Cultured cells were exposed to a drug at 10 concentrations, and the drug effect was measured as a "
            "percentage of the maximal possible effect.",
    columns=("concentration (µM)", "effect (% of maximum)"), unit="%",
    x=np.logspace(-2, 2, 10),
    params=("Emax", "EC50"),
    models=(Model("Hyperbolic Emax model", "E = Emax·C/(EC50 + C)", hyperbolic),
            Model("Sigmoid Emax model (Hill coefficient 2)", "E = Emax·C²/(EC50² + C²)", sigmoid),
            Model("Log-linear model", "E = m·ln(C/C0)", loglinear)),
    sample=_dose_sample, starts=_dose_starts)


# --- enzyme inhibition: substrate S and inhibitor I (µM) -> initial velocity (µM/min) ---

def competitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / (km * (1 + i / ki) + s)


def noncompetitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / ((km + s) * (1 + i / ki))


def uncompetitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / (km + s * (1 + i / ki))


INHIBITOR = 10.0
_S = np.round(np.logspace(0, np.log10(200), 8), 1)


def _enzyme_sample(rng, i):
    return (rng.uniform(10, 50), float(np.exp(rng.uniform(np.log(5), np.log(40)))),
            float(np.exp(rng.uniform(np.log(2), np.log(20)))))


def _enzyme_starts(x, y):
    top = max(float(y.max()), 1e-3)
    return [(top * k, km, ki) for k in (1.0, 2.0) for km in (5.0, 30.0) for ki in (2.0, 20.0)]


ENZYME = Family(
    key="enzyme",
    context=f"The initial velocity of a purified enzyme was measured at 8 substrate concentrations, without "
            f"inhibitor and with an inhibitor at {INHIBITOR:g} µM.",
    columns=("substrate (µM)", "inhibitor (µM)", "initial velocity (µM/min)"), unit="µM/min",
    x=np.vstack([np.tile(_S, 2), np.repeat([0.0, INHIBITOR], len(_S))]),
    params=("Vmax", "Km", "Ki"),
    models=(Model("Competitive inhibition", "v = Vmax·S/(Km·(1 + I/Ki) + S)", competitive),
            Model("Noncompetitive inhibition", "v = Vmax·S/((Km + S)·(1 + I/Ki))", noncompetitive),
            Model("Uncompetitive inhibition", "v = Vmax·S/(Km + S·(1 + I/Ki))", uncompetitive)),
    sample=_enzyme_sample, starts=_enzyme_starts)


# --- cell growth: time (h) -> OD600 ---

def logistic(t, n0, r, k):
    return k / (1 + (k - n0) / n0 * np.exp(-r * t))


def gompertz(t, n0, r, k):
    return k * np.exp(np.log(n0 / k) * np.exp(-r * t))


def monomolecular(t, n0, r, k):
    return k - (k - n0) * np.exp(-r * t)


_GROWTH_RATE = ((0.15, 0.4), (0.06, 0.2), (0.07, 0.2))


def _growth_sample(rng, i):
    return rng.uniform(0.02, 0.08), rng.uniform(*_GROWTH_RATE[i]), rng.uniform(0.8, 1.5)


def _growth_starts(x, y):
    n0, k = max(float(y[0]), 1e-3), max(float(y.max()), 2e-3)
    return [(n0, r, k) for r in (0.05, 0.1, 0.2, 0.4)]


GROWTH = Family(
    key="growth",
    context="A bacterial culture was grown in batch, and its optical density (OD600) was measured every 4 hours.",
    columns=("time (h)", "OD600"), unit="OD units",
    x=np.arange(0.0, 48.0, 4.0),
    params=("N0", "r", "K"),
    models=(Model("Logistic growth", "N = K/(1 + ((K − N0)/N0)·e^(−r·t))", logistic),
            Model("Gompertz growth", "N = K·exp(ln(N0/K)·e^(−r·t))", gompertz),
            Model("Monomolecular growth", "N = K − (K − N0)·e^(−r·t)", monomolecular)),
    sample=_growth_sample, starts=_growth_starts)


# --- drug elimination: time after an intravenous dose (h) -> plasma concentration (mg/L) ---

def first_order(t, c0, k):
    return c0 * np.exp(-k * t)


def zero_order(t, c0, k0):
    return np.maximum(c0 - k0 * t, 0.0)


def second_order(t, c0, k2):
    return c0 / (1 + c0 * k2 * t)


_T_END = 12.0


def _elimination_sample(rng, i):
    c0, left = rng.uniform(5, 50), rng.uniform(0.05, 0.3)  # share of the dose left at the last sample
    rate = (-np.log(left) / _T_END, (1 - left) * c0 / _T_END, (1 / left - 1) / (_T_END * c0))[i]
    return c0, rate


def _elimination_starts(x, y):
    # A dense grid: the zero-order model's kink traps a fit started far away (checked against random restarts).
    c0 = max(float(y[0]), 1e-3)
    return [(c * c0, rate) for c in np.linspace(0.6, 2.0, 15) for rate in np.logspace(-4, 1, 40)]


ELIMINATION = Family(
    key="elimination",
    context="After a single intravenous bolus dose of a drug, its plasma concentration was measured at 10 time points.",
    columns=("time (h)", "plasma concentration (mg/L)"), unit="mg/L",
    x=np.array([0.5, 1, 1.5, 2, 3, 4, 6, 8, 10, 12.0]),
    params=("C0", "k"),
    models=(Model("First-order elimination", "C = C0·e^(−k·t)", first_order),
            Model("Zero-order elimination", "C = max(C0 − k0·t, 0)", zero_order),
            Model("Second-order elimination", "C = C0/(1 + C0·k2·t)", second_order)),
    sample=_elimination_sample, starts=_elimination_starts)


FAMILIES: tuple[Family, ...] = (DOSE, ENZYME, GROWTH, ELIMINATION)
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: `13 passed`

Run: `python -m pytest -q`
Expected: `383 passed, 3 deselected`

- [ ] **Step 6: 커밋**

```bash
git add pyproject.toml src/reasonlineage/gold/synth.py tests/test_gold_synth.py
git commit -m "Add the bio-shaped model families for the synthetic gold set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 맞춤, 사후확률, 난이도 구간

**Files:**
- Modify: `src/reasonlineage/gold/synth.py` (import 블록, `FAMILIES` 줄 뒤)
- Modify: `tests/test_gold_synth.py` (끝에 더하기)

**Interfaces:**
- Consumes: Task 1의 `Model`, `Family`, `FAMILIES`, `ENZYME`
- Produces:
  - `BANDS: dict[str, tuple[float, float]]`: 아래 경계는 포함하고, 위 경계는 포함하지 않는다.
  - `FIT_FROM = 8`
  - `round3(values) -> np.ndarray`
  - `fit(model, family, y) -> tuple[float, tuple[float, ...]] | None`: 결과는 (RSS, 파라미터)다.
  - `posteriors(family, y, sigma) -> list[dict] | None`
    - 모델 순서대로 `{"model", "rss", "posterior", "params"}`를 낸다.
    - 하나라도 맞춤이 실패하면 None이다.
  - `band_of(posterior) -> str | None`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_synth.py` 끝에 더한다.

```python
@pytest.mark.parametrize("family", synth.FAMILIES, ids=lambda f: f.key)
@pytest.mark.parametrize("truth", [0, 1, 2])
def test_a_fit_to_clean_data_finds_the_true_model(family, truth):
    params = family.sample(np.random.default_rng(1), truth)
    y = family.models[truth].f(family.x, *params)
    fits = synth.posteriors(family, y, sigma=0.01 * float(np.max(y)))
    assert fits[truth]["rss"] == pytest.approx(0, abs=1e-6)
    assert fits[truth]["params"] == pytest.approx(list(params), rel=1e-2)
    assert fits[truth]["posterior"] > 0.999


def test_data_that_do_not_tell_the_models_apart_are_not_kept():
    # Without inhibition the three inhibition types are the same curve, so no posterior reaches 0.9.
    s, i = synth.ENZYME.x
    y = 30 * s / (10 + s)
    fits = synth.posteriors(synth.ENZYME, y, sigma=0.5)
    assert all(f["posterior"] < 0.9 for f in fits)
    assert synth.band_of(max(f["posterior"] for f in fits)) is None


@pytest.mark.parametrize("posterior, band", [
    (1.0, "easy"), (0.999, "easy"), (0.9989, "medium"), (0.97, "medium"),
    (0.9699, "hard"), (0.9, "hard"), (0.8999, None), (0.5, None),
])
def test_bands_split_the_true_models_posterior(posterior, band):
    assert synth.band_of(posterior) == band


def test_shown_values_have_three_significant_digits():
    assert synth.round3(np.array([123.456, 0.0012345, -9.8765])).tolist() == [123.0, 0.00123, -9.88]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: FAIL, `22 failed, 13 passed`, `AttributeError: module 'reasonlineage.gold.synth' has no attribute 'posteriors'` 등

- [ ] **Step 3: 맞춤과 구간 쓰기**

`synth.py`의 import 블록(모듈 docstring 아래부터 `import numpy as np`까지)을 다음으로 바꾼다.

```python
import warnings
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit
```

`FAMILIES: tuple[Family, ...] = (DOSE, ENZYME, GROWTH, ELIMINATION)` 줄 바로 뒤, 파일 끝에 더한다.

```python
# The true model's posterior for each band (gold synth design 4.3): low bound inclusive, high bound exclusive.
BANDS: dict[str, tuple[float, float]] = {"easy": (0.999, 1.01), "medium": (0.97, 0.999), "hard": (0.90, 0.97)}
FIT_FROM = 8  # starting points refined per model


def round3(values: np.ndarray) -> np.ndarray:
    """Values rounded to 3 significant digits, as the task shows them."""
    return np.array([float(f"{v:.3g}") for v in np.ravel(values)]).reshape(np.shape(values))


def fit(model: Model, family: Family, y: np.ndarray) -> tuple[float, tuple[float, ...]] | None:
    """The least residual sum of squares of `model` on the data, with its parameters.

    Refines the FIT_FROM starting points with the lowest residuals; parameters stay positive. None when no start
    converges.
    """
    def rss(p):
        with np.errstate(all="ignore"):
            return float(np.sum((model.f(family.x, *p) - y) ** 2))

    scored = sorted((r, p0) for p0 in family.starts(family.x, y) if np.isfinite(r := rss(p0)))
    best = None
    for _, p0 in scored[:FIT_FROM]:
        try:
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore", OptimizeWarning)
                p, _ = curve_fit(model.f, family.x, y, p0=p0, bounds=(1e-9, np.inf), maxfev=5000)
        except (RuntimeError, ValueError):
            continue
        r = rss(p)
        if np.isfinite(r) and (best is None or r < best[0]):
            best = (r, tuple(float(v) for v in p))
    return best


def posteriors(family: Family, y: np.ndarray, sigma: float) -> list[dict[str, Any]] | None:
    """Each candidate's fit and posterior, in the family's model order; None when any fit fails.

    The three models have the same number of parameters, so the BIC weights reduce to exp(−RSS/2σ²) (design 4.3).
    """
    fits = [fit(model, family, y) for model in family.models]
    if any(f is None for f in fits):
        return None
    rss = np.array([f[0] for f in fits])
    logw = -(rss - rss.min()) / (2 * sigma**2)
    w = np.exp(logw) / np.exp(logw).sum()
    return [{"model": m.name, "rss": round(f[0], 6), "posterior": float(p), "params": [round(v, 6) for v in f[1]]}
            for m, f, p in zip(family.models, fits, w)]


def band_of(posterior: float) -> str | None:
    for band, (low, high) in BANDS.items():
        if low <= posterior < high:
            return band
    return None

```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: `35 passed`

Run: `python -m pytest -q`
Expected: `405 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/synth.py tests/test_gold_synth.py
git commit -m "Fit the candidate models and band tasks by the true model's posterior

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 과제 하나 만들기

**Files:**
- Modify: `src/reasonlineage/gold/synth.py` (import 블록, 파일 끝)
- Modify: `tests/test_gold_synth.py` (import 블록, 끝에 더하기)

**Interfaces:**
- Consumes:
  - Task 1의 `FAMILIES`, `DOSE`
  - Task 2의 `round3`, `posteriors`, `band_of`
  - `reasonlineage.gold.build.shuffled(items, key)`
- Produces:
  - `SynthError(RuntimeError)`
  - `MAX_TRIES = 2000`
  - `assignment(index) -> (Family, int)`
  - `draw(family, truth, band, rng) -> dict | None`
  - `question(family, y, sigma, order) -> str`
  - `make_task(set_name, index, band) -> {"task": dict, "gold": dict, "record": dict}`
    - `task`는 엔진 과제 형식이다(`id`, `question`, `candidates`, `category: analytical`, `data_sensitivity: public`).
    - `gold`는 `{"approved": [정답], "failed": [나머지 둘, 정렬]}`이다.
    - `record`는 `family`, `truth`, `params`, `sigma`, `tries`, `fits`다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_synth.py`의 docstring 아래 import 블록(`from reasonlineage.gold import synth  # noqa: E402`까지)을 다음으로 바꾼다.

```python
from collections import Counter

import numpy as np
import pytest

pytest.importorskip("scipy")  # the gold extra; the base suite runs without it (design 8)

from reasonlineage.gold import synth  # noqa: E402
```

파일 끝에 더한다.

```python
def test_tasks_rotate_families_and_true_models():
    picks = [synth.assignment(i) for i in range(10)]
    assert Counter(f.key for f, _ in picks) == {"dose": 3, "enzyme": 3, "growth": 2, "elimination": 2}
    assert [t for f, t in picks if f.key == "dose"] == [0, 1, 2]
    assert [t for f, t in picks if f.key == "growth"] == [0, 1]


def test_a_task_shows_the_data_and_candidates_and_its_truth_is_in_the_band():
    made = synth.make_task("synth-test", 0, "easy")
    task, gold, record = made["task"], made["gold"], made["record"]
    names = [m.name for m in synth.DOSE.models]
    assert task["id"] == "synth-test-01" and sorted(task["candidates"]) == sorted(names)
    assert (task["category"], task["data_sensitivity"]) == ("analytical", "public")
    assert gold == {"approved": ["Hyperbolic Emax model"], "failed": sorted(names[1:])}
    assert record["family"] == "dose" and record["truth"] == "Hyperbolic Emax model"
    posterior = {f["model"]: f["posterior"] for f in record["fits"]}
    assert synth.band_of(posterior["Hyperbolic Emax model"]) == "easy"
    question = task["question"]
    assert f"Measurement error is Gaussian with SD {record['sigma']:.3g} %." in question
    assert "| concentration (µM) | effect (% of maximum) |" in question
    lines = [line for line in question.splitlines() if line.startswith("- ")]
    assert lines == [f"- {name}: {next(m.formula for m in synth.DOSE.models if m.name == name)}" for name in task["candidates"]]
    values = [float(row.split("|")[2]) for row in question.splitlines() if row.startswith("| ") and "µM" not in row and "---" not in row]
    assert len(values) == 10 and min(values) >= 0


def test_the_same_set_gives_the_same_task_and_another_set_other_data():
    first, again = synth.make_task("synth-test", 1, "easy"), synth.make_task("synth-test", 1, "easy")
    assert first == again
    assert synth.make_task("synth-other", 1, "easy")["task"]["question"] != first["task"]["question"]


def test_a_band_that_cannot_be_filled_stops_with_the_count(monkeypatch):
    monkeypatch.setattr(synth, "MAX_TRIES", 3)
    monkeypatch.setattr(synth, "draw", lambda *args: None)
    with pytest.raises(synth.SynthError, match="synth-test-01: no dose data .* band 'hard' after 3 draws"):
        synth.make_task("synth-test", 0, "hard")
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: FAIL, `4 failed, 35 passed`, `AttributeError: module 'reasonlineage.gold.synth' has no attribute 'assignment'`(그리고 `make_task`, `MAX_TRIES`)

- [ ] **Step 3: 과제 만들기 쓰기**

`synth.py`의 import 블록을 다음으로 바꾼다.

```python
import hashlib
import warnings
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .build import shuffled
```

파일 끝에 더한다.

```python
class SynthError(RuntimeError):
    """A set could not be built: a band could not be filled, or the task folder holds files it does not build."""


MAX_TRIES = 2000  # draws per task before giving up (design 7)


def _rng(set_name: str, index: int) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{set_name}:{index}".encode("utf-8")).hexdigest()[:16], 16))


def assignment(index: int) -> tuple[Family, int]:
    """Task `index`'s family and true model: families in turn, and each family's true models in turn (design 4.4)."""
    family = FAMILIES[index % len(FAMILIES)]
    return family, (index // len(FAMILIES)) % 3


def draw(family: Family, truth: int, band: str, rng: np.random.Generator) -> dict[str, Any] | None:
    """One draw of data from the true model; None when it is discarded (design 4.2, 4.3)."""
    params = family.sample(rng, truth)
    clean = family.models[truth].f(family.x, *params)
    sigma = float(f"{rng.uniform(0.02, 0.10) * float(np.max(clean)):.3g}")
    y = round3(clean + rng.normal(0.0, sigma, size=np.shape(clean)))
    if np.any(y < 0):
        return None
    fits = posteriors(family, y, sigma)
    if fits is None or band_of(fits[truth]["posterior"]) != band:
        return None
    return {"params": [float(v) for v in params], "sigma": sigma, "y": y, "fits": fits}


def _number(v: float) -> str:
    return f"{v:.3g}"


def question(family: Family, y: np.ndarray, sigma: float, order: list[str]) -> str:
    formulas = {m.name: m.formula for m in family.models}
    xs = family.x if family.x.ndim == 2 else family.x[None, :]
    rows = ["| " + " | ".join(family.columns) + " |", "|" + " --- |" * len(family.columns)]
    rows += ["| " + " | ".join([*(_number(x[j]) for x in xs), _number(y[j])]) + " |" for j in range(len(y))]
    lines = [f"{family.context} Measurement error is Gaussian with SD {_number(sigma)} {family.unit}.", "Data:", *rows,
             "Candidate models (parameters unknown, all positive):", *(f"- {name}: {formulas[name]}" for name in order),
             "Which candidate model most likely generated these data? Rank the candidates, and give the features of "
             "the data that decide it, the key evidence, and one further measurement that would best confirm the "
             "top pick."]
    return "\n".join(lines)


def make_task(set_name: str, index: int, band: str) -> dict[str, Any]:
    """Task `index` of the set: its task file body, gold entry and generation record (design 4.2–4.4)."""
    family, truth = assignment(index)
    rng = _rng(set_name, index)
    task_id = f"{set_name}-{index + 1:02d}"
    for tries in range(1, MAX_TRIES + 1):
        drawn = draw(family, truth, band, rng)
        if drawn is not None:
            break
    else:
        raise SynthError(f"{task_id}: no {family.key} data with the true model's posterior in band {band!r} "
                         f"after {MAX_TRIES} draws")
    names = [m.name for m in family.models]
    order = shuffled(names, task_id)
    body = {"id": task_id, "question": question(family, drawn["y"], drawn["sigma"], order), "candidates": order,
            "category": "analytical", "data_sensitivity": "public"}
    gold = {"approved": [names[truth]], "failed": sorted(n for i, n in enumerate(names) if i != truth)}
    record = {"family": family.key, "truth": names[truth], "params": dict(zip(family.params, drawn["params"])),
              "sigma": drawn["sigma"], "tries": tries, "fits": drawn["fits"]}
    return {"task": body, "gold": gold, "record": record}
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: `39 passed`

Run: `python -m pytest -q`
Expected: `409 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/synth.py tests/test_gold_synth.py
git commit -m "Draw a synthetic task whose data support the true model

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 과제, 정답, 생성 기록 파일 쓰기

**Files:**
- Modify: `src/reasonlineage/gold/synth.py` (import 블록, 파일 끝)
- Modify: `tests/test_gold_synth.py` (import 블록, 끝에 더하기)

**Interfaces:**
- Consumes:
  - Task 3의 `make_task`, `SynthError`
  - Task 2의 `BANDS`
  - `reasonlineage.engine.config.load_task`
  - `reasonlineage.diagnose.gold.correctness`
- Produces: `build(set_name, band, count, tasks_dir, gold_dir) -> list[Path]`
  - `tasks_dir/<SET>-NN.json`, `gold_dir/gold.json`, `gold_dir/generation.json`를 쓴다.
  - 모르는 구간, 이번에 만들지 않는 과제 파일, 채울 수 없는 구간이면 `SynthError`를 내고 아무것도 쓰지 않는다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_synth.py`의 import 블록을 다음으로 바꾼다.

```python
import json
from collections import Counter

import numpy as np
import pytest

pytest.importorskip("scipy")  # the gold extra; the base suite runs without it (design 8)

from reasonlineage.diagnose.gold import correctness  # noqa: E402
from reasonlineage.engine.config import load_task  # noqa: E402
from reasonlineage.gold import synth  # noqa: E402
```

파일 끝에 더한다.

```python
def test_build_writes_loadable_tasks_the_gold_file_and_the_generation_record(tmp_path):
    paths = synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    assert [p.name for p in paths] == ["synth-test-01.json", "synth-test-02.json"]
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text())
    record = json.loads((tmp_path / "gold" / "generation.json").read_text())
    assert gold["source"] == record["source"] == {"generator": "reasonlineage.gold.synth", "set": "synth-test", "band": "easy"}
    for path in paths:
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}  # what score_run checks
        assert correctness([*truth["approved"], *truth["failed"]], truth) == 1.0
        assert record["tasks"][task.id]["truth"] == truth["approved"][0]
    assert record["tasks"]["synth-test-02"]["family"] == "enzyme"


def test_build_refuses_files_it_does_not_make_and_writes_nothing(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "synth-test-03.json").write_text("{}")
    with pytest.raises(synth.SynthError, match="synth-test-03.json is not built by this set"):
        synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    assert not (tmp_path / "gold").exists()


def test_build_refuses_an_unknown_band(tmp_path):
    with pytest.raises(synth.SynthError, match="unknown band 'medium-hard'"):
        synth.build("synth-test", "medium-hard", 2, tmp_path / "tasks", tmp_path / "gold")


def test_building_the_same_set_again_gives_the_same_bytes(tmp_path):
    synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    before = {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]}
    synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    after = {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]}
    assert after == before


def test_the_symbols_in_a_question_survive_the_task_file(tmp_path):
    (path, _) = synth.build("synth-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    question = load_task(path).question
    assert "µM" in question and "C²/(EC50² + C²)" in question and "Emax·C" in question
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: FAIL, `5 failed, 39 passed`, `AttributeError: module 'reasonlineage.gold.synth' has no attribute 'build'`

- [ ] **Step 3: 파일 쓰기 구현**

`synth.py`의 import 블록을 다음으로 바꾼다.

```python
import hashlib
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .build import shuffled
```

파일 끝에 더한다.

```python
def build(set_name: str, band: str, count: int, tasks_dir: str | Path, gold_dir: str | Path) -> list[Path]:
    """Write `count` task files, gold.json and generation.json; nothing is written if a task cannot be made
    or the task folder holds files this build does not make (design 4.4, 7)."""
    if band not in BANDS:
        raise SynthError(f"unknown band {band!r}; use one of {sorted(BANDS)}")
    tasks_dir, gold_dir = Path(tasks_dir), Path(gold_dir)
    ids = [f"{set_name}-{i + 1:02d}" for i in range(count)]
    stale = [f"{path} is not built by this set; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise SynthError("; ".join(stale))
    made = [make_task(set_name, i, band) for i in range(count)]
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in made:
        path = tasks_dir / f"{task['task']['id']}.json"
        path.write_text(json.dumps(task["task"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    source = {"generator": "reasonlineage.gold.synth", "set": set_name, "band": band}
    gold = {"source": source, "tasks": {t["task"]["id"]: t["gold"] for t in made}}
    generation = {"source": source, "tasks": {t["task"]["id"]: t["record"] for t in made}}
    for name, body in (("gold.json", gold), ("generation.json", generation)):
        (gold_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_synth.py`
Expected: `44 passed`

Run: `python -m pytest -q`
Expected: `414 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/synth.py tests/test_gold_synth.py
git commit -m "Write the synthetic set's task, gold and generation files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 만들기 스크립트

**Files:**
- Create: `scripts/build_synth.py` (실행 권한)
- Create: `tests/test_build_synth_script.py`

**Interfaces:**
- Consumes: Task 4의 `synth.build`, `synth.SynthError`
- Produces: `python scripts/build_synth.py SET --band easy|medium|hard --tasks N [--tasks-dir DIR] [--gold-dir DIR]`
  - 기본 폴더는 `tasks/SET`, `gold/SET`이다.
  - 종료 코드: 성공 0, 만들 수 없거나 numpy/scipy가 없으면 1, 인자 오류 2.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_build_synth_script.py`를 만든다.

```python
"""The synthetic set build script (gold synth design 3, 7)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_synth.py"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=env)


def test_the_script_builds_a_set(tmp_path):
    pytest.importorskip("scipy")
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""  # no fit warnings
    assert sorted(p.name for p in (tmp_path / "tasks").iterdir()) == ["synth-test-01.json", "synth-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold").iterdir()) == ["generation.json", "gold.json"]


@pytest.mark.parametrize("args, message", [
    (("synth-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("Synth_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("synth-test", "--band", "easy", "--tasks", 0), "--tasks must be at least 1"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    result = run(*args, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_without_scipy_the_script_says_how_to_install_it(tmp_path):
    fake = tmp_path / "fake" / "scipy"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("raise ImportError('No module named scipy')\n")
    env = os.environ | {"PYTHONPATH": str(tmp_path / "fake")}
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", env=env)
    assert result.returncode == 1 and "pip install -e '.[gold]'" in result.stderr


def test_a_stale_task_file_stops_the_build(tmp_path):
    pytest.importorskip("scipy")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "synth-test-09.json").write_text("{}")
    result = run("synth-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 1 and "cannot build synth-test: " in result.stderr and "synth-test-09.json" in result.stderr
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_build_synth_script.py`
Expected: FAIL, `6 failed`, `can't open file '…/scripts/build_synth.py'`

- [ ] **Step 3: 스크립트 쓰기**

`scripts/build_synth.py`를 만들고 `chmod +x scripts/build_synth.py`로 실행 권한을 준다.

```python
#!/usr/bin/env python3
"""Build a synthetic hidden-law gold set (gold synth design 3, 4).

    python scripts/build_synth.py SET --band easy|medium|hard --tasks N
    # tasks/SET/*.json, gold/SET/gold.json and gold/SET/generation.json
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

BANDS = ("easy", "medium", "hard")  # synth.BANDS; listed here so a wrong argument fails before numpy loads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("set", help="set name, e.g. synth-calib-easy or synth-v1")
    parser.add_argument("--band", required=True, choices=BANDS, help="the true model's posterior band")
    parser.add_argument("--tasks", required=True, type=int, help="number of tasks")
    parser.add_argument("--tasks-dir", type=Path, help="default: tasks/SET")
    parser.add_argument("--gold-dir", type=Path, help="default: gold/SET")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.set):
        parser.error("the set name takes lowercase letters, digits and single hyphens, e.g. synth-v1")
    if args.tasks < 1:
        parser.error("--tasks must be at least 1")
    try:
        from reasonlineage.gold import synth
    except ImportError as exc:
        print(f"building a synthetic set needs numpy and scipy ({exc}); install them with: pip install -e '.[gold]'",
              file=sys.stderr)
        return 1
    tasks_dir = args.tasks_dir or ROOT / "tasks" / args.set
    gold_dir = args.gold_dir or ROOT / "gold" / args.set
    try:
        written = synth.build(args.set, args.band, args.tasks, tasks_dir, gold_dir)
    except synth.SynthError as exc:
        print(f"cannot build {args.set}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {tasks_dir}; gold.json and generation.json in {gold_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_build_synth_script.py`
Expected: `6 passed`

Run: `python -m pytest -q`
Expected: `420 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add scripts/build_synth.py tests/test_build_synth_script.py
git commit -m "Add the script that builds a synthetic gold set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 보정 세트 만들기 (모델 호출 없음)

**Files:**
- Create: `tasks/synth-calib-{easy,medium,hard}/*.json`
- Create: `gold/synth-calib-{easy,medium,hard}/gold.json`, `generation.json`

**Interfaces:**
- Consumes: Task 5의 `scripts/build_synth.py`
- Produces: Task 7이 돌리는 세 세트. 각 세트는 2과제다. `-01`은 용량-반응(정답: 쌍곡선 Emax), `-02`는 효소 억제(정답: 경쟁적)다.

- [ ] **Step 1: 세 세트 만들기**

```bash
for b in easy medium hard; do python scripts/build_synth.py synth-calib-$b --band $b --tasks 2; done
```

Expected: 세 줄 모두 `2 task files in …/tasks/synth-calib-<구간>; gold.json and generation.json in …/gold/synth-calib-<구간>`

- [ ] **Step 2: 정답 사후확률이 구간 안에 있는지 확인**

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "src")
from reasonlineage.gold import synth
for b in ("easy", "medium", "hard"):
    record = json.load(open(f"gold/synth-calib-{b}/generation.json"))
    for tid, t in record["tasks"].items():
        p = next(f["posterior"] for f in t["fits"] if f["model"] == t["truth"])
        assert synth.band_of(p) == b, (tid, p)
        print(tid, t["family"], t["truth"], round(p, 4), "tries", t["tries"])
PY
```

Expected: 과제 6줄이 나오고 assert 오류가 없다. 계열은 세트마다 `dose`, `enzyme`이다.

- [ ] **Step 3: 다시 만들어도 같은지 확인**

```bash
git add tasks/synth-calib-* gold/synth-calib-*
for b in easy medium hard; do python scripts/build_synth.py synth-calib-$b --band $b --tasks 2; done
git diff --exit-code --stat -- tasks gold && echo same
```

Expected: 마지막 줄이 `same`이다(다시 만든 파일이 스테이징한 파일과 같다).

- [ ] **Step 4: 커밋**

```bash
git commit -m "Add the three calibration sets of the synthetic gold set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 보정 실행과 구간 고르기 (모델 호출: 사용자에게 먼저 묻는다)

**Files:**
- 커밋하는 파일 없음. 출력은 git이 무시하는 `runs/gold-synth-calib-<구간>/`에 남는다.

**Interfaces:**
- Consumes: Task 6의 세 세트, `scripts/run_gold.sh`
- Produces: 고른 구간 하나(`easy`, `medium`, `hard`) 또는 "멈춤". Task 8이 쓴다.

- [ ] **Step 1: 사용자에게 묻기**

다음을 알리고 승인을 받는다: 6과제, 모델 호출 약 96회와 J1 점검(jev) 24회, 약 40분. 승인이 없으면 여기서 멈춘다.

- [ ] **Step 2: 세 세트 돌리기**

```bash
for b in easy medium hard; do scripts/run_gold.sh synth-calib-$b || break; done
```

Expected: 세트마다 마지막에 `reasonlineage gold` 요약이 나오고, `runs/gold-synth-calib-<구간>/report.json`이 생긴다.
- 실행 하나가 중간에 멈추면 스크립트가 `resume` 방법을 알린다. 그대로 이어 돌린 뒤 같은 명령을 다시 돌린다. 끝난 과제는 건너뛴다.

- [ ] **Step 3: 규칙대로 구간 고르기**

```bash
python - <<'PY'
import json
order = ["easy", "medium", "hard"]
share = {b: json.load(open(f"runs/gold-synth-calib-{b}/report.json"))["level1"]["share_correct"] for b in order}
ok = [b for b in order if 0.375 <= share[b] <= 0.75]
pick = min(ok, key=lambda b: (abs(share[b] - 0.6), -order.index(b))) if ok else None
print(share, "->", pick or "stop: no band in 0.375-0.75")
PY
```

Expected: 구간별 비율과 고른 구간이 한 줄로 나온다.

- [ ] **Step 4: 보고하기**

사용자에게 한 줄 결론으로 시작해서 알린다(예: "medium을 골랐어요. 정답 비율 easy 1.0, medium 0.62, hard 0.38").
- 고른 구간이 없으면 멈추고, 측정점 수, σ 범위, 후보 조합 중 무엇을 바꿀지 묻는다(설계 5.1).
- 진행 기록에 세 비율과 고른 구간을 적는다.

---

### Task 8: 본 세트 만들기와 1단계 실행 (모델 호출: 사용자에게 먼저 묻는다)

**Files:**
- Create: `tasks/synth-v1/*.json`, `gold/synth-v1/gold.json`, `gold/synth-v1/generation.json`

**Interfaces:**
- Consumes: Task 7의 고른 구간 `BAND`, `scripts/build_synth.py`, `scripts/run_gold.sh`
- Produces: `runs/gold-synth-v1/report.json`의 1단계 판정

- [ ] **Step 1: 본 세트 만들기**

```bash
BAND=<Task 7에서 고른 구간>
python scripts/build_synth.py synth-v1 --band "$BAND" --tasks 10
```

Expected: `10 task files in …/tasks/synth-v1; gold.json and generation.json in …/gold/synth-v1`

- [ ] **Step 2: 확인하고 커밋하기**

```bash
python - <<'PY'
import json, sys
from collections import Counter
sys.path.insert(0, "src")
from reasonlineage.gold import synth
record = json.load(open("gold/synth-v1/generation.json"))
band = record["source"]["band"]
for tid, t in record["tasks"].items():
    p = next(f["posterior"] for f in t["fits"] if f["model"] == t["truth"])
    assert synth.band_of(p) == band, (tid, p)
print(band, Counter(t["family"] for t in record["tasks"].values()))
PY
git add tasks/synth-v1 gold/synth-v1
git commit -m "Add the synthetic gold set v1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `<구간> Counter({'dose': 3, 'enzyme': 3, 'growth': 2, 'elimination': 2})`

- [ ] **Step 3: 사용자에게 묻기**

다음을 알리고 승인을 받는다: 10과제, 모델 호출 약 160회와 J1 점검(jev) 40회, 약 70분. 승인이 없으면 여기서 멈춘다.

- [ ] **Step 4: 1단계 실행**

```bash
scripts/run_gold.sh synth-v1
python -c "import json; l=json.load(open('runs/gold-synth-v1/report.json'))['level1']; print(l['verdict'], l['share_correct'], l['pairs'], l['concordance'], l['by_model'])"
```

Expected: 판정 하나(`signal`, `no signal`, `hold: ceiling`, `hold: too few pairs`)와 그 수치가 나온다.

- [ ] **Step 5: 보고하기**

사용자에게 한 줄 결론으로 시작해서 알린다(예: "신호 있음: 적합도가 정답을 따라갔어요(일치도 0.78, 쌍 24개)").
- 이어서 판정의 근거 수치를 한두 줄로 적는다.
- `signal`이면 2단계 기준을 먼저 정하자고 제안한다(설계 6). 그 밖의 판정이면 무엇을 뜻하는지 한 줄로 적는다.
- 판정 기준과 구간은 바꾸지 않는다.
