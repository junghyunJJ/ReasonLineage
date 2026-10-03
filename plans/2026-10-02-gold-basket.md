# 장바구니 정답지 (B2 세트) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코드로 만든 장바구니 과제(마트 세 곳 중 실결제액이 싼 순서)로 1단계를 재고 분석 보고서를 낸다. 누구나 영수증으로 검산할 수 있는 과제라서, 지금까지의 연구 자료 세트와 달리 사용자가 직접 정답을 확인할 수 있다.

**Architecture:**
- 새 모듈 `src/reasonlineage/gold/basket.py` 하나가 품목·규칙 뽑기, 실결제액 계산, 오독 시뮬레이션, 구간 거르기, 과제·정답·영수증 파일을 맡는다.
- 난이도는 계산량이 아니라 **규칙 해석**으로 만든다. 그럴듯한 오독 6개를 코드가 모두 계산해 보고, 1위를 바꾸는 오독이 정해진 수 이상인 과제만 남긴다. 합성 법칙 세트는 모델이 계산을 정확히 해내서 천장에 걸렸다.
- 스크립트 `scripts/build_basket.py`가 세트를 만들고, 실행과 판정은 기존 `scripts/run_gold.sh`와 `reasonlineage gold --analysis`를 그대로 쓴다.
- **새 파일만 추가한다.** 기존 코드를 건드리지 않으므로 다른 세트의 실행 중에도 안전하다.

**Tech Stack:** Python 3.11 이상, 표준 라이브러리만(hashlib, json, random), pytest.

**Spec:** `specs/2026-10-02-gold-basket-design.md` (판정 규칙은 `specs/2026-09-30-gold-dev-design.md` 6.1–6.2)

**미리 확인한 것 (2026-10-02):**
- 코드를 임시 복사본에서 모두 짜고 돌려 봤다. 세 구간이 모두 빠르게 채워진다. 과제당 중앙값 시도 횟수는 easy 12, medium 43, hard 116이고 시간은 6–65 ms다.
- 생성한 과제를 읽어 보고 두 가지를 고쳤다.
  - 쿠폰이 없는 마트가 "쿠폰 차감 후"를 기준으로 말하는 어색한 문구가 나왔다. 그래서 무료배송 기준 시점은 그 마트가 실제로 가진 단계만 쓰게 했다.
  - 어떤 마트의 실결제액이 프롬프트에 적힌 숫자(기준 금액)와 우연히 같은 경우가 있었다. 그런 뽑기는 버린다. 정답과 같은 숫자가 프롬프트에 보이지 않는다.
- `gold-basket` 브랜치의 새 복사본에 Task 1–5를 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED는 아래 Expected처럼 실패했고 GREEN은 통과했다. 전체 테스트는 525 → 535 → 539 → 547 → 552 passed, 3 deselected다.

## Global Constraints

**작업 환경**
- Python 3.11 이상. 엔진의 `dependencies = []`는 그대로 두고, 새 코드는 표준 라이브러리만 쓴다.
- 작업은 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 브랜치 `gold-basket`(`gold-biorxiv` 위)에서 한다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령은 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`를 붙인다.

**보안과 개인정보**
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다.
- 사용자의 이메일이나 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다.

**실행과 멈춤**
- 실행(모델 호출)은 미리 승인받았다. 멈춰 묻는 곳은 두 곳이다: 보정 규칙에 걸릴 때(Task 6 Step 4)와 본 세트를 돌리기 전 과제 하나를 보여 줄 때(Task 7 Step 2, 확인만 받는다).
- **다른 세트의 실행이 돌고 있으면 기다린다.** 같은 CLI를 동시에 쓰면 서로 느려지고, 측정 중인 실행이 더 중요하다. `pgrep -f "reasonlineage (run|resume)"`로 확인한다.
- 긴 실행은 `setsid nohup`으로 분리해서 돌린다. 백그라운드 작업은 2시간에 끊긴다.
- 멈춘 실행은 5분 뒤 이어 돌리고, 최대 3번까지만 한다.
- 제공자가 거부하면 과제를 버리기 전에 이미 정상으로 돌아간 과제로 대조 확인부터 한다.

**고정한 값**
- 구간은 1~2위 금액 차이와 1위를 바꾸는 오독 수로 정한다: easy(3% 이상, 1개 이상), medium(1~3%, 2개 이상), hard(0.2~1%, 3개 이상).
- 1~2위 차이는 항상 1위 금액의 0.2% 이상이다. 운으로 갈리는 과제를 막는다.
- 보정 구간 고르기(실행 전에 고정): 정답 비율이 0.375–0.75인 구간 중 0.6에 가장 가까운 구간. 같으면 더 어려운 구간. 세 구간이 모두 0.75를 넘거나 모두 0.375 미만이면 멈추고 사용자와 정한다.
- 1단계 판정 기준은 바꾸지 않는다: 천장 80%, 쌍 10개, 일치율 0.70, 적합도 동점 0.5.
- **판정은 세트마다 따로 한다.** 다른 세트와 합친 수치는 보고서의 보조 수치로만 적는다.
- 쌍이 10개에 못 미치면 같은 구간·같은 생성기로 과제 10개를 더 만들어 이어 붙인다(설계 5.2에서 미리 정해 둔 것이다).
- 결과를 본 뒤 구간, 과제, 판정 기준을 바꾸지 않는다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 테스트는 그 코드를 맡은 Task에 들어 있다.
- **프롬프트에 정답과 같은 숫자가 보이면 안 된다.** 기준 금액이 우연히 어떤 마트의 실결제액과 같을 수 있다(Task 3 `test_a_draw_meets_its_band_or_is_discarded`가 쓰는 `printed` 검사, Task 4 `test_a_task_reads_as_a_shopping_question_and_hides_the_answer`).
- **마트가 가지지 않은 단계를 기준으로 말하면 안 된다.** 쿠폰이 없는데 "쿠폰 차감 후"라고 쓰면 읽는 사람이 판단할 수 없다(Task 3 `test_a_store_never_measures_its_threshold_at_a_step_it_does_not_have`).
- **묶음 할인은 수량이 묶음 배수가 아닐 때가 중요하다.** 4개를 2+1로 사면 3개 값이고, 3분의 1 할인과 다르다(Task 2 `test_treating_a_bundle_as_a_percentage_differs_when_the_quantity_is_not_a_full_group`).
- **비율 할인은 배송비에 붙지 않는다.** 붙이면 금액이 달라져 순위가 바뀔 수 있다(Task 1 `test_the_steps_run_bundle_then_coupon_then_percent_then_delivery`, Task 2 `test_a_misreading_can_charge_the_discount_on_delivery`).
- **정답이 한 글자에 쏠리면 안 된다.** 첫 보기를 고르는 경향이 정답률을 부풀린다(Task 4 `test_the_cheapest_store_is_spread_evenly_over_the_letters`).

---

### Task 1: 마트가 청구하는 금액

**Files:**
- Create: `src/reasonlineage/gold/basket.py`
- Create: `tests/test_gold_basket.py`

**Interfaces:**
- Consumes: `reasonlineage.gold.build.shuffled`
- Produces:
  - `BasketError(RuntimeError)`
  - `ITEMS`(품목 12개: 이름, 분류, 기준 가격), `CATEGORIES`, `STORES = ("A", "B", "C")`, `MEASURED`, `BANDS`, `MAX_TRIES`, `QUESTION`
  - `won(amount) -> str`, `category_of(item) -> str`
  - `bundle_paid(quantity, group) -> int`
  - `line_totals(prices, basket, rules, bundle_as_percent=False) -> dict[str, int]`
  - `price(store, basket, misreading=None) -> dict`: `lines`, `goods`, `after_coupon`, `after_discount`, `delivery`, `total`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_basket.py`를 만든다.

