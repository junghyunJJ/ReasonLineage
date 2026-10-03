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
