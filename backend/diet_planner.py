"""Deterministic weekly meal planner over food_data. No model decides numbers or safety.

Given daily targets (plan_engine) and a person's food preferences it picks meal templates per slot, scales portions to
the calorie budget, filters by diet style / allergies / dislikes (hard filters), nudges by likes and conditions, keeps
variety, and can swap a meal or produce a grocery list. Everything is an ESTIMATE and shown with a range.
"""
from __future__ import annotations

import hashlib
from typing import Any

import food_db
from food_data import FOODS

Component = tuple[str, float, "str | None"]

# (id, slot, display name, components, tags)   tags: lowgi, refined, fried, iron, highprotein, light, sweet
TEMPLATES: list[tuple[str, str, str, list[Component], str]] = [
    # --- breakfast
    ("b-poha", "breakfast", "Poha with peanuts and tea", [("poha", 1.25, None), ("peanuts", 0.5, None), ("tea without sugar", 1, None)], "light"),
    ("b-idli", "breakfast", "Idli, sambar and coconut chutney", [("idli", 3, None), ("sambar", 1, None), ("coconut chutney", 2, None)], "light lowgi"),
    ("b-dosa", "breakfast", "Dosa with sambar", [("plain dosa", 2, None), ("sambar", 1, None), ("coconut chutney", 1, None)], ""),
    ("b-besan", "breakfast", "Besan chilla with curd", [("besan chilla", 2, None), ("green chutney", 1, None), ("curd", 1, None)], "lowgi highprotein"),
    ("b-moong", "breakfast", "Moong dal chilla with chutney", [("moong dal chilla", 2, None), ("green chutney", 1, None), ("curd", 0.75, None)], "lowgi highprotein"),
    ("b-oats", "breakfast", "Oats porridge with banana and almonds", [("oats porridge", 1, None), ("banana", 1, None), ("almonds", 6, None)], "lowgi"),
    ("b-upma", "breakfast", "Vegetable upma with curd", [("upma", 1, None), ("curd", 0.75, None)], ""),
    ("b-paratha", "breakfast", "Aloo paratha with curd", [("aloo paratha", 1, None), ("curd", 1, None)], ""),
    ("b-sandwich", "breakfast", "Veg sandwich with milk", [("veg sandwich", 1, None), ("toned milk", 1, None)], "refined"),
    ("b-eggs", "breakfast", "Egg bhurji with brown bread", [("egg bhurji", 1, None), ("brown bread", 2, None), ("orange", 1, None)], "highprotein"),
    ("b-omelette", "breakfast", "Masala omelette and toast", [("omelette", 1, None), ("brown bread", 2, None), ("banana", 1, None)], "highprotein"),
    ("b-sprouts", "breakfast", "Sprouts chaat with tea", [("sprouts", 1.5, None), ("tea without sugar", 1, None), ("orange", 1, None)], "lowgi highprotein iron"),
    ("b-daliya", "breakfast", "Daliya porridge with milk", [("daliya", 1, None), ("toned milk", 1, None)], "lowgi"),
    ("b-yogurt", "breakfast", "Greek yogurt with muesli and berries", [("greek yogurt", 1.5, None), ("muesli", 0.75, None), ("strawberries", 1, None)], "highprotein"),
    ("b-ragi", "breakfast", "Ragi roti with curd", [("ragi roti", 2, None), ("curd", 1, None), ("green chutney", 1, None)], "lowgi iron"),
    ("b-thalipeeth", "breakfast", "Thalipeeth with curd", [("thalipeeth", 2, None), ("curd", 1, None)], "lowgi"),
    ("b-paneerparatha", "breakfast", "Paneer paratha with curd", [("paneer paratha", 1, None), ("curd", 1, None)], "highprotein"),
    ("b-tofu", "breakfast", "Tofu bhurji on brown bread", [("tofu bhurji", 1.25, None), ("brown bread", 2, None), ("banana", 1, None)], "highprotein"),
    ("b-oatssoy", "breakfast", "Overnight oats with soy milk and banana", [("oats", 1, None), ("soy milk", 1, None), ("banana", 1, None), ("chia seeds", 1, None)], "lowgi"),
    ("b-pesarattu", "breakfast", "Pesarattu with coconut chutney", [("pesarattu", 2, None), ("coconut chutney", 2, None)], "lowgi highprotein"),
    # --- snacks
    ("s-fruit-nuts", "snack", "Apple with almonds", [("apple", 1, None), ("almonds", 8, None)], "lowgi"),
    ("s-chana", "snack", "Roasted chana and buttermilk", [("roasted chana", 1.5, None), ("chaas", 1, None)], "lowgi highprotein iron"),
    ("s-sprout", "snack", "Sprouts salad", [("sprouts", 1, None), ("cucumber", 1, None), ("tomato", 1, None)], "lowgi light iron"),
    ("s-makhana", "snack", "Roasted makhana", [("makhana", 1.5, None)], "light"),
    ("s-guava", "snack", "Guava and a handful of peanuts", [("guava", 1, None), ("peanuts", 0.7, None)], "lowgi"),
    ("s-curdfruit", "snack", "Curd with papaya", [("curd", 1, None), ("papaya", 1, None)], "light"),
    ("s-paneer", "snack", "Paneer cubes with cucumber", [("paneer", 0.5, None), ("cucumber", 1.5, None)], "highprotein lowgi"),
    ("s-egg", "snack", "Boiled eggs with a fruit", [("boiled egg", 2, None), ("guava", 1, None)], "highprotein"),
    ("s-shake", "snack", "Protein shake with banana", [("whey protein", 1, None), ("banana", 1, None), ("water", 1, None)], "highprotein"),
    ("s-hummus", "snack", "Hummus with cucumber and carrot", [("hummus", 3, None), ("cucumber", 1.5, None), ("carrot", 1, None)], "lowgi"),
    ("s-dhokla", "snack", "Dhokla with green chutney", [("dhokla", 3, None), ("green chutney", 1, None)], "light"),
    ("s-corn", "snack", "Steamed sweet corn", [("sweet corn", 1.5, None), ("nimbu pani", 0.5, None)], ""),
    ("s-tofu", "snack", "Soya chunks salad", [("soya chunks", 1, None), ("green salad", 1, None)], "highprotein lowgi iron"),
    ("s-fruitbowl", "snack", "Fruit bowl", [("papaya", 1, None), ("pomegranate", 1, None), ("orange", 1, None)], "light lowgi"),
    ("s-yogurt", "snack", "Greek yogurt with walnuts", [("greek yogurt", 1, None), ("walnuts", 3, None)], "highprotein lowgi"),
    ("s-peanutbread", "snack", "Peanut butter on brown bread", [("peanut butter", 1.5, None), ("brown bread", 2, None)], ""),
    # --- lunch / dinner (main meals)
    ("m-rotidal", "main", "Roti, dal, vegetable and curd", [("roti", 2, None), ("toor dal", 1, None), ("mixed vegetable", 1, None), ("curd", 1, None), ("green salad", 1, None)], "lowgi"),
    ("m-ricedal", "main", "Rice, dal, vegetable and salad", [("rice", 1.25, None), ("toor dal", 1, None), ("mixed vegetable", 1, None), ("green salad", 1, None)], "refined"),
    ("m-rajma", "main", "Rajma with rice and salad", [("rajma", 1, None), ("rice", 1, None), ("green salad", 1, None)], "iron highprotein"),
    ("m-chole", "main", "Chole with roti and salad", [("chole", 1, None), ("roti", 2, None), ("green salad", 1, None)], "iron highprotein"),
    ("m-palakpaneer", "main", "Palak paneer with roti and salad", [("palak paneer", 1, None), ("roti", 2, None), ("green salad", 1, None)], "iron highprotein"),
    ("m-chicken", "main", "Chicken curry with roti and salad", [("chicken curry", 1, None), ("roti", 2, None), ("green salad", 1, None)], "highprotein"),
    ("m-grilledchicken", "main", "Grilled chicken, sweet potato and salad", [("chicken breast", 1.5, None), ("sweet potato", 1, None), ("green salad", 1.5, None)], "highprotein lowgi"),
    ("m-fish", "main", "Fish curry with rice and a vegetable", [("fish curry", 1, None), ("rice", 1, None), ("beans poriyal", 1, None)], "highprotein"),
    ("m-eggcurry", "main", "Egg curry with roti and salad", [("egg curry", 1, None), ("roti", 2, None), ("green salad", 1, None)], "highprotein"),
    ("m-khichdi", "main", "Moong khichdi with curd and salad", [("khichdi", 1.25, None), ("curd", 1, None), ("green salad", 1, None)], "light"),
    ("m-curdrice", "main", "Curd rice with a vegetable", [("curd rice", 1.25, None), ("beans poriyal", 1, None), ("pickle", 1, None)], ""),
    ("m-paneerbhurji", "main", "Paneer bhurji with roti and dal", [("paneer bhurji", 1, None), ("roti", 2, None), ("moong dal", 1, None)], "highprotein"),
    ("m-soya", "main", "Soya chunks curry with roti and salad", [("soya chunks curry", 1, None), ("roti", 2, None), ("green salad", 1, None)], "highprotein iron"),
    ("m-tofu", "main", "Tofu bhurji with roti and dal", [("tofu bhurji", 1, None), ("roti", 2, None), ("moong dal", 1, None)], "highprotein"),
    ("m-quinoa", "main", "Quinoa, dal and vegetables", [("quinoa", 1, None), ("moong dal", 1, None), ("mixed vegetable", 1, None)], "lowgi"),
    ("m-mushroom", "main", "Mushroom masala with roti and dal", [("mushroom masala", 1, None), ("roti", 2, None), ("masoor dal", 1, None)], ""),
    ("m-kadhi", "main", "Kadhi, rice and vegetable", [("kadhi", 1, None), ("rice", 1, None), ("lauki sabzi", 1, None)], ""),
    ("m-bajra", "main", "Bajra roti, dal and vegetable", [("bajra roti", 2, None), ("toor dal", 1, None), ("lauki sabzi", 1, None), ("chaas", 1, None)], "lowgi iron"),
    ("m-jowar", "main", "Jowar roti, palak dal and sabzi", [("jowar roti", 2, None), ("palak dal", 1, None), ("cabbage sabzi", 1, None)], "lowgi iron"),
    ("m-sambar", "main", "Sambar rice with poriyal", [("rice", 1, None), ("sambar", 1.5, None), ("cabbage sabzi", 1, None), ("curd", 0.75, None)], ""),
    ("m-mutton", "main", "Mutton curry with roti and salad", [("mutton curry", 1, None), ("roti", 2, None), ("green salad", 1, None)], "highprotein iron"),
    ("m-prawn", "main", "Prawn curry with rice and salad", [("prawn curry", 1, None), ("rice", 1, None), ("green salad", 1, None)], "highprotein"),
    ("m-chana-salad", "main", "Chana salad bowl with curd", [("boiled chana", 1.5, None), ("green salad", 2, None), ("curd", 1, None)], "lowgi highprotein iron light"),
    ("m-dalroti-veg", "main", "Roti, dal fry and aloo gobi", [("roti", 2, None), ("dal fry", 1, None), ("aloo gobi", 1, None)], ""),
    ("m-lobia", "main", "Lobia curry, roti and salad", [("lobia", 1, None), ("roti", 2, None), ("green salad", 1, None)], "lowgi iron"),
    ("m-pasta", "main", "Vegetable pasta with salad", [("pasta", 1.5, None), ("green salad", 1.5, None), ("mushrooms", 1, None)], "refined"),
]
SLOT_SHARE = {3: {"breakfast": 0.27, "main1": 0.38, "main2": 0.35},
              4: {"breakfast": 0.25, "main1": 0.32, "snack": 0.1, "main2": 0.33},
              5: {"breakfast": 0.23, "snack1": 0.08, "main1": 0.3, "snack2": 0.1, "main2": 0.29}}
