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
