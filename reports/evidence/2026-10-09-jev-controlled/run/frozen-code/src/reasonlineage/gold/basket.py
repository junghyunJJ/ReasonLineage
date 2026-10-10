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
CONVENTIONS = (
    "Every store applies its promotions in this order: the bundle offers, then the category coupon, then the "
    "percentage discount, then delivery. A coupon's category total is the amount after the bundle offers. A "
    "percentage discount's own threshold is checked on the amount after the coupon. The percentage never applies "
    "to the delivery fee, and every amount is a whole number of won.")
QUESTION = (
    "You are buying the same shopping list from three online stores. Each store has its own unit prices and "
    "promotions. You have no tools: do the arithmetic in your own reasoning.\n\n"
    + CONVENTIONS + "\n\n"
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
    if misreading == "percent_before_coupon":  # this reader has already applied both steps by then
        measured = {"before": goods, "after_coupon": after_discount, "after_discount": after_discount}
    else:
        measured = {"before": goods, "after_coupon": after_coupon, "after_discount": after_discount}
    where = delivery["measured"]
    if misreading == "delivery_after_discount":
        where = "after_discount"
    elif misreading == "delivery_before":
        where = "before"
    fee = 0 if measured[where] >= delivery["free_at"] else delivery["fee"]
    if misreading == "no_delivery":
        fee = 0
    if misreading == "percent_on_delivery" and after_discount != after_coupon:
        total = (after_coupon + fee) - (after_coupon + fee) * percent["rate"] // 100  # the fee is discounted too
    else:
        total = after_discount + fee
    return {"lines": lines, "goods": goods, "after_coupon": after_coupon, "after_discount": after_discount,
            "delivery": fee, "total": total}


def category_of(item: str) -> str:
    return next(category for name, category, _ in ITEMS if name == item)


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
    for letter, store in sorted(zip(letters, drawn["stores"]), key=lambda pair: pair[0]):
        prices = ", ".join(f"{item} {won(store['prices'][item])}" for item in drawn["basket"])
        rules = "\n".join(f"  - {render_rule(rule)}" for rule in store["rules"])
        blocks.append(f"Store {letter}\n  unit prices (won): {prices}\n{rules}")
    return QUESTION.format(list=items, stores="\n\n".join(blocks) + "\n")


def letter_for(set_name: str, index: int) -> str:
    """The letter the cheapest store takes in task `index`.

    Each block of three tasks gets each letter once, in an order fixed by the set name and the block, so the
    letters stay balanced for any count and adding tasks never changes the ones already measured.
    """
    return shuffled(list(STORES), f"{set_name}:letters:{index // len(STORES)}")[index % len(STORES)]


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
    misreadings = {}
    for name, _ in MISREADINGS:
        totals = [price(store, drawn["basket"], name)["total"] for store in drawn["stores"]]
        misreadings[name] = {"winner": f"Store {letters[totals.index(min(totals))]}", "totals": totals}
    record = {"band": band, "letters": letters, "winner": f"Store {letter}", "margin": round(drawn["margin"], 5),
              "misreadings": misreadings,
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
    made = [make_task(set_name, i, band, letter_for(set_name, i)) for i in range(count)]
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