SLOT_LABEL = {"breakfast": "Breakfast", "main1": "Lunch", "main2": "Dinner", "snack": "Evening snack", "snack1": "Mid-morning snack", "snack2": "Evening snack"}
LOG_MEAL = {"breakfast": "breakfast", "main1": "lunch", "main2": "dinner", "snack": "snack", "snack1": "snack", "snack2": "snack"}   # names the food log accepts
DIET_RANK = {"V": 0, "v": 1, "e": 2, "n": 3}
ALLOWED_RANK = {"vegan": 0, "vegetarian": 1, "veg": 1, "jain": 1, "eggetarian": 2, "egg": 2, "non-vegetarian": 3, "nonveg": 3, "none": 3, "": 3, None: 3}
RAW_FACTOR = {"rice": 0.4, "dal": 0.35, "bread": 0.7, "breakfast": 0.6}
AISLE = {"bread": "Grains & flours", "rice": "Grains & flours", "grain": "Grains & flours", "breakfast": "Grains & flours", "dal": "Pulses & legumes",
         "vegetable": "Fresh produce", "fruit": "Fresh produce", "curry": "Fresh produce", "dairy": "Dairy & eggs", "protein": "Dairy, eggs & protein",
         "nonveg": "Meat & fish", "nuts": "Nuts & seeds", "fat": "Oils & pantry", "condiment": "Oils & pantry", "snack": "Snacks", "drink": "Drinks", "sweet": "Pantry"}
