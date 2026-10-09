"""Food lookup, household-unit conversion and nutrient scaling over food_data.FOODS (+ the user's own foods).

Pure functions. Results are ESTIMATES: nutrients scale linearly from one reference serving and always carry a range.
"""
from __future__ import annotations

import difflib
import re
from functools import lru_cache
from typing import Any, Iterable

from food_data import CATEGORY_UNIT_GRAMS, FAT_UNIT_GRAMS, FOODS, GENERIC_UNIT_GRAMS

NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g")
# +/- spread applied to every estimate. Simple single-ingredient foods are tighter than cooked mixed dishes.
TOLERANCE = {"fruit": 0.12, "vegetable": 0.15, "dairy": 0.15, "protein": 0.15, "nuts": 0.12, "grain": 0.15, "fat": 0.10, "drink": 0.15,
             "condiment": 0.25, "sweet": 0.25, "bread": 0.20, "rice": 0.22, "dal": 0.25, "curry": 0.30, "nonveg": 0.30, "snack": 0.30, "breakfast": 0.25}
OIL_TSP_KCAL = 45.0
MAX_CUSTOM_FOODS = 200
UNIT_ALIASES = {"katoris": "katori", "bowls": "bowl", "cups": "cup", "glasses": "glass", "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
                "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "ladles": "ladle", "plates": "plate", "pieces": "piece", "pcs": "piece",
                "pc": "piece", "slices": "slice", "scoops": "scoop", "spoon": "tbsp", "spoons": "tbsp", "handfuls": "handful", "grams": "g", "gram": "g",
                "gm": "g", "gms": "g", "kgs": "kg", "litres": "l", "liters": "l", "litre": "l", "liter": "l", "millilitres": "ml", "ml": "ml"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower().replace("&", " and ")).strip()


def _variants(word: str) -> list[str]:
    out = [word]
    if word.endswith("ies") and len(word) > 4:
        out.append(word[:-3] + "y")
    if word.endswith("es") and len(word) > 3:
        out.append(word[:-2])
    if word.endswith("s") and len(word) > 2:
        out.append(word[:-1])
    return out


@lru_cache(maxsize=1)
def _index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for name, row in FOODS.items():
        idx.setdefault(norm(name), name)
    for name, row in FOODS.items():           # primary names win over aliases
        for alias in row["aliases"]:
            idx.setdefault(norm(alias), name)
    return idx


def _lookup_phrase(phrase: str, extra: dict[str, dict] | None = None) -> str | None:
    phrase = norm(phrase)
    if not phrase:
        return None
    idx = _index()
    tokens = phrase.split()
    for form in dict.fromkeys(" ".join(tokens[:-1] + [v]) for v in _variants(tokens[-1])):
        if extra and form in extra:
            return form
        if form in idx:
            return idx[form]
    return None


def find_food(query: str, extra: dict[str, dict] | None = None) -> dict | None:
    """Exact (name/alias/plural) match only. ``extra`` = the user's own foods keyed by normalised name."""
    key = _lookup_phrase(query, extra)
    if key is None:
        return None
    return (extra or {}).get(key) or FOODS.get(key)


def search(query: str, limit: int = 10, extra: dict[str, dict] | None = None) -> list[dict]:
    """Ranked matches: exact > prefix > all-words-contained > close spelling."""
    q = norm(query)
    if not q:
        return []
    limit = max(1, min(limit, 30))
    pool: dict[str, dict] = {**FOODS, **dict(list((extra or {}).items())[:MAX_CUSTOM_FOODS])}
    scored: list[tuple[float, str]] = []
    words = q.split()
    for name, row in pool.items():
        names = [norm(name)] + [norm(a) for a in row.get("aliases", [])]
        best = 0.0
        for n in names:
            if q == n or q in _variants(n) or n in _variants(q):
                best = max(best, 100)
            elif n.startswith(q) or q.startswith(n + " "):
                best = max(best, 80 - min(len(n) - len(q), 20) * 0.1)
            elif all(w in n.split() or any(v in n.split() for v in _variants(w)) for w in words):
                best = max(best, 60)
            elif len(q) >= 3 and q in n:
                best = max(best, 45)
        if best:
            scored.append((best, name))
    if len(scored) < limit and len(q) >= 3:
        have = {n for _s, n in scored}
        for name, row in pool.items():  # misspelling of any single word: "chikken" -> chicken curry
            if name in have:
                continue
            primary = set(norm(name).split())
            tokens = primary | {t for a in row.get("aliases", []) for t in norm(a).split()}
            best = max((difflib.SequenceMatcher(None, w, t).ratio() + (0.05 if t in primary else 0.0)
                        for w in words if len(w) >= 4 for t in tokens if len(t) >= 4), default=0.0)
            if best >= 0.8:
                scored.append((30 + best * 10, name))
    scored.sort(key=lambda t: (-t[0], len(t[1]), t[1]))
    return [pool[n] for _s, n in scored[:limit]]