```python
"""The generated shopping-basket gold set (basket design 4): prices, misreadings, bands and files."""

import pytest

from reasonlineage.gold import basket as bk

BASKET = {"milk": 3, "eggs": 2, "coffee": 1}
PRICES = {"milk": 2000, "eggs": 7000, "coffee": 10000}


def store(*rules, prices=None):
    return {"prices": dict(prices or PRICES), "rules": list(rules)}


DELIVERY = {"kind": "delivery", "fee": 3000, "free_at": 100000, "measured": "before"}


# --- 4.2 what a store charges ---

@pytest.mark.parametrize("quantity, group, paid", [(3, 3, 2), (4, 3, 3), (6, 3, 4), (2, 2, 1), (3, 2, 2), (1, 3, 1)])
def test_a_bundle_offer_pays_for_all_but_one_unit_of_each_group(quantity, group, paid):
    assert bk.bundle_paid(quantity, group) == paid


def test_the_plain_total_is_the_lines_plus_delivery():
    receipt = bk.price(store(DELIVERY), BASKET)
    assert receipt["goods"] == 3 * 2000 + 2 * 7000 + 10000 == 30000
    assert receipt["delivery"] == 3000 and receipt["total"] == 33000


def test_the_steps_run_bundle_then_coupon_then_percent_then_delivery():
    receipt = bk.price(store({"kind": "bundle", "item": "milk", "group": 3},
                             {"kind": "coupon", "category": "dairy", "threshold": 18000, "amount": 4000},
                             {"kind": "percent", "rate": 10, "threshold": None}, DELIVERY), BASKET)
    assert receipt["lines"]["milk"] == 4000  # 3 for the price of 2
    assert receipt["goods"] == 4000 + 14000 + 10000 == 28000
    assert receipt["after_coupon"] == 24000  # dairy lines 18000 >= 18000
    assert receipt["after_discount"] == 21600  # 10% off, never on delivery
    assert receipt["total"] == 24600


def test_a_coupon_whose_category_falls_short_is_not_taken():
    receipt = bk.price(store({"kind": "coupon", "category": "dairy", "threshold": 20001, "amount": 4000}, DELIVERY),
                       BASKET)
    assert receipt["after_coupon"] == receipt["goods"] == 30000


def test_a_percentage_with_a_threshold_waits_for_it():
    rule = {"kind": "percent", "rate": 5, "threshold": 30001}
    assert bk.price(store(rule, DELIVERY), BASKET)["after_discount"] == 30000
    rule = {"kind": "percent", "rate": 5, "threshold": 30000}
    assert bk.price(store(rule, DELIVERY), BASKET)["after_discount"] == 28500


@pytest.mark.parametrize("measured, free", [("before", True), ("after_coupon", True), ("after_discount", False)])
def test_where_a_store_measures_its_free_delivery_threshold_decides_the_fee(measured, free):
    rules = (
        {"kind": "coupon", "category": "dairy", "threshold": 18000, "amount": 2000},
        {"kind": "percent", "rate": 20, "threshold": None},
        {"kind": "delivery", "fee": 3000, "free_at": 26000, "measured": measured},
    )
    receipt = bk.price(store(*rules), BASKET)
    assert (receipt["goods"], receipt["after_coupon"], receipt["after_discount"]) == (30000, 28000, 22400)
    assert receipt["delivery"] == (0 if free else 3000)


def test_every_step_is_floored_to_whole_won():
    receipt = bk.price(store({"kind": "percent", "rate": 7, "threshold": None}, DELIVERY), BASKET)
    assert receipt["after_discount"] == 30000 - 2100 == 27900
    receipt = bk.price(store({"kind": "percent", "rate": 3, "threshold": None},
                             {"kind": "delivery", "fee": 0, "free_at": 10 ** 9, "measured": "before"}),
                       {"milk": 1}, )
    assert receipt["after_discount"] == 2000 - 60 == 1940


"""The generated shopping-basket gold set (basket design 4): prices, misreadings, bands and files."""

import json
import random
from collections import Counter

import pytest

from reasonlineage.diagnose.gold import correctness
from reasonlineage.engine.config import load_task
from reasonlineage.gold import basket as bk

BASKET = {"milk": 3, "eggs": 2, "coffee": 1}
PRICES = {"milk": 2000, "eggs": 7000, "coffee": 10000}


def store(*rules, prices=None):
    return {"prices": dict(prices or PRICES), "rules": list(rules)}


DELIVERY = {"kind": "delivery", "fee": 3000, "free_at": 100000, "measured": "before"}


# --- 4.2 what a store charges ---

@pytest.mark.parametrize("quantity, group, paid", [(3, 3, 2), (4, 3, 3), (6, 3, 4), (2, 2, 1), (3, 2, 2), (1, 3, 1)])
def test_a_bundle_offer_pays_for_all_but_one_unit_of_each_group(quantity, group, paid):
    assert bk.bundle_paid(quantity, group) == paid


def test_the_plain_total_is_the_lines_plus_delivery():
    receipt = bk.price(store(DELIVERY), BASKET)
    assert receipt["goods"] == 3 * 2000 + 2 * 7000 + 10000 == 30000
    assert receipt["delivery"] == 3000 and receipt["total"] == 33000


def test_the_steps_run_bundle_then_coupon_then_percent_then_delivery():
    receipt = bk.price(store({"kind": "bundle", "item": "milk", "group": 3},
                             {"kind": "coupon", "category": "dairy", "threshold": 18000, "amount": 4000},
                             {"kind": "percent", "rate": 10, "threshold": None}, DELIVERY), BASKET)
    assert receipt["lines"]["milk"] == 4000  # 3 for the price of 2
    assert receipt["goods"] == 4000 + 14000 + 10000 == 28000
    assert receipt["after_coupon"] == 24000  # dairy lines 18000 >= 18000
    assert receipt["after_discount"] == 21600  # 10% off, never on delivery
    assert receipt["total"] == 24600


def test_a_coupon_whose_category_falls_short_is_not_taken():
    receipt = bk.price(store({"kind": "coupon", "category": "dairy", "threshold": 20001, "amount": 4000}, DELIVERY),
                       BASKET)
    assert receipt["after_coupon"] == receipt["goods"] == 30000


def test_a_percentage_with_a_threshold_waits_for_it():
    rule = {"kind": "percent", "rate": 5, "threshold": 30001}
    assert bk.price(store(rule, DELIVERY), BASKET)["after_discount"] == 30000
    rule = {"kind": "percent", "rate": 5, "threshold": 30000}
    assert bk.price(store(rule, DELIVERY), BASKET)["after_discount"] == 28500


@pytest.mark.parametrize("measured, free", [("before", True), ("after_coupon", True), ("after_discount", False)])
def test_where_a_store_measures_its_free_delivery_threshold_decides_the_fee(measured, free):
    rules = (
        {"kind": "coupon", "category": "dairy", "threshold": 18000, "amount": 2000},
        {"kind": "percent", "rate": 20, "threshold": None},
        {"kind": "delivery", "fee": 3000, "free_at": 26000, "measured": measured},
    )
    receipt = bk.price(store(*rules), BASKET)
    assert (receipt["goods"], receipt["after_coupon"], receipt["after_discount"]) == (30000, 28000, 22400)
    assert receipt["delivery"] == (0 if free else 3000)


def test_every_step_is_floored_to_whole_won():
    receipt = bk.price(store({"kind": "percent", "rate": 7, "threshold": None}, DELIVERY), BASKET)
    assert receipt["after_discount"] == 30000 - 2100 == 27900
    receipt = bk.price(store({"kind": "percent", "rate": 3, "threshold": None},
                             {"kind": "delivery", "fee": 0, "free_at": 10 ** 9, "measured": "before"}),
                       {"milk": 1}, )
    assert receipt["after_discount"] == 2000 - 60 == 1940
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: FAIL, `ImportError: cannot import name 'basket' from 'reasonlineage.gold'` (1 error)

- [ ] **Step 3: 모듈 쓰기**

`src/reasonlineage/gold/basket.py`를 만든다.

```python
"""Generated shopping-basket gold set (basket design 4).

Each task gives one shopping list and three stores with their own unit prices and promotions, and asks which store
charges least. The tasks are generated, so the answer exists nowhere and cannot be recalled. What makes a task hard
is not the arithmetic but the promotions: a task is kept only when plausible misreadings of the rules change which
store wins, so a wrong answer comes from reading a rule wrongly rather than from bad luck (design 4.3).
"""

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