PIECE_STEP = 0.5


def _slots(meals_per_day: int) -> list[tuple[str, str]]:
    shares = SLOT_SHARE.get(meals_per_day) or SLOT_SHARE[4]
    return [(k, "main" if k.startswith("main") else "snack" if k.startswith("snack") else k) for k in shares]


def _words(texts: list[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        for w in food_db.norm(t).split():
            out.add(w)
            out.update(food_db._variants(w))
    return out


def _template_foods(tpl) -> list[dict]:
    return [FOODS[c[0]] for c in tpl[3]]


def _eligible(tpl, prefs: dict) -> bool:
    foods = _template_foods(tpl)
    rank_limit = ALLOWED_RANK.get((prefs.get("diet_style") or "").lower(), 3)
    if any(DIET_RANK[f["diet"]] > rank_limit for f in foods):
        return False
    if (prefs.get("diet_style") or "").lower() == "jain" and not all(f["jain_ok"] for f in foods):
        return False
    allergy = _words(prefs.get("allergies") or [])
    if allergy:
        if "nut" in allergy or "nuts" in allergy:
            allergy |= {"peanut", "tree"}
        for f in foods:
            tokens = _words(f["allergens"] + [f["name"]] + f.get("aliases", []))
            if allergy & tokens:
                return False
        if "gluten" in allergy or "wheat" in allergy:
            if any("gluten" in f["allergens"] for f in foods):
                return False
    dislikes = _words(prefs.get("dislikes") or [])
    if dislikes and any(dislikes & _words([f["name"]] + f.get("aliases", [])) for f in foods):
        return False
    return True


def _round_qty(food: dict, qty: float) -> float:
    if food["unit"] in ("piece", "slice", "scoop"):
        return max(PIECE_STEP, round(qty / PIECE_STEP) * PIECE_STEP) if qty < 6 else float(round(qty))
    if food["unit"] == "g":
        return max(0.25, round(qty * 4) / 4)
    return max(0.25, round(qty * 4) / 4)


def _build_meal(tpl, factor: float) -> dict:
    items = []
    for name, qty, unit in tpl[3]:
        food = FOODS[name]
        q = _round_qty(food, qty * factor)
        grams = q * (food_db.unit_grams(food, unit) or food["serving_g"])
        n = food_db.scale(food, grams)
        items.append(_item(food, name, q, unit, n))
    return {"template_id": tpl[0], "name": tpl[2], "items": items, "factor": round(factor, 2), "tags": tpl[4].split(), "totals": _totals(items)}


def _item(food: dict, name: str, q: float, unit: str | None, n: dict, **extra) -> dict:
    return {"food": name, "quantity": q, "unit": unit or food["unit"], "grams": n["grams"], "kcal": n["kcal"], "kcal_low": n["kcal_low"],
            "kcal_high": n["kcal_high"], "protein_g": n["protein_g"], "carbs_g": n["carbs_g"], "fat_g": n["fat_g"], "fibre_g": n["fibre_g"],
            "category": food["category"], "micros": n["micros"], "label": _label(food, q, unit, n["grams"]), **extra}


def _label(food: dict, q: float, unit: str | None, grams: float) -> str:
    """Plain wording for a portion: '40 g chicken breast', '2 roti', '1.5 katori rice'."""
    unit = unit or food["unit"]
    if unit == "g" or food["unit"] == "g":
        return f"{round(grams / 5) * 5:g} g {food['name']}"
    return f"{q:g} {unit} {food['name']}"


def _totals(items: list[dict]) -> dict:
    keys = ("kcal", "kcal_low", "kcal_high", "protein_g", "carbs_g", "fat_g", "fibre_g")
    sums = {k: sum(i[k] for i in items) for k in keys}
    return {k: round(v, 1) if k.endswith("_g") else round(v) for k, v in sums.items()}


def _scale_for(tpl, target_kcal: float) -> tuple[float, float]:
    base = sum(FOODS[c[0]]["kcal"] * c[1] * (food_db.unit_grams(FOODS[c[0]], c[2]) or FOODS[c[0]]["serving_g"]) / FOODS[c[0]]["serving_g"] for c in tpl[3])
    factor = max(0.55, min(1.8, target_kcal / base)) if base > 0 else 1.0
    return factor, base * factor


def _score(tpl, meal: dict, slot_kcal: float, prefs: dict, recent: list[str], day_protein_need: float) -> float:
    err = abs(meal["totals"]["kcal"] - slot_kcal) / max(slot_kcal, 1)
    score = 50.0 - 120.0 * err
    foods = [c[0] for c in tpl[3]]
    likes = _words(prefs.get("likes") or []) | _words(prefs.get("must_include") or [])
    if likes:
        score += 6 * len(likes & _words(foods + [a for f in foods for a in FOODS[f].get("aliases", [])]))
    for must in prefs.get("must_include") or []:
        if food_db.norm(must) in {food_db.norm(f) for f in foods}:
            score += 14
    if tpl[0] in recent[-3:]:
        score -= 60
    elif tpl[0] in recent:
        score -= 15
    tags = set(meal["tags"])
    c = prefs.get("conditions") or {}
    if c.get("diabetes") or c.get("pcos"):
        score += 10 * ("lowgi" in tags) - 15 * ("refined" in tags)
    if c.get("anaemia") or prefs.get("menstruating"):
        score += 6 * ("iron" in tags)
    if c.get("cholesterol") or c.get("gerd"):
        score -= 8 * ("fried" in tags)
    if prefs.get("goal") == "lose":
        score += 3 * ("light" in tags) + 4 * ("highprotein" in tags)
    pshare = meal["totals"]["protein_g"] / max(day_protein_need, 1)
    score += min(22.0, 60 * pshare)
    jitter = int(hashlib.md5((tpl[0] + str(prefs.get("seed", 0)) + str(len(recent))).encode()).hexdigest()[:4], 16) / 65535.0
    return score + 3 * jitter


def plan_day(targets: dict, prefs: dict, recent: list[str] | None = None, meals_per_day: int = 4) -> dict:
    recent = list(recent or [])
    shares = SLOT_SHARE.get(meals_per_day) or SLOT_SHARE[4]
    pool = [t for t in TEMPLATES if _eligible(t, prefs)]
    meals: list[dict] = []
    for slot, kind in _slots(meals_per_day):
        slot_kcal = targets["kcal"] * shares[slot]
        candidates = [t for t in pool if t[1] == kind]
        if not candidates:
            continue
        best = None
        for tpl in candidates:
            factor, _ = _scale_for(tpl, slot_kcal)
            meal = _build_meal(tpl, factor)
            sc = _score(tpl, meal, slot_kcal, prefs, recent, targets["protein_g"] * shares[slot])
            if best is None or sc > best[0]:
                best = (sc, meal)
        meal = best[1]
        meal.update(slot=slot, label=SLOT_LABEL[slot], target_kcal=round(slot_kcal), log_meal=LOG_MEAL[slot])
        recent.append(meal["template_id"])
        meals.append(meal)
    _boost_protein(meals, targets, prefs)
    _rebalance(meals, targets)
    _fine_tune(meals, targets)
    return _finish_day(meals, targets)


# Protein add-ons, tried in order of protein per kcal. (food, quantity, label)
ADDONS: list[tuple[str, float, str]] = [
    ("whey protein", 1, "a scoop of protein powder in water or milk"), ("soya chunks", 1, "a serving of soya chunks"),
    ("boiled egg", 2, "2 boiled eggs"), ("chicken breast", 1, "100 g grilled chicken"), ("greek yogurt", 1.5, "150 g Greek yogurt"),
    ("tofu", 1.5, "150 g tofu"), ("sprouts", 1.5, "a katori and a half of sprouts"), ("paneer", 0.5, "50 g paneer"), ("boiled chana", 1.5, "boiled chana"),
]


def _addon_ok(food: dict, prefs: dict) -> bool:
    fake = ("x", "snack", "x", [(food["name"], 1, None)], "")
    return _eligible(fake, prefs)


def _boost_protein(meals: list[dict], targets: dict, prefs: dict) -> None:
    """If the day is clearly short on protein, add up to two protein foods and scale other portions down to keep calories."""
    tpl_by_id = {t[0]: t for t in TEMPLATES}
    for _ in range(2):
        protein = sum(m["totals"]["protein_g"] for m in meals)
        if protein >= 0.92 * targets["protein_g"] or not meals:
            return
        used = {a["food"] for m in meals for a in m.get("addons", [])}
        options = [(FOODS[n]["protein_g"] * q * (food_db.unit_grams(FOODS[n], None) / FOODS[n]["serving_g"]) / max(FOODS[n]["kcal"] * q, 1), n, q, label)
                   for n, q, label in ADDONS if n not in used and _addon_ok(FOODS[n], prefs)]
        if not options:
            return
        _r, name, qty, label = max(options)
        food = FOODS[name]
        add = food_db.scale(food, qty * food["serving_g"])
        day_kcal = sum(m["totals"]["kcal"] for m in meals)
        shrink = max(0.8, (targets["kcal"] - add["kcal"]) / day_kcal) if day_kcal else 1.0
        _rescale(meals, shrink)
        target_meal = next((m for m in meals if m["slot"].startswith("snack")), meals[0])
        entry = {"food": name, "quantity": qty, "label": label}
        target_meal.setdefault("addons", []).append(entry)
        _apply_addon(target_meal, entry)


def _rescale(meals: list[dict], scale: float) -> None:
    tpl_by_id = {t[0]: t for t in TEMPLATES}
    for m in meals:
        addons = m.get("addons", [])
        rebuilt = _build_meal(tpl_by_id[m["template_id"]], m["factor"] * scale)
        m["items"], m["totals"], m["factor"] = rebuilt["items"], rebuilt["totals"], rebuilt["factor"]
        for a in addons:
            _apply_addon(m, a)


def _rebalance(meals: list[dict], targets: dict) -> None:
    """Nudge portions so the day lands within ~3% of the calorie target (add-on foods keep their size)."""
    for _ in range(3):
        total = sum(m["totals"]["kcal"] for m in meals)
        addon = sum(it["kcal"] for m in meals for it in m["items"] if it.get("addon"))
        base = total - addon
        if base <= 0:
            return
        scale = (targets["kcal"] - addon) / base
        if abs(scale - 1) <= 0.02:
            return
        _rescale(meals, max(0.75, min(1.3, scale)))


def _apply_addon(meal: dict, addon: dict) -> None:
    food = FOODS[addon["food"]]
    n = food_db.scale(food, addon["quantity"] * food["serving_g"])
    meal["items"].append(_item(food, addon["food"], addon["quantity"], None, n, addon=True))
    meal["totals"] = _totals(meal["items"])


STEP = {"piece": 0.5, "slice": 1.0, "scoop": 1.0}
TUNABLE = ("rice", "bread", "dal", "breakfast", "grain", "curry", "nonveg", "vegetable", "fruit", "dairy")


def _fine_tune(meals: list[dict], targets: dict) -> None:
    """Move single portions by one natural step (e.g. half a roti) until the day is within ~3% of the target."""
    target = targets["kcal"]
    aim = target * 1.015          # aim just above the target so a plan can never land below the intake floor
    for _ in range(14):
        total = sum(m["totals"]["kcal"] for m in meals)
        diff = aim - total
        if abs(diff) <= 0.015 * target:
            return
        best = None
        for m in meals:
            for it in m["items"]:
                if it.get("addon") or it["category"] not in TUNABLE:
                    continue
                food = FOODS[it["food"]]
                step = STEP.get(food["unit"], 0.25)
                q = it["quantity"] + (step if diff > 0 else -step)
                if q < step:
                    continue
                per = (food_db.unit_grams(food, None) if it["unit"] == food["unit"] else food_db.unit_grams(food, it["unit"])) or food["serving_g"]
                n = food_db.scale(food, q * per)
                change = n["kcal"] - it["kcal"]
                remaining = abs(diff - change)
                if best is None or remaining < best[0]:
                    best = (remaining, m, it, q, n, food)
        if best is None or best[0] >= abs(diff):
            return
        _r, m, it, q, n, food = best
        idx = m["items"].index(it)
        m["items"][idx] = _item(food, it["food"], q, it["unit"] if it["unit"] != food["unit"] else None, n)
        m["totals"] = _totals(m["items"])


def _finish_day(meals: list[dict], targets: dict) -> dict:
    totals = {k: sum(m["totals"][k] for m in meals) for k in ("kcal", "kcal_low", "kcal_high", "protein_g", "carbs_g", "fat_g", "fibre_g")}
    totals = {k: round(v, 1) if k.endswith("_g") else round(v) for k, v in totals.items()}
    micros: dict[str, float] = {}
    for m in meals:
        for it in m["items"]:
            for k, v in it["micros"].items():
                micros[k] = round(micros.get(k, 0.0) + v, 1)
    return {"meals": meals, "totals": totals, "micros": micros, "target_kcal": targets["kcal"], "protein_target_g": targets["protein_g"],
            "kcal_gap": totals["kcal"] - targets["kcal"], "protein_ok": totals["protein_g"] >= 0.85 * targets["protein_g"], "label": "estimate"}


def plan_week(targets: dict, prefs: dict | None = None, meals_per_day: int = 4, days: int = 7) -> dict:
    """Seven days of meals. `prefs`: diet_style, allergies[], dislikes[], likes[], must_include[], conditions{}, goal, menstruating, seed."""
    prefs = dict(prefs or {})
    prefs.setdefault("goal", targets.get("goal"))
    recent: list[str] = []
    week = []
    for i in range(max(1, min(days, 14))):
        prefs["seed"] = prefs.get("seed", 0)
        day = plan_day(targets, prefs, recent, meals_per_day)
        recent = recent + [m["template_id"] for m in day["meals"]]
        day["day"] = i + 1
        week.append(day)
    if not week or not week[0]["meals"]:
        return {"days": [], "ok": False, "reason": "No meals fit your diet style, allergies and dislikes. Loosen one of them and try again."}
    return {"days": week, "ok": True, "meals_per_day": meals_per_day, "label": "estimate",
            "summary": {"avg_kcal": round(sum(d["totals"]["kcal"] for d in week) / len(week)), "avg_protein_g": round(sum(d["totals"]["protein_g"] for d in week) / len(week), 1),
                        "variety": len({m["template_id"] for d in week for m in d["meals"]})}}


def swap_options(targets: dict, prefs: dict, current_template: str, slot: str, meals_per_day: int = 4, limit: int = 5, exclude: list[str] | None = None) -> list[dict]:
    """Alternatives for one slot that keep calories within about 5% of the slot target (with natural portions)."""
    shares = SLOT_SHARE.get(meals_per_day) or SLOT_SHARE[4]
    if slot not in shares:
        return []
    kind = "main" if slot.startswith("main") else "snack" if slot.startswith("snack") else slot
    slot_kcal = targets["kcal"] * shares[slot]
    out = []
    for tpl in TEMPLATES:
        if tpl[1] != kind or tpl[0] == current_template or tpl[0] in (exclude or []) or not _eligible(tpl, prefs):
            continue
        factor, _ = _scale_for(tpl, slot_kcal)
        meal = _build_meal(tpl, factor)
        err = abs(meal["totals"]["kcal"] - slot_kcal) / slot_kcal
        if err <= 0.05 and 0.7 <= factor <= 1.6:
            meal.update(slot=slot, label=SLOT_LABEL[slot], target_kcal=round(slot_kcal), log_meal=LOG_MEAL[slot])
            out.append((err - 0.002 * meal["totals"]["protein_g"], meal))
    out.sort(key=lambda t: t[0])
    return [m for _e, m in out[:limit]]


def grocery_list(week: dict, people: int = 1) -> dict[str, list[dict]]:
    """Weekly shopping list grouped by aisle. Cooked weights are converted to approximate raw weights; quantities are estimates."""
    people = max(1, min(people, 12))
    totals: dict[str, dict] = {}
    for day in week.get("days", []):
        for meal in day["meals"]:
            for it in meal["items"]:
                food = FOODS[it["food"]]
                raw = RAW_FACTOR.get(food["category"], 1.0)
                row = totals.setdefault(it["food"], {"food": it["food"], "grams": 0.0, "category": food["category"], "raw_factor": raw})
                row["grams"] += it["grams"] * raw * people
    aisles: dict[str, list[dict]] = {}
    for row in sorted(totals.values(), key=lambda r: r["food"]):
        grams = row["grams"]
        qty = f"{round(grams / 1000, 2)} kg" if grams >= 1000 else f"{round(grams / 10) * 10:.0f} g"
        aisles.setdefault(AISLE.get(row["category"], "Pantry"), []).append({"food": row["food"], "quantity": qty, "grams": round(grams),
                                                                           "note": "approximate raw weight" if row["raw_factor"] != 1.0 else None})
    return aisles


def explain(meal: dict, prefs: dict) -> str:
    likes = _words(prefs.get("likes") or [])
    liked = [it["food"] for it in meal["items"] if likes & _words([it["food"]])]
    base = f"About {meal['totals']['kcal']} kcal and {meal['totals']['protein_g']:g} g protein, sized to your daily plan."
    return base + (f" Includes {', '.join(liked)}, which you like." if liked else "")
