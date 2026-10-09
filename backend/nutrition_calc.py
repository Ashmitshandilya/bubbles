"""Pure nutrition / energy calculators. No I/O. Every limit comes from clinical_constants.

All outputs that are estimates carry a range; nothing here diagnoses. Inputs are validated and clamped so the
functions can never return NaN/inf or an unsafe number, whatever they are given.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Sequence

import clinical_constants as K


class CalcError(ValueError):
    """Bad input (message is safe to show the user)."""


def _finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CalcError(f"{label} must be a number")
    if not math.isfinite(number):
        raise CalcError(f"{label} must be a finite number")
    return number


def check_body(weight_kg: Any = None, height_cm: Any = None, age: Any = None, required: tuple[str, ...] = ()) -> dict[str, float]:
    """Validate against the plausible ranges; returns floats. ``required`` names values that may not be missing."""
    out: dict[str, float] = {}
    for label, value, (lo, hi) in (("weight_kg", weight_kg, K.MIN_PLAUSIBLE["weight_kg"]),
                                   ("height_cm", height_cm, K.MIN_PLAUSIBLE["height_cm"]),
                                   ("age", age, K.MIN_PLAUSIBLE["age"])):
        if value is None:
            if label in required:
                raise CalcError(f"{label} is required")
            continue
        number = _finite(value, label)
        if not lo <= number <= hi:
            raise CalcError(f"{label} must be between {lo:g} and {hi:g}")
        out[label] = number
    return out


def age_from_birth(birth_date: str | date | None, today: date | None = None) -> int | None:
    if not birth_date:
        return None
    try:
        born = birth_date if isinstance(birth_date, date) else date.fromisoformat(str(birth_date)[:10])
    except ValueError:
        return None
    today = today or date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years if 0 <= years <= 120 else None


def basis(value: Any) -> str:
    v = str(value or "average").strip().lower()
    return v if v in K.FORMULA_BASES else "average"


def bmr(weight_kg: float, height_cm: float, age: float, formula_basis: str = "average") -> float:
    """Mifflin-St Jeor resting energy, kcal/day."""
    check_body(weight_kg, height_cm, age, required=("weight_kg", "height_cm", "age"))
    return K.MIFFLIN_KG * weight_kg + K.MIFFLIN_CM * height_cm - K.MIFFLIN_AGE * age + K.MIFFLIN_CONSTANT[basis(formula_basis)]


def activity_factor(level: Any) -> float:
    return K.ACTIVITY_FACTORS.get(str(level or "light").strip().lower(), K.ACTIVITY_FACTORS["light"])


def tdee(weight_kg: float, height_cm: float, age: float, formula_basis: str = "average", activity: str = "light") -> float:
    return bmr(weight_kg, height_cm, age, formula_basis) * activity_factor(activity)


def bmi(weight_kg: float, height_cm: float) -> float:
    check_body(weight_kg, height_cm, required=("weight_kg", "height_cm"))
    return weight_kg / ((height_cm / 100.0) ** 2)


def bmi_band(value: float) -> str:
    if value < K.BMI_UNDERWEIGHT:
        return "below the usual range"
    if value < K.BMI_OVERWEIGHT:
        return "in the usual range"
    if value < K.BMI_OBESE:
        return "above the usual range"
    return "well above the usual range"


def bmi_info(weight_kg: float, height_cm: float) -> dict[str, Any]:
    value = bmi(weight_kg, height_cm)
    asian = ("below" if value < K.BMI_UNDERWEIGHT else "usual" if value < K.BMI_ASIAN_OVERWEIGHT
             else "above" if value < K.BMI_ASIAN_OBESE else "well above")
    return {"bmi": round(value, 1), "who_band": bmi_band(value), "asian_cutoff_band": asian,
            "note": "BMI is a rough screen. It ignores muscle, age, sex and ethnicity and says nothing about your health on its own."}


def weight_for_bmi(target_bmi: float, height_cm: float) -> float:
    return target_bmi * (height_cm / 100.0) ** 2


def healthy_weight_range(height_cm: float) -> tuple[float, float]:
    return (round(weight_for_bmi(K.BMI_UNDERWEIGHT, height_cm), 1), round(weight_for_bmi(K.BMI_OVERWEIGHT - 0.1, height_cm), 1))


def reference_weight(weight_kg: float, height_cm: float) -> float:
    """Weight protein is based on: actual weight, or an adjusted weight when BMI >= 30."""
    if bmi(weight_kg, height_cm) < K.BMI_OBESE:
        return weight_kg
    ideal = weight_for_bmi(K.IDEAL_BMI_FOR_REFERENCE, height_cm)
    return ideal + K.OBESE_REFERENCE_WEIGHT_WEIGHT * (weight_kg - ideal)


def intake_floor(formula_basis: str) -> float:
    return max(K.INTAKE_FLOOR_KCAL[basis(formula_basis)], K.INTAKE_FLOOR_ABSOLUTE_KCAL)


def weekly_pace_cap_kg(weight_kg: float) -> float:
    """Largest weekly loss we would ever plan or accept, in kg."""
    return min(K.HARD_CAP_KG_PER_WEEK, weight_kg * K.HARD_CAP_PCT_PER_WEEK / 100.0)


def daily_target(tdee_kcal: float, desired_weekly_kg: float, formula_basis: str, weight_kg: float, goal: str = "lose") -> dict[str, Any]:
    """Clamp a desired pace into a safe calorie target.

    Returns {kcal, deficit, pace_kg_per_week (achieved, positive number), limited_by: [...], at_floor: bool}.
    The result is >= the intake floor for loss/maintain goals under every input. A deficit is never created when
    maintenance energy is already at or below the floor.
    """
    tdee_kcal = _finite(tdee_kcal, "tdee")
    desired = max(0.0, _finite(desired_weekly_kg, "pace"))
    floor = intake_floor(formula_basis)
    limited: list[str] = []
    if goal == "maintain":
        return {"kcal": round(max(tdee_kcal, floor)), "deficit": 0, "pace_kg_per_week": 0.0, "limited_by": [], "at_floor": tdee_kcal <= floor}
    if goal == "gain":
        pace = min(desired, K.MAX_GAIN_KG_PER_WEEK)
        surplus = min(pace * K.KCAL_PER_KG_BODY_MASS / 7.0, K.MAX_SURPLUS_KCAL)
        return {"kcal": round(tdee_kcal + surplus), "deficit": -round(surplus), "pace_kg_per_week": round(surplus * 7 / K.KCAL_PER_KG_BODY_MASS, 2),
                "limited_by": ["gain pace cap"] if pace < desired else [], "at_floor": False}
    pace_cap = weekly_pace_cap_kg(weight_kg)
    if desired > pace_cap:
        desired = pace_cap
        limited.append("weekly pace cap")
    deficit = desired * K.KCAL_PER_KG_BODY_MASS / 7.0
    if deficit > K.MAX_DEFICIT_PCT_OF_TDEE * tdee_kcal:
        deficit = K.MAX_DEFICIT_PCT_OF_TDEE * tdee_kcal
        limited.append("25% of daily energy use")
    if deficit > K.MAX_DEFICIT_KCAL:
        deficit = K.MAX_DEFICIT_KCAL
        limited.append("1000 kcal/day cap")
    kcal = tdee_kcal - deficit
    at_floor = False
    if kcal < floor:  # never plan below the floor, even when maintenance energy itself is under it
        kcal = floor
        at_floor = True
        limited.append("minimum safe intake")
    deficit_final = max(0.0, tdee_kcal - kcal)
    return {"kcal": round(kcal), "deficit": round(deficit_final), "pace_kg_per_week": round(deficit_final * 7 / K.KCAL_PER_KG_BODY_MASS, 2),
            "limited_by": limited, "at_floor": at_floor}


def macros(kcal: float, weight_kg: float, height_cm: float, resistance_training: bool = True, kidney_caution: bool = False) -> dict[str, Any]:
    """Protein/fat/carb/fibre targets in grams for a calorie target."""
    ref = reference_weight(weight_kg, height_cm)
    per_kg = K.PROTEIN_G_PER_KG_TRAINING if resistance_training else K.PROTEIN_G_PER_KG[0]
    if kidney_caution:
        per_kg = K.PROTEIN_G_PER_KG_KIDNEY_NOTE
    protein = per_kg * ref
    protein = min(protein, 0.35 * kcal / 4.0)           # protein never above 35% of energy
    fat = max(K.FAT_MIN_PCT_KCAL * kcal / 9.0, min(K.FAT_MAX_PCT_KCAL * kcal / 9.0, 0.28 * kcal / 9.0))
    carbs = max(0.0, (kcal - protein * 4.0 - fat * 9.0) / 4.0)
    return {"protein_g": round(protein), "fat_g": round(fat), "carbs_g": round(carbs), "fibre_g": round(sum(K.FIBRE_G_PER_DAY) / 2),
            "protein_g_per_kg": round(protein / ref, 2), "sodium_limit_mg": K.SODIUM_LIMIT_MG}


def hydration_target(weight_kg: float, exercise_minutes: float = 0.0, pregnant: bool = False, breastfeeding: bool = False) -> int:
    """Rough daily drinks target in ml, clamped to the min/max."""
    ml = weight_kg * K.HYDRATION_ML_PER_KG + max(0.0, exercise_minutes) * K.HYDRATION_ML_PER_EXERCISE_MIN
    ml += K.HYDRATION_PREGNANCY_ADD_ML if pregnant else 0.0
    ml += K.HYDRATION_BREASTFEEDING_ADD_ML if breastfeeding else 0.0
    return int(round(min(K.HYDRATION_MAX_ML, max(K.HYDRATION_MIN_ML, ml)) / 50.0) * 50)


def met_burn(activity: str, minutes: float, weight_kg: float) -> dict[str, Any]:
    """Estimated kcal for an activity (MET x kg x hours), as a range, and the portion credited to the food budget."""
    met = K.MET_VALUES.get(str(activity).strip().lower().replace(" ", "_"))
    if met is None:
        raise CalcError("unknown activity")
    minutes = max(0.0, min(_finite(minutes, "minutes"), 1440.0))
    kcal = met * weight_kg * minutes / 60.0
    return {"activity": activity, "met": met, "kcal": round(kcal), "kcal_low": round(kcal * 0.8), "kcal_high": round(kcal * 1.2),
            "credited_kcal": round(kcal * K.EXERCISE_CALORIE_CREDIT), "label": "estimate"}


def time_to_goal(current_kg: float, target_kg: float, weekly_kg: float) -> dict[str, Any]:
    """Weeks to goal as a RANGE (never a single date). weekly_kg is the planned pace (positive)."""
    gap = abs(current_kg - target_kg)
    if gap < 0.05:
        return {"weeks_low": 0, "weeks_high": 0, "gap_kg": 0.0}
    pace = max(0.05, weekly_kg)
    # real-world pace is usually below plan: assume between 65% and 100% of plan
    return {"weeks_low": math.ceil(gap / pace), "weeks_high": math.ceil(gap / (pace * 0.65)), "gap_kg": round(gap, 1)}


def weight_trend(points: Sequence[tuple[str, float]], alpha: float = K.TREND_SMOOTHING_ALPHA) -> list[dict[str, Any]]:
    """Exponentially weighted trend over (iso date, kg) points, oldest first. Ignores non-finite/implausible points."""
    clean = []
    for day, kg in sorted(points, key=lambda p: p[0]):
        try:
            kg = float(kg)
        except (TypeError, ValueError):
            continue
        if math.isfinite(kg) and K.MIN_PLAUSIBLE["weight_kg"][0] <= kg <= K.MIN_PLAUSIBLE["weight_kg"][1]:
            clean.append((str(day)[:10], kg))
    out: list[dict[str, Any]] = []
    trend: float | None = None
    for day, kg in clean:
        trend = kg if trend is None else trend + alpha * (kg - trend)
        out.append({"date": day, "weight_kg": round(kg, 2), "trend_kg": round(trend, 2)})
    return out


def trend_rate_kg_per_week(trend: Sequence[dict[str, Any]], window_days: int = 14) -> float | None:
    """Slope of the smoothed trend over the last `window_days` (kg/week, negative = losing). None when too little data."""
    if len(trend) < 2:
        return None
    last = date.fromisoformat(trend[-1]["date"])
    recent = [p for p in trend if (last - date.fromisoformat(p["date"])).days <= window_days]
    if len(recent) < 2:
        return None
    first = recent[0]
    span = (last - date.fromisoformat(first["date"])).days
    if span < 5:
        return None
    return round((recent[-1]["trend_kg"] - first["trend_kg"]) / span * 7.0, 3)


def estimate_expenditure(avg_intake_kcal: float, trend_change_kg: float, days: int) -> float | None:
    """Observed daily energy use = intake - (change in body mass x 7700 / days). None when too little data."""
    if days < 7 or not math.isfinite(avg_intake_kcal) or not math.isfinite(trend_change_kg):
        return None
    return avg_intake_kcal - trend_change_kg * K.KCAL_PER_KG_BODY_MASS / days