from .build import shuffled


class BasketError(RuntimeError):
    """A set could not be built: a band could not be filled, or the task folder holds files it does not build."""


# name, category, base price in won (multiples of 100)
ITEMS: tuple[tuple[str, str, int], ...] = (
    ("milk", "dairy", 2400), ("eggs", "dairy", 6800), ("yogurt", "dairy", 4200), ("cheese", "dairy", 7500),
    ("bananas", "fresh", 1100), ("apples", "fresh", 5600), ("lettuce", "fresh", 2900),
    ("coffee", "pantry", 12500), ("pasta", "pantry", 2200), ("rice", "pantry", 18000),
    ("detergent", "household", 9900), ("toothpaste", "household", 3600),
)
CATEGORIES = ("dairy", "fresh", "pantry", "household")
STORES = ("A", "B", "C")
MEASURED = ("before", "after_coupon", "after_discount")  # when a store measures its free-delivery threshold
BANDS: dict[str, tuple[float, float, int]] = {  # (low margin, high margin, misreadings that must flip the winner)
    "easy": (0.03, 1.0, 1), "medium": (0.01, 0.03, 2), "hard": (0.002, 0.01, 3),
}
MAX_TRIES = 2000
QUESTION = (
    "You are buying the same shopping list from three online stores. Each store has its own unit prices and "
    "promotions. You have no tools: do the arithmetic in your own reasoning.\n\n"
    "Shopping list: {list}\n\n{stores}\n"
    "Which store charges the least in total, including delivery? Rank the three stores from cheapest to most "
    "expensive, and give the steps that decide the order, the key comparison, and one check that would confirm "
    "your top pick.")


def won(amount: int) -> str:
    return f"{amount:,}"


# --- 4.2 the rules ---

def bundle_paid(quantity: int, group: int) -> int:
    """Units paid for under a `group`-for-(group-1) offer: 3 for 2 is group 3, 2 for 1 is group 2."""
    return quantity - quantity // group


def line_totals(prices: Mapping[str, int], basket: Mapping[str, int], rules: Sequence[Mapping[str, Any]],
                bundle_as_percent: bool = False) -> dict[str, int]:
    """Each item's line total after the store's bundle offers.

    `bundle_as_percent` is the misreading that treats 3-for-2 as a third off the line instead of one free unit.
    """
    bundles = {rule["item"]: rule["group"] for rule in rules if rule["kind"] == "bundle"}
    lines = {}
    for item, quantity in basket.items():
        group = bundles.get(item)
        if group is None:
            lines[item] = prices[item] * quantity
        elif bundle_as_percent:
            lines[item] = (prices[item] * quantity * (group - 1)) // group
        else:
            lines[item] = prices[item] * bundle_paid(quantity, group)
    return lines


def price(store: Mapping[str, Any], basket: Mapping[str, int], misreading: str | None = None) -> dict[str, Any]:
    """What the store charges for the basket, step by step (design 4.2); `misreading` applies one of design 4.3's.

    Steps: bundle offers, then the category coupon, then the percentage discount, then delivery. The percentage
    never applies to delivery, and every step is floored to whole won.
    """
    rules = store["rules"]
    lines = line_totals(store["prices"], basket, rules, bundle_as_percent=misreading == "bundle_as_percent")
    goods = sum(lines.values())
    coupon = next((r for r in rules if r["kind"] == "coupon"), None)
    percent = next((r for r in rules if r["kind"] == "percent"), None)
    delivery = next(r for r in rules if r["kind"] == "delivery")

    def apply_coupon(amount: int) -> int:
        if coupon is None:
            return amount
        in_category = sum(v for item, v in lines.items() if category_of(item) == coupon["category"])
        return max(amount - coupon["amount"], 0) if in_category >= coupon["threshold"] else amount

    def apply_percent(amount: int) -> int:
        if percent is None:
            return amount
        if percent["threshold"] is not None and amount < percent["threshold"]:
            return amount
        return amount - amount * percent["rate"] // 100

    if misreading == "percent_before_coupon":
        after_coupon = apply_percent(goods)
        after_discount = apply_coupon(after_coupon)
    else:
        after_coupon = apply_coupon(goods)
        after_discount = apply_percent(after_coupon)
    measured = {"before": goods, "after_coupon": after_coupon, "after_discount": after_discount}
    where = delivery["measured"]
    if misreading == "delivery_after_discount":
        where = "after_discount"
    elif misreading == "delivery_before":
        where = "before"
    fee = 0 if measured[where] >= delivery["free_at"] else delivery["fee"]
    if misreading == "no_delivery":
        fee = 0
    total = apply_percent(after_coupon + fee) if misreading == "percent_on_delivery" else after_discount + fee
    return {"lines": lines, "goods": goods, "after_coupon": after_coupon, "after_discount": after_discount,
            "delivery": fee, "total": total}