def unit_grams(food: dict, unit: str | None) -> float | None:
    """Grams in one `unit` of this food, or None if the unit does not apply."""
    if not unit:
        return food["serving_g"]
    unit = UNIT_ALIASES.get(norm(unit), norm(unit))
    if unit in ("g", "kg", "ml", "l"):  # a weight/volume is always taken literally (1 ml ~ 1 g)
        return GENERIC_UNIT_GRAMS[unit]
    if unit == food.get("unit") or unit in ("serving", "portion", "helping"):
        return food["serving_g"]
    if unit in ("piece", "slice", "scoop") and food.get("unit") in ("piece", "slice", "scoop"):
        return food["serving_g"]
    if food.get("category") == "fat" and unit in FAT_UNIT_GRAMS:
        return FAT_UNIT_GRAMS[unit]
    by_cat = CATEGORY_UNIT_GRAMS.get(food.get("category", ""), {})
    if unit in by_cat:
        return by_cat[unit]
    if unit in GENERIC_UNIT_GRAMS:
        return GENERIC_UNIT_GRAMS[unit]
    return None


def scale(food: dict, grams: float, oil_extra_tsp: float = 0.0) -> dict[str, Any]:
    """Nutrients for `grams` of the food with a low/high range. grams is clamped to 0..5000."""
    grams = max(0.0, min(float(grams), 5000.0))
    factor = grams / food["serving_g"] if food["serving_g"] else 0.0
    out: dict[str, Any] = {k: food[k] * factor for k in NUTRIENTS}
    if oil_extra_tsp:
        extra = max(0.0, min(oil_extra_tsp, 20.0))
        out["kcal"] += extra * OIL_TSP_KCAL
        out["fat_g"] += extra * 5.0
    tol = TOLERANCE.get(food.get("category", ""), 0.25)
    if food.get("verified"):
        tol *= 0.6
    micros = {k: round(v * factor, 1) for k, v in (food.get("micros") or {}).items()}
    return {**{k: round(v, 1) for k, v in out.items()}, "kcal_low": round(out["kcal"] * (1 - tol)), "kcal_high": round(out["kcal"] * (1 + tol)),
            "micros": micros, "grams": round(grams, 1), "tolerance": tol}


def card(food: dict) -> dict:
    """Compact public shape for lists / search results."""
    return {"name": food["name"], "category": food.get("category"), "serving": food.get("serving"), "unit": food.get("unit"),
            "serving_g": food.get("serving_g"), **{k: food[k] for k in NUTRIENTS}, "diet": food.get("diet_label"),
            "allergens": food.get("allergens", []), "verified": bool(food.get("verified")), "source": food.get("source")}


def custom_food(name: str, serving_desc: str, serving_g: float, kcal: float, protein_g: float = 0.0, carbs_g: float = 0.0,
                fat_g: float = 0.0, fibre_g: float = 0.0, diet: str = "v", allergens: Iterable[str] = ()) -> dict:
    """A user-defined food (validated)."""
    name = norm(name)[:80]
    if not name:
        raise ValueError("name is required")
    nums = {"serving_g": serving_g, "kcal": kcal, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g, "fibre_g": fibre_g}
    for label, value in nums.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{label} must be a number")
    if not 1 <= serving_g <= 2000 or not 0 <= kcal <= 5000 or any(not 0 <= nums[k] <= 500 for k in ("protein_g", "carbs_g", "fat_g", "fibre_g")):
        raise ValueError("values are out of range")
    if kcal / serving_g > 9.5:
        raise ValueError("that is more calories per gram than pure fat has; please check the serving size")
    energy = 4 * protein_g + 4 * carbs_g + 9 * fat_g
    if kcal > 20 and not 0.7 * kcal <= energy + 4 * fibre_g * 0.5 <= 1.35 * kcal and energy > 0:
        raise ValueError("the calories do not match the protein, carbs and fat you entered; please check them")
    return {"name": name, "aliases": [], "category": "custom", "unit": "serving", "serving_g": float(serving_g), "serving": str(serving_desc)[:80] or "1 serving",
            "kcal": float(kcal), "protein_g": float(protein_g), "carbs_g": float(carbs_g), "fat_g": float(fat_g), "fibre_g": float(fibre_g),
            "diet": diet if diet in ("V", "v", "e", "n") else "v", "diet_label": {"V": "vegan", "v": "vegetarian", "e": "eggetarian", "n": "non-vegetarian"}.get(diet, "vegetarian"),
            "allergens": [str(a)[:20] for a in allergens][:10], "micros": {}, "jain_ok": False, "source": "your own entry", "verified": False}


def from_open_food_facts(product: dict) -> dict | None:
    """Convert an Open Food Facts product JSON (per 100 g) into a food row; None if it lacks energy. Network-free."""
    n = product.get("nutriments") or {}

    def num(key: str) -> float | None:
        value = n.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value == value else None

    kcal = num("energy-kcal_100g")
    if kcal is None and num("energy_100g") is not None:
        kcal = num("energy_100g") / 4.184
    if kcal is None or not 0 <= kcal <= 1000:
        return None
    name = norm(product.get("product_name") or product.get("generic_name") or "")[:80]
    if not name:
        return None
    serving_g = 100.0
    return {"name": name, "aliases": [], "category": "packaged", "unit": "g", "serving_g": serving_g, "serving": "100 g",
            "kcal": round(kcal, 1), "protein_g": min(num("proteins_100g") or 0.0, 100.0), "carbs_g": min(num("carbohydrates_100g") or 0.0, 100.0),
            "fat_g": min(num("fat_100g") or 0.0, 100.0), "fibre_g": min(num("fiber_100g") or 0.0, 100.0), "diet": "v", "diet_label": "check label", "allergens": [],
            "micros": {}, "jain_ok": False, "source": "Open Food Facts (community data, check the pack)", "verified": False,
            "barcode": str(product.get("code") or "")[:20]}
