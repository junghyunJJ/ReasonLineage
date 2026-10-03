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