def category_of(item: str) -> str:
    return next(category for name, category, _ in ITEMS if name == item)
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: `14 passed`

Run: `python -m pytest -q`
Expected: `525 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/basket.py tests/test_gold_basket.py
git commit -m "Price a basket at a store: bundles, then the coupon, then the percentage, then delivery

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: 오독이 승자를 바꾸는가

**Files:**
- Modify: `src/reasonlineage/gold/basket.py` (파일 끝)
- Modify: `tests/test_gold_basket.py` (파일 끝)

**Interfaces:**
- Consumes: Task 1의 `price`
- Produces:
  - `MISREADINGS`: (이름, 설명) 6개
  - `winner(stores, basket, misreading=None) -> int`
  - `flipping(stores, basket) -> list[str]`: 1위를 바꾸는 오독들
  - `margin(stores, basket) -> float`: 2위가 1위보다 더 내는 비율

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_basket.py` 끝에 더한다.

```python
# --- 4.3 the misreadings ---

MISREAD_RULES = (
    {"kind": "bundle", "item": "milk", "group": 3},
    {"kind": "coupon", "category": "dairy", "threshold": 18000, "amount": 4000},
    {"kind": "percent", "rate": 10, "threshold": None},
    {"kind": "delivery", "fee": 3000, "free_at": 26000, "measured": "before"},
)


@pytest.mark.parametrize("misreading, total", [
    (None, 21600),  # goods 28000 -> coupon 24000 -> 10% off 21600, delivery free (28000 >= 26000)
    ("delivery_after_discount", 24600),  # 21600 < 26000, so the fee is charged
    ("delivery_before", 21600),  # already measured there
    ("percent_before_coupon", 21200),  # 10% off 28000 = 25200, then -4000
    ("bundle_as_percent", 21600),  # milk line 4000 either way for 3 units
    ("no_delivery", 21600),
    ("percent_on_delivery", 21600),  # delivery is free here, so there is nothing to discount
])
def test_each_misreading_changes_the_total_the_way_it_says(misreading, total):
    assert bk.price(store(*MISREAD_RULES), BASKET, misreading)["total"] == total


def test_a_misreading_can_charge_the_discount_on_delivery():
    rules = (*MISREAD_RULES[:3], {"kind": "delivery", "fee": 5000, "free_at": 10 ** 9, "measured": "before"})
    plain = bk.price(store(*rules), BASKET)
    assert plain["total"] == 21600 + 5000
    assert bk.price(store(*rules), BASKET, "percent_on_delivery")["total"] == (24000 + 5000) * 90 // 100


def test_treating_a_bundle_as_a_percentage_differs_when_the_quantity_is_not_a_full_group():
    basket = {"milk": 4}
    rules = (({"kind": "bundle", "item": "milk", "group": 3}),
             {"kind": "delivery", "fee": 0, "free_at": 10 ** 9, "measured": "before"})
    assert bk.price(store(*rules), basket)["goods"] == 3 * 2000
    assert bk.price(store(*rules), basket, "bundle_as_percent")["goods"] == 8000 * 2 // 3


def test_the_flipping_misreadings_are_the_ones_that_change_the_winner():
    # The cheapest store's fee is free on the goods total (30,000) but not on the discounted amount (27,000).
    cheap = store({"kind": "percent", "rate": 10, "threshold": None},
                  {"kind": "delivery", "fee": 9000, "free_at": 28000, "measured": "before"})
    dear = store({"kind": "delivery", "fee": 0, "free_at": 10 ** 9, "measured": "before"},
                 prices={"milk": 2100, "eggs": 7000, "coffee": 10000})
    third = store({"kind": "delivery", "fee": 0, "free_at": 10 ** 9, "measured": "before"},
                  prices={"milk": 3000, "eggs": 9000, "coffee": 12000})
    stores = [cheap, dear, third]
    assert bk.winner(stores, BASKET) == 0 and bk.winner(stores, BASKET, "percent_on_delivery") == 0
    assert bk.winner(stores, BASKET, "no_delivery") == 0
    assert "delivery_after_discount" in bk.flipping(stores, BASKET)  # the fee returns and store B wins
    assert bk.margin(stores, BASKET) == pytest.approx((30300 - 27000) / 27000)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: FAIL, `1 failed, 23 passed`, `AttributeError: module 'reasonlineage.gold.basket' has no attribute 'winner'`

- [ ] **Step 3: 코드 쓰기**

`basket.py` 끝에 더한다.

```python
# --- 4.3 the misreadings ---

MISREADINGS: tuple[tuple[str, str], ...] = (
    ("delivery_after_discount", "reads every free-delivery threshold as measured after the discounts"),
    ("delivery_before", "reads every free-delivery threshold as measured on the goods total"),
    ("percent_before_coupon", "applies the percentage discount before the coupon"),
    ("bundle_as_percent", "treats 3-for-2 as a third off the line instead of one free unit"),
    ("no_delivery", "leaves the delivery fee out"),
    ("percent_on_delivery", "applies the percentage discount to the delivery fee too"),
)


def winner(stores: Sequence[Mapping[str, Any]], basket: Mapping[str, int], misreading: str | None = None) -> int:
    totals = [price(store, basket, misreading)["total"] for store in stores]
    return totals.index(min(totals))


def flipping(stores: Sequence[Mapping[str, Any]], basket: Mapping[str, int]) -> list[str]:
    """The misreadings that change which store wins."""
    true_winner = winner(stores, basket)
    return [name for name, _ in MISREADINGS if winner(stores, basket, name) != true_winner]


def margin(stores: Sequence[Mapping[str, Any]], basket: Mapping[str, int]) -> float:
    """How much more the second-cheapest store charges, as a share of the cheapest."""
    first, second, _ = sorted(price(store, basket)["total"] for store in stores)
    return (second - first) / first
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: `24 passed`

Run: `python -m pytest -q`
Expected: `535 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/basket.py tests/test_gold_basket.py
git commit -m "Count the misreadings of the rules that change which store wins

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 과제 뽑기와 구간 거르기

**Files:**
- Modify: `src/reasonlineage/gold/basket.py` (파일 끝)
- Modify: `tests/test_gold_basket.py` (import 블록, 파일 끝)

**Interfaces:**
- Consumes: Task 1–2의 함수
- Produces:
  - `draw_basket(rng)`, `draw_prices(rng, basket)`, `draw_rules(rng, basket, prices, measured)`, `draw_stores(rng, basket)`
  - `printed(stores) -> set[int]`: 과제가 보여 주는 모든 금액
  - `draw(band, rng) -> dict | None`: `basket`, `stores`, `receipts`, `margin`, `flipping`, `winner`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_basket.py`의 import 블록(`import pytest`까지)을 다음으로 바꾼다.

```python
"""The generated shopping-basket gold set (basket design 4): prices, misreadings, bands and files."""

import random

import pytest

from reasonlineage.gold import basket as bk
```

파일 끝에 더한다.

