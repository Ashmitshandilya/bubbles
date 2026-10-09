"""Understand a whole meal written in plain words: "2 rotis, dal, sabzi and a katori of curd" -> items + nutrient totals.

Deterministic (no model). Quantities, Indian household units and common combos (thali, dal chawal, idli sambar ...) are
understood. Anything it cannot match is returned in ``unrecognised`` and is NEVER guessed or counted. Totals carry a range.
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

import food_db
from food_data import FOODS

NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "half": 0.5, "quarter": 0.25, "couple": 2, "few": 3, "single": 1, "double": 2}
SIZE_FACTOR = {"small": 0.75, "mini": 0.6, "medium": 1.0, "large": 1.3, "big": 1.3, "huge": 1.7, "extra": 1.3}
FILLER = {"of", "some", "the", "my", "i", "had", "ate", "eaten", "have", "having", "just", "about", "around", "approx", "approximately", "fresh",
          "homemade", "home", "made", "hot", "cold", "warm", "plain", "little", "bit", "more", "extra", "for", "breakfast", "lunch", "dinner", "snack",
          "today", "yesterday", "tonight", "this", "morning", "evening", "afternoon", "night", "to", "in", "on", "sabji", "cooked", "boiled", "steamed"}
# boiled/steamed/cooked are dropped only after a direct lookup fails ("boiled egg", "steamed momos", "boiled potato" are real entries)
UNITS = {"katori", "katoris", "bowl", "bowls", "cup", "cups", "glass", "glasses", "tbsp", "tablespoon", "tablespoons", "tsp", "teaspoon", "teaspoons",
         "ladle", "ladles", "plate", "plates", "piece", "pieces", "pcs", "pc", "slice", "slices", "scoop", "scoops", "spoon", "spoons", "handful", "handfuls",
         "g", "gm", "gms", "gram", "grams", "kg", "ml", "l", "litre", "liter", "serving", "servings", "portion", "portions"}

# multi-item names people say as one thing. (food name, quantity, unit-or-None)
COMBOS: dict[str, list[tuple[str, float, str | None]]] = {
    "dal chawal": [("toor dal", 1, "katori"), ("rice", 1, "katori")], "dal rice": [("toor dal", 1, "katori"), ("rice", 1, "katori")],
    "rajma chawal": [("rajma", 1, "katori"), ("rice", 1, "katori")], "rajma rice": [("rajma", 1, "katori"), ("rice", 1, "katori")],
    "chole chawal": [("chole", 1, "katori"), ("rice", 1, "katori")], "chole bhature": [("chole", 1, "katori"), ("bhatura", 2, None)],
    "chana bhatura": [("chole", 1, "katori"), ("bhatura", 2, None)], "kadhi chawal": [("kadhi", 1, "katori"), ("rice", 1, "katori")],
    "idli sambar": [("idli", 3, None), ("sambar", 1, "katori"), ("coconut chutney", 2, "tbsp")],
    "dosa sambar": [("plain dosa", 1, None), ("sambar", 1, "katori"), ("coconut chutney", 2, "tbsp")],
    "vada sambar": [("medu vada", 2, None), ("sambar", 1, "katori")],
    "poori bhaji": [("puri", 3, None), ("aloo sabzi", 1, "katori")], "puri bhaji": [("puri", 3, None), ("aloo sabzi", 1, "katori")],
    "poori sabzi": [("puri", 3, None), ("aloo sabzi", 1, "katori")], "roti sabzi": [("roti", 2, None), ("mixed vegetable", 1, "katori")],
    "roti dal": [("roti", 2, None), ("toor dal", 1, "katori")], "dal roti": [("roti", 2, None), ("toor dal", 1, "katori")],
    "paratha curd": [("paratha", 2, None), ("curd", 1, "katori")], "paratha dahi": [("paratha", 2, None), ("curd", 1, "katori")],
    "aloo paratha curd": [("aloo paratha", 2, None), ("curd", 1, "katori")], "bread omelette": [("white bread", 2, None), ("omelette", 1, None)],
    "bread butter": [("white bread", 2, None), ("butter", 2, "tsp")], "bread jam": [("white bread", 2, None), ("sugar", 3, "tsp")],
    "tea biscuit": [("tea", 1, "cup"), ("biscuit", 4, None)], "chai biscuit": [("tea", 1, "cup"), ("biscuit", 4, None)],
    "chai samosa": [("tea", 1, "cup"), ("samosa", 1, None)], "egg roti": [("omelette", 1, None), ("roti", 2, None)],
    "chicken roti": [("chicken curry", 1, "katori"), ("roti", 2, None)], "chicken rice": [("chicken curry", 1, "katori"), ("rice", 1, "katori")],
    "fish rice": [("fish curry", 1, "katori"), ("rice", 1, "katori")], "fish curry rice": [("fish curry", 1, "katori"), ("rice", 1, "katori")],
    "sambar rice": [("sambar", 1, "katori"), ("rice", 1, "katori")], "rasam rice": [("rasam", 1, "katori"), ("rice", 1, "katori")],
    "curd chawal": [("curd rice", 1, "katori")], "oats milk": [("oats", 1, None), ("toned milk", 1, "glass")],
    "cornflakes milk": [("cornflakes", 1, None), ("toned milk", 1, "glass")], "pasta salad": [("pasta", 1, "katori"), ("green salad", 1, "bowl")],
    "thali": [("roti", 2, None), ("rice", 1, "katori"), ("toor dal", 1, "katori"), ("mixed vegetable", 1, "katori"), ("curd", 1, "katori"), ("green salad", 1, "bowl")],
    "veg thali": [("roti", 2, None), ("rice", 1, "katori"), ("toor dal", 1, "katori"), ("mixed vegetable", 1, "katori"), ("curd", 1, "katori"), ("green salad", 1, "bowl")],
    "south indian thali": [("rice", 1, "katori"), ("sambar", 1, "katori"), ("rasam", 1, "katori"), ("mixed vegetable", 1, "katori"), ("curd", 1, "katori"), ("papad", 1, None)],
    "non veg thali": [("roti", 2, None), ("rice", 1, "katori"), ("chicken curry", 1, "katori"), ("toor dal", 1, "katori"), ("green salad", 1, "bowl")],
    "full meal": [("roti", 2, None), ("rice", 1, "katori"), ("toor dal", 1, "katori"), ("mixed vegetable", 1, "katori"), ("curd", 1, "katori")],
}

MAX_CHUNKS = 30        # a meal has a handful of foods; more is a typo or an attack and would cost seconds of CPU
MAX_QUANTITY = 100
_SPLIT = re.compile(r"\s*(?:,|;|\+|&|\n|\bplus\b|\band\b|\bwith\b|\balong with\b|\bon\b|\btopped with\b|\bfollowed by\b|\bthen\b)\s*")
_NUM = re.compile(r"^(\d+\s+\d/\d|\d+/\d+|\d+(?:\.\d+)?|[a-z]+)\b")
_GRAMS_FIRST = re.compile(r"^(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|litre|liter)\b\s*(?:of\s+)?(.*)$")
_TRAILING_X = re.compile(r"\s*(?:x|\*)\s*(\d+(?:\.\d+)?)\s*$")


def _to_number(token: str) -> float | None:
    token = token.strip().lower()
    if token.isalpha():                       # words only from the table: "nan" and "inf" are not numbers
        return NUMBER_WORDS.get(token)
    try:
        if " " in token:
            whole, frac = token.split(" ", 1)
            value = float(whole) + float(Fraction(frac))
        elif "/" in token:
            value = float(Fraction(token))
        else:
            value = float(token)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return value if value == value and abs(value) < 1e6 else None


def _split_amount(chunk: str) -> tuple[float | None, str | None, str, float]:
    """-> (quantity or None, unit or None, food phrase, size factor)"""
    text = chunk.strip()
    size = 1.0
    m = _GRAMS_FIRST.match(text)
    if m:
        return float(m[1]), m[2], m[3].strip(), size
    qty: float | None = None
    mx = _TRAILING_X.search(text)
    if mx:
        qty, text = float(mx[1]), text[:mx.start()].strip()
    m = _NUM.match(text)
    if m and _to_number(m[1]) is not None:
        number = _to_number(m[1])
        rest = text[m.end():].strip()
        if qty is None:
            qty = number
        text = rest
    unit = None
    words = text.split()
    # "2 tsp ghee", "1 katori of dal", "half plate rice", "a bowl of dal"
    while words and words[0] in SIZE_FACTOR:
        size *= SIZE_FACTOR[words[0]]
        words = words[1:]
    if words and words[0] in UNITS:
        unit = words[0]
        words = words[1:]
        if words and words[0] == "of":
            words = words[1:]
    # a quantity word that was not a number ("couple of rotis") is handled by NUMBER_WORDS above
    return qty, unit, " ".join(words).strip(), size


def _resolve(phrase: str, extra: dict[str, dict] | None) -> tuple[dict | None, str]:
    """-> (food, match quality 'exact'|'approximate'|'none')"""
    words = [w for w in food_db.norm(phrase).split() if w]
    if not words:
        return None, "none"
    candidates = [" ".join(words)]
    stripped = [w for w in words if w not in FILLER]
    if stripped and stripped != words:
        candidates.append(" ".join(stripped))
    # drop size words, then try the last 3, 2, 1 words ("homemade paneer butter masala")
    base = [w for w in stripped if w not in SIZE_FACTOR]
    for n in (3, 2, 1):
        if len(base) > n:
            candidates.append(" ".join(base[-n:]))
    candidates.append(" ".join(base))
    for cand in dict.fromkeys(candidates):
        food = food_db.find_food(cand, extra)
        if food:
            return food, "exact"
    for cand in dict.fromkeys(c for c in candidates if len(c) <= 30):
        hits = food_db.search(cand, limit=1, extra=extra)
        if hits and len(cand) >= 4 and cand.split()[-1] in food_db.norm(hits[0]["name"] + " " + " ".join(hits[0].get("aliases", []))).split():
            return hits[0], "approximate"
    return None, "none"


def _qty_unit_grams(food: dict, qty: float | None, unit: str | None, size: float) -> tuple[float, float | None, str | None, str | None]:
    """-> (grams, shown quantity, shown unit, note)"""
    note = None
    if unit and food_db.UNIT_ALIASES.get(unit, unit) in ("g", "kg", "ml", "l"):
        per = food_db.unit_grams(food, unit) or 1.0
        return (qty if qty is not None else 1.0) * per, qty, unit, None
    q = min(qty if qty is not None else 1.0, MAX_QUANTITY) * size
    if unit:
        per = food_db.unit_grams(food, unit)
        if per is None:
            per, note = food["serving_g"], f"'{unit}' is not a size Bubbles knows for {food['name']}; counted as one serving"
        return q * per, q, food_db.UNIT_ALIASES.get(unit, unit), note
    return q * food["serving_g"], q, food["unit"], None


def compose(text: str, extra_foods: dict[str, dict] | None = None, oil_extra_tsp: float = 0.0) -> dict[str, Any]:
    """Parse a meal description. Returns {items, totals, unrecognised, allergens, notes}. Never raises on odd text."""
    text = (text or "")[:2000].lower().strip()
    items: list[dict] = []
    unrecognised: list[str] = []
    notes: list[str] = []

    def add(food: dict, qty: float | None, unit: str | None, size: float, said: str, quality: str) -> None:
        grams, shown_qty, shown_unit, note = _qty_unit_grams(food, qty, unit, size)
        oil = oil_extra_tsp if food.get("category") in ("curry", "rice", "dal", "nonveg", "breakfast", "snack", "bread") and oil_extra_tsp else 0.0
        nut = food_db.scale(food, grams, oil)
        items.append({"text": said, "food": food["name"], "category": food.get("category"), "quantity": shown_qty, "unit": shown_unit, "grams": nut["grams"],
                      "kcal": nut["kcal"], "kcal_low": nut["kcal_low"], "kcal_high": nut["kcal_high"], "protein_g": nut["protein_g"],
                      "carbs_g": nut["carbs_g"], "fat_g": nut["fat_g"], "fibre_g": nut["fibre_g"], "micros": nut["micros"],
                      "match": quality, "allergens": food.get("allergens", []), "diet": food.get("diet"),
                      "source": food.get("source"), "verified": bool(food.get("verified"))})
        if note:
            notes.append(note)

    chunks = list(dict.fromkeys(c.strip()[:80] for c in _SPLIT.split(text) if c and c.strip()))[:MAX_CHUNKS]
    resolved: dict[str, tuple[dict | None, str]] = {}
    for chunk in chunks:
        clean = re.sub(r"^(?:i\s+)?(?:had|ate|eaten|have|having|took|got|ordered)\s+", "", chunk).strip()
        combo_key = " ".join(w for w in food_db.norm(clean).split() if w not in ("a", "an", "the", "some", "full"))
        combo_key = re.sub(r"^(?:\d+\s+)", "", combo_key)
        combo = COMBOS.get(combo_key) or COMBOS.get(food_db.norm(clean))
        if combo:
            for name, qty, unit in combo:
                food = FOODS.get(name)
                if food:
                    add(food, qty, unit, 1.0, f"{clean} ({name})", "combo")
            continue
        qty, unit, phrase, size = _split_amount(clean)
        if not phrase:
            continue
        if phrase not in resolved:
            resolved[phrase] = _resolve(phrase, extra_foods)
        food, quality = resolved[phrase]
        if food is None:
            if food_db.norm(phrase) not in ("nothing", "water", "it", "that", "this"):
                unrecognised.append(" ".join(w for w in phrase.split() if w not in FILLER) or phrase)
            continue
        add(food, qty, unit, size, clean, quality)

    totals = {"kcal": 0.0, "kcal_low": 0.0, "kcal_high": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fibre_g": 0.0}
    micros: dict[str, float] = {}
    for it in items:
        for k in totals:
            totals[k] += it[k]
        for k, v in it["micros"].items():
            micros[k] = micros.get(k, 0.0) + v
    totals = {k: round(v, 1) if k.endswith("_g") else round(v) for k, v in totals.items()}
    allergens = sorted({a for it in items for a in it["allergens"]})
    return {"items": items, "totals": totals, "micros": {k: round(v, 1) for k, v in micros.items()}, "unrecognised": unrecognised,
            "allergens": allergens, "notes": notes, "approximate": any(i["match"] == "approximate" for i in items),
            "label": "estimate" if items else "nothing recognised"}


def conflicts(parsed: dict, diet_style: str | None, allergies: list[str] | None) -> list[str]:
    """Plain warnings if the meal clashes with the user's diet style or recorded allergies (never silent)."""
    out: list[str] = []
    rank = {"V": 0, "v": 1, "e": 2, "n": 3}
    limit = {"vegan": 0, "vegetarian": 1, "veg": 1, "jain": 1, "eggetarian": 2}.get((diet_style or "").lower())
    allergy_words = [food_db.norm(a) for a in (allergies or []) if a]
    for it in parsed.get("items", []):
        if limit is not None and rank.get(it.get("diet") or "v", 1) > limit:
            out.append(f"{it['food']} is not {diet_style}")
        for word in allergy_words:
            if word and (word in [food_db.norm(a) for a in it.get("allergens", [])] or word in food_db.norm(it["food"]).split()):
                out.append(f"{it['food']} may contain {word}, which is on your allergy list")
    return list(dict.fromkeys(out))
