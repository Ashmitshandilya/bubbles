"""plan_engine (daily targets) and diet_planner (weekly meals): safety invariants and behaviour."""
import random

import pytest

import clinical_constants as K
import diet_planner as D
import nutrition_calc as N
import plan_engine as P
from food_data import FOODS

BASE = dict(age=30, height_cm=165, weight_kg=78, target_weight_kg=68, formula_basis="female", activity_level="light")


def test_targets_basic_shape_and_label():
    t = P.build_targets(BASE)
    assert t["goal"] == "lose" and t["estimate"] is True and t["kcal"] >= t["floor_kcal"] == 1200
    assert t["review"]["status"] == K.REVIEW_STATUS and "not medical advice" in t["review"]["notice"]
    assert t["time_to_goal"]["weeks_high"] > t["time_to_goal"]["weeks_low"] > 0
    assert 0 < t["pace_kg_per_week"] <= 1.0 and t["water_ml"] and t["sleep_hours"] == [7.0, 9.0]


def test_review_banner_turns_off_only_with_the_env_flag(monkeypatch):
    monkeypatch.setenv("BUBBLES_CLINICALLY_REVIEWED", "true")
    assert P.build_targets(BASE)["review"] == {"reviewed": True, "status": "REVIEWED", "notice": None}


def test_goal_inference_and_maintenance():
    assert P.build_targets({**BASE, "target_weight_kg": 78})["goal"] == "maintain"
    gain = P.build_targets({**BASE, "weight_kg": 45, "target_weight_kg": 52})
    assert gain["goal"] == "gain" and gain["kcal"] > gain["tdee_kcal"]


def test_unsafe_targets_are_refused_politely():
    with pytest.raises(N.CalcError, match="healthy range"):
        P.build_targets({**BASE, "target_weight_kg": 40})
    with pytest.raises(N.CalcError):
        P.build_targets({**BASE, "weight_kg": None})
    with pytest.raises(N.CalcError):
        P.build_targets({**BASE, "height_cm": 20})


@pytest.mark.parametrize("situation,expected", [
    ({"age": 16}, "adults"), ({"pregnant": True}, "Pregnancy"), ({"breastfeeding": True}, "Pregnancy"),
    ({"conditions": ["pregnancy"]}, "Pregnancy"), ({"weight_kg": 47, "height_cm": 165, "target_weight_kg": 45}, "below the usual range"),
])
def test_no_deficit_situations_return_maintenance_with_a_note(situation, expected):
    t = P.build_targets({**BASE, "target_weight_kg": 60, **situation}) if "weight_kg" not in situation else P.build_targets({**BASE, **situation})
    assert t["goal"] == "maintain" and t["deficit_kcal"] == 0 and any(expected in n for n in t["notes"])


def test_condition_notes_and_water_suppression():
    t = P.build_targets({**BASE, "conditions": ["chronic kidney disease", "type 2 diabetes"], "medications": ["Ozempic"]})
    assert t["water_ml"] is None and any("water target" in n for n in t["notes"])
    assert any("GLP-1" in n for n in t["notes"]) and any("kidney" in n.lower() for n in t["notes"])
    assert t["protein_g_per_kg"] <= 0.9


def test_aggressive_pace_request_is_clamped():
    t = P.build_targets({**BASE, "pace_pct_per_week": 5})
    assert t["pace_kg_per_week"] <= 1.0 and t["limited_by"]


def test_day_budget_credits_half_of_exercise():
    t = P.build_targets(BASE)
    b = P.day_budget(t, 1000, 400)
    assert b["exercise_credit_kcal"] == 200 and b["budget_kcal"] == t["kcal"] + 200 and b["remaining_kcal"] == b["budget_kcal"] - 1000


def test_fuzz_targets_never_below_floor_or_above_caps():
    rng = random.Random(11)
    for _ in range(1500):
        w = rng.uniform(35, 180)
        prof = dict(age=rng.uniform(18, 85), height_cm=rng.uniform(140, 200), weight_kg=w, target_weight_kg=w * rng.uniform(0.6, 1.2),
                    formula_basis=rng.choice(["male", "female", "average"]), activity_level=rng.choice(list(K.ACTIVITY_FACTORS)),
                    pace_pct_per_week=rng.choice([None, 0.1, 0.5, 1, 3, 9]))
        try:
            t = P.build_targets(prof)
        except N.CalcError:
            continue
        assert t["kcal"] >= max(t["floor_kcal"], 1200) or t["goal"] == "gain"
        assert t["deficit_kcal"] <= K.MAX_DEFICIT_KCAL and t["pace_kg_per_week"] <= K.HARD_CAP_KG_PER_WEEK + 0.01


# --- diet planner -----------------------------------------------------------------------------------------