```python
# --- 4.3 the bands ---

@pytest.mark.parametrize("band", sorted(bk.BANDS))
def test_a_draw_meets_its_band_or_is_discarded(band):
    low, high, least = bk.BANDS[band]
    rng = random.Random(7)
    kept = 0
    while kept < 10:
        drawn = bk.draw(band, rng)
        if drawn is None:
            continue
        kept += 1
        assert low <= drawn["margin"] < high and len(drawn["flipping"]) >= least
        totals = [receipt["total"] for receipt in drawn["receipts"]]
        assert len(set(totals)) == 3 and totals[drawn["winner"]] == min(totals)
        assert drawn["margin"] >= 0.002  # never decided by luck


def test_a_store_never_measures_its_threshold_at_a_step_it_does_not_have():
    rng = random.Random(11)
    for _ in range(40):
        drawn = bk.draw("medium", rng)
        if drawn is None:
            continue
        for store_ in drawn["stores"]:
            kinds = {rule["kind"] for rule in store_["rules"]}
            delivery = next(rule for rule in store_["rules"] if rule["kind"] == "delivery")
            assert delivery["measured"] != "after_coupon" or "coupon" in kinds
            assert delivery["measured"] != "after_discount" or "percent" in kinds
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: FAIL, `4 failed, 24 passed`, `AttributeError: module 'reasonlineage.gold.basket' has no attribute 'draw'`

- [ ] **Step 3: 코드 쓰기**

`basket.py` 끝에 더한다.

```python
# --- 4.1, 4.2 drawing a task ---

def draw_basket(rng: random.Random) -> dict[str, int]:
    names = [name for name, _, _ in ITEMS]
    chosen = rng.sample(names, rng.randint(4, 8))
    return {item: rng.randint(1, 4) for item in sorted(chosen, key=names.index)}


def draw_prices(rng: random.Random, basket: Mapping[str, int]) -> dict[str, int]:
    base = {name: price for name, _, price in ITEMS}
    return {item: max(100, round(base[item] * rng.uniform(0.85, 1.15) / 100) * 100) for item in basket}


def draw_rules(rng: random.Random, basket: Mapping[str, int], prices: Mapping[str, int],
               measured: str) -> list[dict[str, Any]]:
    """Two to four rules: the delivery rule, plus one to three of the others (design 4.2)."""
    goods = sum(prices[item] * quantity for item, quantity in basket.items())
    pool: list[dict[str, Any]] = []
    repeated = [item for item, quantity in basket.items() if quantity >= 2]
    if repeated:
        item = rng.choice(repeated)
        pool.append({"kind": "bundle", "item": item, "group": 3 if basket[item] >= 3 else 2})
    categories = {category_of(item) for item in basket}
    if categories:
        category = rng.choice(sorted(categories))
        in_category = sum(prices[item] * quantity for item, quantity in basket.items() if category_of(item) == category)
        if in_category > 2000:
            pool.append({"kind": "coupon", "category": category,
                         "threshold": round(in_category * rng.uniform(0.5, 0.95) / 100) * 100,
                         "amount": round(in_category * rng.uniform(0.1, 0.3) / 100) * 100})
    rate = rng.randint(3, 8)
    threshold = None if rng.random() < 0.4 else round(goods * rng.uniform(0.7, 1.05) / 100) * 100
    pool.append({"kind": "percent", "rate": rate, "threshold": threshold})
    # A store may only measure its threshold at a step it actually has: "after the coupon" needs a coupon rule,
    # "after all discounts" needs the percentage rule. Otherwise the wording would describe a step that is absent.
    needed = {"after_coupon": "coupon", "after_discount": "percent"}.get(measured)
    required = [rule for rule in pool if rule["kind"] == needed]
    if needed and not required:
        measured = "before"
    rest = [rule for rule in pool if rule not in required]
    rng.shuffle(rest)
    rules = required + rest[:rng.randint(1, 3) - len(required)]
    rng.shuffle(rules)
    rules.append({"kind": "delivery", "fee": rng.choice((2500, 2900, 3500, 4500)),
                  "free_at": round(goods * rng.uniform(0.8, 1.1) / 100) * 100, "measured": measured})
    return rules


def draw_stores(rng: random.Random, basket: Mapping[str, int]) -> list[dict[str, Any]]:
    measured = list(MEASURED)
    rng.shuffle(measured)
    stores = []
    for where in measured:
        prices = draw_prices(rng, basket)
        stores.append({"prices": prices, "rules": draw_rules(rng, basket, prices, where)})
    return stores


def _rng(set_name: str, index: int) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{set_name}:{index}".encode("utf-8")).hexdigest()[:16], 16))


def printed(stores: Sequence[Mapping[str, Any]]) -> set[int]:
    """Every amount the task prints: unit prices, thresholds, coupon amounts and delivery fees."""
    shown: set[int] = set()
    for store in stores:
        shown |= set(store["prices"].values())
        for rule in store["rules"]:
            shown |= {rule[key] for key in ("threshold", "amount", "fee", "free_at")
                      if isinstance(rule.get(key), int)}
    return shown


def draw(band: str, rng: random.Random) -> dict[str, Any] | None:
    """One draw of a basket and three stores; None when it does not meet the band (design 4.3)."""
    low, high, least_flips = BANDS[band]
    basket = draw_basket(rng)
    stores = draw_stores(rng, basket)
    receipts = [price(store, basket) for store in stores]
    totals = [receipt["total"] for receipt in receipts]
    if len(set(totals)) < 3 or set(totals) & printed(stores):
        return None  # no printed number may equal a store's total, so the answer is nowhere in the prompt
    gap = margin(stores, basket)
    flips = flipping(stores, basket)
    if not low <= gap < high or len(flips) < least_flips:
        return None
    return {"basket": dict(basket), "stores": stores, "receipts": receipts, "margin": gap, "flipping": flips,
            "winner": totals.index(min(totals))}
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: `28 passed`

Run: `python -m pytest -q`
Expected: `539 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/basket.py tests/test_gold_basket.py
git commit -m "Draw a basket and three stores that meet a difficulty band

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 과제·정답·영수증 파일

**Files:**
- Modify: `src/reasonlineage/gold/basket.py` (파일 끝)
- Modify: `tests/test_gold_basket.py` (import 블록, 파일 끝)

**Interfaces:**
- Consumes: Task 3의 `draw`, `build.shuffled`, `reasonlineage.engine.config.load_task`, `reasonlineage.diagnose.gold.correctness`
- Produces:
  - `render_rule(rule) -> str`, `question(drawn, letters) -> str`
  - `make_task(set_name, index, band, letter) -> {"task", "gold", "record"}`
  - `build(set_name, band, count, tasks_dir, gold_dir) -> list[Path]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_basket.py`의 import 블록을 다음으로 바꾼다.

```python
"""The generated shopping-basket gold set (basket design 4): prices, misreadings, bands and files."""

import json
import random
from collections import Counter

import pytest

from reasonlineage.diagnose.gold import correctness
from reasonlineage.engine.config import load_task
from reasonlineage.gold import basket as bk
```

파일 끝에 더한다.

```python
# --- 4.4 the task and the files ---

