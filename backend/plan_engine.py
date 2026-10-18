"""The ONE place daily targets are computed (calories, macros, water, steps, sleep). Pure, deterministic.

Diet planner, calorie log, workout planner, Today and chat all read these numbers; no screen recomputes them.
Every output is clamped by clinical_constants, whatever the input, and carries the review notice until a clinician signs off.
"""
from __future__ import annotations

import os
from typing import Any

import clinical_constants as K
import condition_rules
import nutrition_calc as N

STEPS_BY_ACTIVITY = K.STEPS_BY_ACTIVITY
LOSS_GOALS = {"lose"}


def clinically_reviewed() -> bool:
    return os.environ.get("BUBBLES_CLINICALLY_REVIEWED", "").strip().lower() in {"1", "true", "yes"}


def review_banner() -> dict[str, Any]:
    reviewed = clinically_reviewed()
    return {"reviewed": reviewed, "status": "REVIEWED" if reviewed else K.REVIEW_STATUS, "notice": None if reviewed else K.REVIEW_NOTICE}


def normalise_profile(raw: dict | None) -> dict[str, Any]:
    """Coerce a stored/submitted profile into the fields the engine needs. Raises N.CalcError with a user-safe message."""
    p = dict(raw or {})
    age = p.get("age")
    if age in (None, "") and p.get("birth_date"):
        age = N.age_from_birth(p["birth_date"])
    out: dict[str, Any] = {
        "age": age, "height_cm": p.get("height_cm"), "weight_kg": p.get("weight_kg"), "target_weight_kg": p.get("target_weight_kg"),
        "formula_basis": N.basis(p.get("formula_basis") or p.get("sex")), "activity_level": str(p.get("activity_level") or "light").lower(),
        "diet_style": (p.get("diet_style") or "").lower() or None, "allergies": list(p.get("allergies") or []),
        "conditions": list(p.get("conditions") or []), "medications": list(p.get("medications") or []),
        "pregnant": bool(p.get("pregnant")), "breastfeeding": bool(p.get("breastfeeding")),
        "resistance_training": p.get("resistance_training", True) is not False, "pace_pct_per_week": p.get("pace_pct_per_week"),
        "exercise_min_per_week": p.get("exercise_min_per_week") or 0, "eating_concern": bool(p.get("eating_concern") or p.get("eating_disorder_history")),
    }
    if out["activity_level"] not in K.ACTIVITY_FACTORS:
        out["activity_level"] = "light"
    N.check_body(out["weight_kg"], out["height_cm"], out["age"], required=("weight_kg", "height_cm", "age"))
    out["age"], out["height_cm"], out["weight_kg"] = float(out["age"]), float(out["height_cm"]), float(out["weight_kg"])
    if out["target_weight_kg"] not in (None, ""):
        out["target_weight_kg"] = N.check_body(weight_kg=out["target_weight_kg"])["weight_kg"]
    else:
        out["target_weight_kg"] = None
    pace = out["pace_pct_per_week"]
    if pace not in (None, ""):
        try:
            pace = float(pace)
        except (TypeError, ValueError):
            raise N.CalcError("pace must be a number")
        out["pace_pct_per_week"] = min(max(pace, 0.0), 5.0) if pace == pace else None   # clamp; the engine caps it again to the safe limit
    else:
        out["pace_pct_per_week"] = None
    return out


def infer_goal(weight_kg: float, target_kg: float | None) -> str:
    if target_kg is None or abs(target_kg - weight_kg) < 0.5:
        return "maintain"
    return "lose" if target_kg < weight_kg else "gain"