def test_every_template_food_exists_and_is_unique():
    ids = [t[0] for t in D.TEMPLATES]
    assert len(ids) == len(set(ids))
    for tpl in D.TEMPLATES:
        assert all(c[0] in FOODS for c in tpl[3]), tpl[0]


@pytest.mark.parametrize("prefs", [{}, {"diet_style": "vegan"}, {"diet_style": "jain"}, {"diet_style": "eggetarian"},
                                   {"diet_style": "vegetarian", "allergies": ["dairy", "peanut"]}, {"dislikes": ["paneer", "egg", "rajma"]}])
def test_week_plan_hits_calories_and_never_falls_below_target(prefs):
    t = P.build_targets(BASE)
    w = D.plan_week(t, prefs)
    assert w["ok"] and len(w["days"]) == 7
    for day in w["days"]:
        assert t["kcal"] <= day["totals"]["kcal"] <= t["kcal"] * 1.06
        assert day["totals"]["kcal_low"] < day["totals"]["kcal"] < day["totals"]["kcal_high"] and day["label"] == "estimate"
    assert w["summary"]["variety"] >= 12


def test_hard_filters_hold_for_every_meal():
    t = P.build_targets(BASE)
    vegan = D.plan_week(t, {"diet_style": "vegan"})
    for day in vegan["days"]:
        for meal in day["meals"]:
            for it in meal["items"]:
                assert FOODS[it["food"]]["diet"] == "V", it
    safe = D.plan_week(t, {"diet_style": "vegetarian", "allergies": ["dairy", "peanut", "gluten"]})
    for day in safe["days"]:
        for meal in day["meals"]:
            for it in meal["items"]:
                allergens = FOODS[it["food"]]["allergens"]
                assert not ({"dairy", "peanut", "gluten"} & set(allergens)), (it, allergens)
    disliked = D.plan_week(t, {"dislikes": ["egg", "chicken"]})
    for day in disliked["days"]:
        for meal in day["meals"]:
            assert not any("egg" in it["food"] or "chicken" in it["food"] for it in meal["items"])


def test_impossible_filters_say_so_instead_of_unsafe_food():
    t = P.build_targets(BASE)
    w = D.plan_week(t, {"diet_style": "vegan", "allergies": ["soy", "gluten", "nuts", "peanut", "sesame", "wheat"], "dislikes": ["rice", "dal", "oats", "poha", "banana", "apple", "idli"]})
    assert w["ok"] is False or all(not (set(FOODS[i["food"]]["allergens"]) & {"soy", "gluten", "peanut", "tree nut"}) for d in w["days"] for m in d["meals"] for i in m["items"])


def test_must_include_foods_appear():
    t = P.build_targets(BASE)
    w = D.plan_week(t, {"must_include": ["rajma"]})
    assert any(it["food"] == "rajma" for d in w["days"] for m in d["meals"] for it in m["items"])


def test_protein_is_boosted_toward_the_target():
    t = P.build_targets(BASE)
    w = D.plan_week(t, {})
    assert w["summary"]["avg_protein_g"] >= 0.9 * t["protein_g"]


def test_swap_options_stay_near_the_calorie_target_and_respect_filters():
    t = P.build_targets(BASE)
    w = D.plan_week(t, {"diet_style": "vegetarian"})
    meal = w["days"][0]["meals"][0]
    options = D.swap_options(t, {"diet_style": "vegetarian"}, meal["template_id"], meal["slot"])
    assert options and all(abs(o["totals"]["kcal"] - o["target_kcal"]) <= 0.06 * o["target_kcal"] for o in options)
    assert all(o["template_id"] != meal["template_id"] for o in options)
    assert D.swap_options(t, {}, "x", "nonsense") == []


def test_grocery_list_groups_and_scales_by_people():
    t = P.build_targets(BASE)
    w = D.plan_week(t, {})
    one, two = D.grocery_list(w, 1), D.grocery_list(w, 2)
    assert "Fresh produce" in one and "Grains & flours" in one
    total = lambda g: sum(i["grams"] for items in g.values() for i in items)
    assert 1.9 < total(two) / total(one) < 2.1


def test_plans_at_the_calorie_floor_never_go_below_it():
    rng = random.Random(3)
    for _ in range(40):
        prof = dict(age=rng.uniform(25, 70), height_cm=rng.uniform(145, 160), weight_kg=rng.uniform(45, 60), target_weight_kg=None,
                    formula_basis="female", activity_level="sedentary")
        t = P.build_targets(prof)
        w = D.plan_week(t, rng.choice([{}, {"diet_style": "vegan"}, {"diet_style": "jain"}]))
        for day in w["days"]:
            assert day["totals"]["kcal"] >= min(t["kcal"], 10**6) and day["totals"]["kcal"] >= 1190  # rounding of single portions only