def test_a_band_that_cannot_be_filled_stops_with_the_count(monkeypatch):
    monkeypatch.setattr(bk, "MAX_TRIES", 3)
    monkeypatch.setattr(bk, "draw", lambda *args: None)
    with pytest.raises(bk.BasketError, match="basket-test-01: no basket in band 'hard' after 3 draws"):
        bk.make_task("basket-test", 0, "hard", "A")

def test_a_task_reads_as_a_shopping_question_and_hides_the_answer():
    made = bk.make_task("basket-test", 0, "medium", "B")
    task, record = made["task"], made["record"]
    assert task["id"] == "basket-test-01" and task["candidates"] == ["Store A", "Store B", "Store C"]
    assert (task["category"], task["data_sensitivity"]) == ("analytical", "public")
    assert made["gold"] == {"approved": ["Store B"], "failed": ["Store A", "Store C"]}
    question = task["question"]
    assert "You have no tools" in question and "Shopping list:" in question
    assert all(f"Store {letter}\n  unit prices (won):" in question for letter in bk.STORES)
    totals = {bk.won(s["receipt"]["total"]) for s in record["stores"]}  # no receipt leaks into the question
    assert not any(total in question for total in totals)
    assert record["winner"] == "Store B" and sorted(record["letters"]) == list(bk.STORES)
    cheapest = next(s for s in record["stores"] if s["letter"] == "B")
    assert cheapest["receipt"]["total"] == min(s["receipt"]["total"] for s in record["stores"])


def test_the_same_set_gives_the_same_task_and_another_set_a_different_one():
    first = bk.make_task("basket-test", 1, "easy", "A")
    assert first == bk.make_task("basket-test", 1, "easy", "A")
    assert bk.make_task("basket-other", 1, "easy", "A")["task"]["question"] != first["task"]["question"]


def test_build_writes_loadable_tasks_the_gold_file_and_the_receipts(tmp_path):
    paths = bk.build("basket-test", "medium", 3, tmp_path / "tasks", tmp_path / "gold")
    assert [p.name for p in paths] == [f"basket-test-0{i}.json" for i in (1, 2, 3)]
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text())
    record = json.loads((tmp_path / "gold" / "generation.json").read_text())
    assert gold["source"] == record["source"] == {"generator": "reasonlineage.gold.basket", "set": "basket-test",
                                                 "band": "medium"}
    for path in paths:
        task = load_task(path)
        truth = gold["tasks"][task.id]
        assert set(task.candidates) == {*truth["approved"], *truth["failed"]}  # what score_run checks
        assert correctness([*truth["approved"], *truth["failed"]], truth) == 1.0
        assert record["tasks"][task.id]["winner"] == truth["approved"][0]


def test_the_cheapest_store_is_spread_evenly_over_the_letters(tmp_path):
    bk.build("basket-test", "easy", 9, tmp_path / "tasks", tmp_path / "gold")
    gold = json.loads((tmp_path / "gold" / "gold.json").read_text())["tasks"]
    counts = Counter(entry["approved"][0] for entry in gold.values())
    assert set(counts) == {f"Store {letter}" for letter in bk.STORES} and max(counts.values()) == 3


def test_building_the_same_set_again_gives_the_same_bytes(tmp_path):
    bk.build("basket-test", "easy", 3, tmp_path / "tasks", tmp_path / "gold")
    before = {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]}
    bk.build("basket-test", "easy", 3, tmp_path / "tasks", tmp_path / "gold")
    assert {p.name: p.read_bytes() for p in [*(tmp_path / "tasks").iterdir(), *(tmp_path / "gold").iterdir()]} == before


def test_build_refuses_files_it_does_not_make_and_writes_nothing(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "basket-test-09.json").write_text("{}")
    with pytest.raises(bk.BasketError, match="basket-test-09.json is not built by this set"):
        bk.build("basket-test", "easy", 2, tmp_path / "tasks", tmp_path / "gold")
    assert not (tmp_path / "gold").exists()


def test_build_refuses_an_unknown_band(tmp_path):
    with pytest.raises(bk.BasketError, match="unknown band 'cheap'"):
        bk.build("basket-test", "cheap", 2, tmp_path / "tasks", tmp_path / "gold")
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: FAIL, `8 failed, 28 passed`, `AttributeError: module 'reasonlineage.gold.basket' has no attribute 'make_task'`(그리고 `build`)

- [ ] **Step 3: 코드 쓰기**

`basket.py` 끝에 더한다.

```python
# --- 4.4 the task and the files ---

def render_rule(rule: Mapping[str, Any]) -> str:
    if rule["kind"] == "bundle":
        offer = "3 for the price of 2" if rule["group"] == 3 else "2 for the price of 1"
        return f"{rule['item']}: {offer}"
    if rule["kind"] == "coupon":
        return (f"if the {rule['category']} items come to {won(rule['threshold'])} won or more, "
                f"take {won(rule['amount'])} won off the order")
    if rule["kind"] == "percent":
        if rule["threshold"] is None:
            return f"{rule['rate']}% off the order, with no condition"
        return f"if the order comes to {won(rule['threshold'])} won or more, {rule['rate']}% off the order"
    when = {"before": "the goods total before any discount",
            "after_coupon": "the amount after the coupon",
            "after_discount": "the amount after all discounts"}[rule["measured"]]
    return (f"delivery {won(rule['fee'])} won, free when {when} is {won(rule['free_at'])} won or more")


def question(drawn: Mapping[str, Any], letters: Sequence[str]) -> str:
    items = ", ".join(f"{item} x{quantity}" for item, quantity in drawn["basket"].items())
    blocks = []
    for letter, store in zip(letters, drawn["stores"]):
        prices = ", ".join(f"{item} {won(store['prices'][item])}" for item in drawn["basket"])
        rules = "\n".join(f"  - {render_rule(rule)}" for rule in store["rules"])
        blocks.append(f"Store {letter}\n  unit prices (won): {prices}\n{rules}")
    return QUESTION.format(list=items, stores="\n\n".join(blocks) + "\n")


def make_task(set_name: str, index: int, band: str, letter: str) -> dict[str, Any]:
    """Task `index` of the set: its task file body, gold entry and receipt record."""
    task_id = f"{set_name}-{index + 1:02d}"
    rng = _rng(set_name, index)
    for tries in range(1, MAX_TRIES + 1):
        drawn = draw(band, rng)
        if drawn is not None:
            break
    else:
        raise BasketError(f"{task_id}: no basket in band {band!r} after {MAX_TRIES} draws")
    # The cheapest store takes `letter`; the other two take the remaining letters in a fixed order.
    others = shuffled([x for x in STORES if x != letter], task_id)
    letters = [None, None, None]
    letters[drawn["winner"]] = letter
    for i in (i for i in range(3) if i != drawn["winner"]):
        letters[i] = others.pop(0)
    body = {"id": task_id, "question": question(drawn, letters), "candidates": [f"Store {x}" for x in STORES],
            "category": "analytical", "data_sensitivity": "public"}
    gold = {"approved": [f"Store {letter}"], "failed": sorted(f"Store {x}" for x in STORES if x != letter)}
    record = {"band": band, "letters": letters, "winner": f"Store {letter}", "margin": round(drawn["margin"], 5),
              "flipping": drawn["flipping"], "tries": tries, "basket": drawn["basket"],
              "stores": [{"letter": x, "prices": s["prices"], "rules": s["rules"], "receipt": r}
                         for x, s, r in zip(letters, drawn["stores"], drawn["receipts"])]}
    return {"task": body, "gold": gold, "record": record}


def build(set_name: str, band: str, count: int, tasks_dir: str | Path, gold_dir: str | Path) -> list[Path]:
    """Write `count` task files, gold.json and generation.json; nothing is written if a task cannot be made."""
    if band not in BANDS:
        raise BasketError(f"unknown band {band!r}; use one of {sorted(BANDS)}")
    tasks_dir, gold_dir = Path(tasks_dir), Path(gold_dir)
    ids = [f"{set_name}-{i + 1:02d}" for i in range(count)]
    stale = [f"{path} is not built by this set; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise BasketError("; ".join(stale))
    # The cheapest store's letter is spread evenly over the set, in an order fixed by the set name.
    letters = shuffled([STORES[i % len(STORES)] for i in range(count)], f"{set_name}:letters")
    made = [make_task(set_name, i, band, letter) for i, letter in enumerate(letters)]
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in made:
        path = tasks_dir / f"{task['task']['id']}.json"
        path.write_text(json.dumps(task["task"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    source = {"generator": "reasonlineage.gold.basket", "set": set_name, "band": band}
    for name, body in (("gold.json", {"source": source, "tasks": {t["task"]["id"]: t["gold"] for t in made}}),
                       ("generation.json", {"source": source, "tasks": {t["task"]["id"]: t["record"] for t in made}})):
        (gold_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_gold_basket.py`