def build_targets(profile: dict, *, extra_exercise_min_per_week: float | None = None) -> dict[str, Any]:
    """Daily targets for a profile. Never returns a calorie figure below the intake floor and never plans loss faster than the caps."""
    p = normalise_profile(profile)
    weight, height, age, basis = p["weight_kg"], p["height_cm"], p["age"], p["formula_basis"]
    rules = condition_rules.classify(p["conditions"], p["medications"])
    notes: list[str] = []
    goal = infer_goal(weight, p["target_weight_kg"])
    cur_bmi = N.bmi(weight, height)

    # situations where we do not plan any energy deficit at all
    no_deficit = None
    if age < K.MIN_ADULT_AGE:
        no_deficit = "Weight-loss plans are only for adults. These numbers are for steady, healthy growth and activity."
    elif p["pregnant"] or rules["pregnancy_hint"] or p["breastfeeding"]:
        no_deficit = "Pregnancy and breastfeeding need personal advice from your midwife, doctor or dietitian. Bubbles does not plan a calorie deficit."
    elif p["eating_concern"] and goal == "lose":
        no_deficit = "Bubbles is keeping these numbers gentle, with no weight-loss target. A doctor or counsellor who knows about eating can help you find what feels right."
    elif cur_bmi < K.MIN_START_BMI_FOR_LOSS and goal == "lose":
        no_deficit = "Your weight is already below the usual range, so Bubbles does not plan weight loss. Please talk to a doctor or dietitian."
    if goal == "lose" and not no_deficit and p["target_weight_kg"] is not None and N.bmi(p["target_weight_kg"], height) < K.MIN_TARGET_BMI:
        low, _ = N.healthy_weight_range(height)
        raise N.CalcError(f"A target below about {low:.0f} kg is under the usual healthy range for your height, so Bubbles will not plan toward it.")
    if no_deficit:
        notes.append(no_deficit)
        goal = "maintain"
    if goal == "gain" and cur_bmi >= K.BMI_OVERWEIGHT:
        notes.append("Your current weight is already above the usual range; Bubbles is keeping calories at maintenance.")
        goal = "maintain"

    activity = p["activity_level"]
    tdee = N.tdee(weight, height, age, basis, activity)
    pct = p["pace_pct_per_week"] if p["pace_pct_per_week"] is not None else sum(K.PACE_PCT_PER_WEEK) / 2
    desired = weight * pct / 100.0
    energy = N.daily_target(tdee, desired, basis, weight, goal=goal)
    macros = N.macros(energy["kcal"], weight, height, p["resistance_training"], kidney_caution=rules["kidney"])
    exercise_min = extra_exercise_min_per_week if extra_exercise_min_per_week is not None else p["exercise_min_per_week"]
    water = None if rules["fluid_restricted"] else N.hydration_target(weight, exercise_min / 7.0, p["pregnant"], p["breastfeeding"])
    if rules["fluid_restricted"]:
        notes.append("Because of a heart, kidney or fluid-related condition on your record, Bubbles does not suggest a water target. Ask your doctor how much to drink.")
    if energy["limited_by"]:
        notes.append("Your pace was limited by: " + ", ".join(energy["limited_by"]) + ".")
    if rules["kidney"]:
        notes.append("Kidney disease on your record: Bubbles does not set a high-protein target. Please ask your doctor or dietitian.")
    if rules["glp1"]:
        notes.append("You use a GLP-1 medicine: protein and fluids matter, and your prescriber decides about doses. Bubbles never suggests dose changes.")
    if age >= K.CAUTION_AGE:
        notes.append("Because of your age, please run big diet or exercise changes past your doctor.")
    for caution in rules["cautions"]:
        if caution not in ("GLP-1 medicine",):
            notes.append(f"{caution.capitalize()} is on your record. The plan adapts, and your doctor or dietitian can tune it further.")

    out: dict[str, Any] = {
        "goal": goal, "formula_basis": basis, "activity_level": activity, "age": round(age), "bmi": N.bmi_info(weight, height),
        "bmr_kcal": round(N.bmr(weight, height, age, basis)), "tdee_kcal": round(tdee), "kcal": energy["kcal"], "deficit_kcal": energy["deficit"],
        "pace_kg_per_week": energy["pace_kg_per_week"], "limited_by": energy["limited_by"], "at_floor": energy["at_floor"],
        "floor_kcal": round(N.intake_floor(basis)), **macros, "water_ml": water, "steps": STEPS_BY_ACTIVITY[activity],
        "sleep_hours": [K.SLEEP_HOURS_ADULT[0], K.SLEEP_HOURS_ADULT[1]] if age >= 18 else [K.SLEEP_HOURS_TEEN[0], K.SLEEP_HOURS_TEEN[1]],
        "exercise": {"moderate_min_week": list(K.WHO_MODERATE_MIN_PER_WEEK), "strength_days_min": K.WHO_STRENGTH_DAYS_MIN},
        "notes": notes, "rules": {k: v for k, v in rules.items() if k in ("blocking", "cautions", "glp1", "fluid_restricted", "kidney")},
        "review": review_banner(), "estimate": True, "healthy_weight_range_kg": list(N.healthy_weight_range(height)),
    }
    if goal in ("lose", "gain") and p["target_weight_kg"] is not None and energy["pace_kg_per_week"] > 0:
        out["time_to_goal"] = N.time_to_goal(weight, p["target_weight_kg"], energy["pace_kg_per_week"])
    out["target_weight_kg"] = p["target_weight_kg"]
    out["current_weight_kg"] = weight
    return out


def day_budget(targets: dict, eaten_kcal: float, exercise_kcal_estimated: float = 0.0) -> dict[str, Any]:
    """Remaining calories for the day. Only half of estimated exercise burn is added back (EXERCISE_CALORIE_CREDIT)."""
    credit = min(max(0.0, exercise_kcal_estimated) * K.EXERCISE_CALORIE_CREDIT, K.EXERCISE_CREDIT_MAX_KCAL)
    budget = targets["kcal"] + credit
    return {"budget_kcal": round(budget), "eaten_kcal": round(eaten_kcal), "remaining_kcal": round(budget - eaten_kcal),
            "exercise_credit_kcal": round(credit), "over": eaten_kcal > budget, "label": "estimate"}