Expected: `36 passed`

Run: `python -m pytest -q`
Expected: `547 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/gold/basket.py tests/test_gold_basket.py
git commit -m "Write the basket set's task, gold and receipt files

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: 만들기 스크립트

**Files:**
- Create: `scripts/build_basket.py` (실행 권한)
- Create: `tests/test_build_basket_script.py`

**Interfaces:**
- Consumes: Task 4의 `basket.build`, `basket.BasketError`
- Produces: `python scripts/build_basket.py SET --band easy|medium|hard --tasks N [--tasks-dir DIR] [--gold-dir DIR]`
  - 기본 폴더는 `tasks/SET`, `gold/SET`이다. 종료 코드는 성공 0, 만들 수 없으면 1, 인자 오류 2다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_build_basket_script.py`를 만든다.

```python
"""The basket set build script (basket design 3, 7)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_basket.py"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=env)


def test_the_script_builds_a_set(tmp_path):
    result = run("basket-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("2 task files in ") and result.stderr == ""  # no fit warnings
    assert sorted(p.name for p in (tmp_path / "tasks").iterdir()) == ["basket-test-01.json", "basket-test-02.json"]
    assert sorted(p.name for p in (tmp_path / "gold").iterdir()) == ["generation.json", "gold.json"]


@pytest.mark.parametrize("args, message", [
    (("basket-test", "--band", "harder", "--tasks", 2), "invalid choice: 'harder'"),
    (("Synth_Test", "--band", "easy", "--tasks", 2), "the set name takes lowercase letters"),
    (("basket-test", "--band", "easy", "--tasks", 0), "--tasks must be at least 1"),
])
def test_wrong_arguments_stop_before_anything_is_built(tmp_path, args, message):
    result = run(*args, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 2 and message in result.stderr
    assert not (tmp_path / "tasks").exists()


def test_a_stale_task_file_stops_the_build(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "basket-test-09.json").write_text("{}")
    result = run("basket-test", "--band", "easy", "--tasks", 2, "--tasks-dir", tmp_path / "tasks", "--gold-dir", tmp_path / "gold")
    assert result.returncode == 1 and "cannot build basket-test: " in result.stderr and "basket-test-09.json" in result.stderr
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest -q tests/test_build_basket_script.py`
Expected: FAIL, `5 failed`, `can't open file '…/scripts/build_basket.py'`

- [ ] **Step 3: 스크립트 쓰기**

`scripts/build_basket.py`를 만들고 `chmod +x scripts/build_basket.py`로 실행 권한을 준다.

```python
#!/usr/bin/env python3
"""Build a shopping-basket gold set (basket design 3, 4).

    python scripts/build_basket.py SET --band easy|medium|hard --tasks N
    # tasks/SET/*.json, gold/SET/gold.json and gold/SET/generation.json
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # this checkout's code, not an installed copy

BANDS = ("easy", "medium", "hard")  # basket.BANDS; listed here so a wrong argument fails before the import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("set", help="set name, e.g. basket-calib-easy or basket-v1")
    parser.add_argument("--band", required=True, choices=BANDS, help="the difficulty band")
    parser.add_argument("--tasks", required=True, type=int, help="number of tasks")
    parser.add_argument("--tasks-dir", type=Path, help="default: tasks/SET")
    parser.add_argument("--gold-dir", type=Path, help="default: gold/SET")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.set):
        parser.error("the set name takes lowercase letters, digits and single hyphens, e.g. basket-v1")
    if args.tasks < 1:
        parser.error("--tasks must be at least 1")
    from reasonlineage.gold import basket
    tasks_dir = args.tasks_dir or ROOT / "tasks" / args.set
    gold_dir = args.gold_dir or ROOT / "gold" / args.set
    try:
        written = basket.build(args.set, args.band, args.tasks, tasks_dir, gold_dir)
    except basket.BasketError as exc:
        print(f"cannot build {args.set}: {exc}", file=sys.stderr)
        return 1
    print(f"{len(written)} task files in {tasks_dir}; gold.json and generation.json in {gold_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest -q tests/test_build_basket_script.py`
Expected: `5 passed`

Run: `python -m pytest -q`
Expected: `552 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add scripts/build_basket.py tests/test_build_basket_script.py
git commit -m "Add the script that builds a basket gold set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 최종 검토 (모델 호출 전에)**

executing-plans의 최종 검토를 지금 한다. 대상은 이 계획의 커밋(설계 문서 커밋 023564b 이후)이다. 가장 강한 모델의 새 검토자를 쓰고, Critical·Important는 실패하는 테스트부터 써서 고친 뒤 Task 6으로 간다.

---

### Task 6: 보정 세트와 보정 실행

**Files:**
- Create: `tasks/basket-calib-{easy,medium,hard}/*.json`, `gold/basket-calib-{easy,medium,hard}/gold.json`, `generation.json`
- Create (커밋하지 않음): `.superpowers/sdd/2026-10-02-gold-basket/run_set.sh`

**Interfaces:**
- Consumes: Task 5의 스크립트, `scripts/run_gold.sh`
- Produces: 고른 구간 하나(`easy`, `medium`, `hard`) 또는 "멈춤". Task 7이 쓴다.

- [ ] **Step 1: 세 세트 만들기**

```bash
for b in easy medium hard; do python scripts/build_basket.py basket-calib-$b --band $b --tasks 2; done
```

Expected: 세 줄 모두 `2 task files in …/tasks/basket-calib-<구간>; gold.json and generation.json in …/gold/basket-calib-<구간>`

- [ ] **Step 2: 구간 조건을 확인하고 커밋**

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "src")
from reasonlineage.gold import basket as bk
for band in ("easy", "medium", "hard"):
    record = json.load(open(f"gold/basket-calib-{band}/generation.json"))
    low, high, least = bk.BANDS[band]
    for task_id, task in record["tasks"].items():
        assert low <= task["margin"] < high and len(task["flipping"]) >= least, (task_id, task["margin"])
        print(task_id, task["winner"], "margin", round(task["margin"], 4), "flips", len(task["flipping"]), "tries", task["tries"])
PY
git add tasks/basket-calib-* gold/basket-calib-*
for b in easy medium hard; do python scripts/build_basket.py basket-calib-$b --band $b --tasks 2 >/dev/null; done
git diff --exit-code --stat -- tasks gold && echo same
git commit -m "Add the three calibration sets of the basket gold set

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: 과제 6줄이 assert 오류 없이 나오고, 다시 만든 파일이 같아서 `same`이 찍힌다.

- [ ] **Step 3: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-basket
mkdir -p $W
cp .superpowers/sdd/2026-10-02-gold-biorxiv/run_set.sh $W/run_set.sh
pgrep -f "reasonlineage (run|resume)" && echo "another run is going; wait for it" || true
for b in easy medium hard; do setsid nohup bash $W/run_set.sh basket-calib-$b >> $W/calib.log 2>&1 < /dev/null; done &
```

- 다른 세트의 실행이 돌고 있으면 끝나기를 기다린다(Global Constraints).
- 대기는 백그라운드 명령으로 한다: `for i in $(seq 1 200); do pgrep -f "run_set.sh basket-calib" >/dev/null || break; sleep 30; done; tail -20 $W/calib.log`
- 과제당 6–10분, 6과제로 약 1시간이다.

- [ ] **Step 4: 규칙대로 구간 고르기**

```bash
python - <<'PY'
import json
order = ["easy", "medium", "hard"]
share = {b: json.load(open(f"runs/gold-basket-calib-{b}/report.json"))["level1"]["share_correct"] for b in order}
ok = [b for b in order if 0.375 <= share[b] <= 0.75]
pick = min(ok, key=lambda b: (abs(share[b] - 0.6), -order.index(b))) if ok else None
print(share, "->", pick or "stop: no band in 0.375-0.75")
PY
```

Expected: 구간별 비율과 고른 구간이 한 줄로 나온다.
- 고른 구간이 없으면 멈추고, 품목 수·규칙 수·차이 범위 중 무엇을 바꿀지 사용자와 정한다(설계 5.1).
- 진행 기록에 세 비율과 고른 구간을 적는다.

---

### Task 7: 본 세트, 실행, 분석 보고

**Files:**
- Create: `tasks/basket-v1/*.json`, `gold/basket-v1/gold.json`, `gold/basket-v1/generation.json`

**Interfaces:**
- Consumes: Task 6의 고른 구간 `BAND`, 실행 스크립트
- Produces: `runs/gold-basket-v1/report.json`과 `analysis.md`, 사용자에게 보내는 결론

- [ ] **Step 1: 본 세트 만들기와 커밋**

```bash
BAND=<Task 6에서 고른 구간>
python scripts/build_basket.py basket-v1 --band "$BAND" --tasks 20
python - <<'PY'
import json, sys
from collections import Counter
sys.path.insert(0, "src")
from reasonlineage.gold import basket as bk
record = json.load(open("gold/basket-v1/generation.json"))
band = record["source"]["band"]
low, high, least = bk.BANDS[band]
for task_id, task in record["tasks"].items():
    assert low <= task["margin"] < high and len(task["flipping"]) >= least, (task_id, task["margin"])
gold = json.load(open("gold/basket-v1/gold.json"))["tasks"]
print(band, Counter(entry["approved"][0] for entry in gold.values()))
PY
git add gold/basket-v1 tasks/basket-v1
git commit -m "Build the basket gold set v1

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Expected: `<구간> Counter({'Store A': 7, 'Store B': 7, 'Store C': 6})` 같은 줄(글자가 고르게 나뉘고, 차이는 최대 1)

- [ ] **Step 2: 과제 하나를 사용자에게 보여 주기**

```bash
python -c "import json; print(json.load(open('tasks/basket-v1/basket-v1-01.json'))['question'])"
python -c "
import json; r=json.load(open('gold/basket-v1/generation.json'))['tasks']['basket-v1-01']
print('receipt:'); [print(' ', s['letter'], s['receipt']) for s in r['stores']]
print('margin', round(r['margin'], 4), '| flipping', r['flipping'])"
```

사용자에게 과제 문구와 영수증을 보여 주고, 읽기 쉬운지 확인받는다. 정답은 코드가 계산하므로 검토가 아니라 확인이다. 답을 기다리되, 수정 요청이 없으면 Step 3으로 간다.

- [ ] **Step 3: 분리 실행하고 기다리기**

```bash
W=.superpowers/sdd/2026-10-02-gold-basket
setsid nohup bash $W/run_set.sh basket-v1 > $W/main.log 2>&1 < /dev/null &
```

Task 6 Step 3과 같은 방식으로 기다린다. 20과제로 약 3시간이다.

- [ ] **Step 4: 쌍이 모자라면 과제를 더하기**

```bash
python -c "import json; l=json.load(open('runs/gold-basket-v1/report.json'))['level1']; print(l['verdict'], l['share_correct'], l['pairs'])"
```

- `pairs`가 10개 이상이면 Step 5로 간다.
- 10개 미만이고 천장도 아니면, 같은 구간에서 과제 10개를 더 만들어 이어 붙인다(설계 5.2). `--tasks 30`으로 다시 만들면 앞 20과제는 그대로이고 10개가 더 생긴다. 그다음 같은 실행 스크립트를 다시 돌린다(끝난 과제는 건너뛴다).

- [ ] **Step 5: 분석 보고**

`runs/gold-basket-v1/analysis.md`를 읽고 사용자에게 알린다.
- 한 줄 결론으로 시작한다: 신호 / 신호 없음 / 보류(천장 또는 쌍 부족), 그리고 왜인지.
- 이어서 근거 수치를 두세 줄로 적는다: 정답률, 쌍 수, 일치도, 심사위원·저자별로 눈에 띄는 점.
- 틀린 답이 어느 오독에 해당하는지 한두 줄로 적는다. 영수증과 `flipping` 목록으로 확인할 수 있다.
- **다른 세트의 판정과 나란히 적는다.** 세트마다 따로 판정하고, 합친 수치는 보조로만 적는다.
- 보고서 경로를 링크한다. `signal`이면 2단계 기준을 먼저 정하자고 제안한다.
- 메모리에 결과를 남긴다.
