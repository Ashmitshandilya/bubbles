"""Hydration: daily goal, beverage factors, quick-add presets, progress-based reminders, streak and the "Bubbles oasis" garden.

Pure functions plus thin loaders. Targets come from ``nutrition_calc.hydration_target`` (weight, exercise minutes,
pregnancy/breastfeeding) and the constants in ``clinical_constants``. When ``condition_rules`` says the user is
fluid-restricted (heart failure, kidney disease, dialysis, cirrhosis, SIADH, hyponatraemia) NO target is shown, only a
clinician note, and no reminders or streak are produced.

Storage: every drink is a normal ``hydration`` tracker entry (``health_logs.save_domain``): ``volume`` = raw ml,
``type`` = beverage (kept as ``drink_type``), so the existing insights see it. Hydrating ml = volume x factor and is computed
when reading. The garden/streak state is the doc ``hydration_state`` / key ``garden`` (``total_ml``, ``met_dates``) so
rewards never shrink and are independent of the tracker's 200-row read cap.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import clinical_constants as K
import doc_store
import nutrition_calc as N
from health_logs import DOMAINS, list_domain
from wellness_common import InputError, fmt_hhmm, local_date_of, number

CLINICIAN_NOTE = ("Your care team may have given you a fluid plan. Bubbles doesn't show a drinking target for you. "
                  "Please follow your clinician's advice about how much to drink.")
SYNONYMS = {"green_tea": "tea", "black_tea": "tea", "chai": "tea", "cola": "soda", "soft_drink": "soda", "nariyal_pani": "coconut_water",
            "chaas": "buttermilk", "lassi": "buttermilk", "fruit_juice": "juice", "wine": "alcohol", "beer": "alcohol", "water": "water"}
PRESETS = [{"id": k, "ml": v, "label": lbl} for (k, v), lbl in zip(K.HYDRATION_PRESETS_ML.items(),
                                                                  ("Cup", "Glass", "Bottle 500 ml", "Bottle 750 ml", "Bottle 1 L"))]
GARDEN_CAPTIONS = {"seed": "A seed is waiting for its first drops.", "sprout": "A little sprout has appeared.",
                   "leaves": "Fresh leaves are unfolding.", "blossom": "Your garden is in blossom.",
                   "pond": "A small pond has formed in your garden.", "oasis": "You have grown a whole oasis."}


# --- inputs --------------------------------------------------------------------------------------------------------------

def normalize_type(value: Any) -> str:
    v = str(value or "water").strip().lower().replace(" ", "_").replace("-", "_")
    v = SYNONYMS.get(v, v)
    return v if v in K.BEVERAGE_HYDRATION_FACTOR else "other"


def check_volume(ml: Any) -> int:
    """A single log in ml. Above HYDRATION_SINGLE_LOG_MAX_ML it is refused as a typo."""
    n = number(ml, 0, 1e9, "amount", required=True)
    if n < K.HYDRATION_CUSTOM_MIN_ML:
        raise InputError(f"amount must be at least {K.HYDRATION_CUSTOM_MIN_ML:g} ml")
    if n > K.HYDRATION_SINGLE_LOG_MAX_ML:
        raise InputError(f"a single drink can't be more than {K.HYDRATION_SINGLE_LOG_MAX_ML:g} ml; please check the amount")
    return round(n)


def volume_from_body(body: dict) -> int:
    preset = body.get("preset")
    if preset not in (None, ""):
        key = str(preset).strip().lower()
        if key not in K.HYDRATION_PRESETS_ML:
            raise InputError("preset must be one of " + ", ".join(K.HYDRATION_PRESETS_ML))
        return int(K.HYDRATION_PRESETS_ML[key])
    return check_volume(body.get("ml", body.get("volume")))


# --- goal ----------------------------------------------------------------------------------------------------------------

def daily_goal(weight_kg: float | None, exercise_minutes: float = 0.0, pregnant: bool = False, breastfeeding: bool = False,
               fluid_restricted: bool = False) -> dict[str, Any]:
    """{goal_ml | None, base_ml, workout_bonus_ml, fluid_restricted, basis, message}. The goal is the clamped, rounded value from
    nutrition_calc; the workout bonus is simply what the day's exercise minutes added (workout days adapt automatically)."""
    if fluid_restricted:
        return {"goal_ml": None, "base_ml": None, "workout_bonus_ml": 0, "fluid_restricted": True, "basis": "none", "message": CLINICIAN_NOTE}
    exercise = 0.0
    try:
        exercise = max(0.0, float(exercise_minutes or 0))
    except (TypeError, ValueError):
        exercise = 0.0
    if weight_kg is None:
        base = int(K.HYDRATION_DEFAULT_ML)
        goal = int(round(min(K.HYDRATION_MAX_ML, K.HYDRATION_DEFAULT_ML + exercise * K.HYDRATION_ML_PER_EXERCISE_MIN) / 50.0) * 50)
        basis = "general"
        msg = "This is a general starting target. Add your weight in your profile for a more personal one."
    else:
        base = N.hydration_target(weight_kg, 0.0, pregnant, breastfeeding)
        goal = N.hydration_target(weight_kg, exercise, pregnant, breastfeeding)
        basis = "personal"
        msg = "A rough daily target for drinks. Thirst, heat and how you feel matter too."
    if goal > base:
        msg += f" Today's activity added about {goal - base} ml."
    return {"goal_ml": goal, "base_ml": base, "workout_bonus_ml": max(0, goal - base), "fluid_restricted": False, "basis": basis, "message": msg}


# --- totals --------------------------------------------------------------------------------------------------------------

def hydrating_ml(volume: float, drink_type: str | None) -> float:
    return float(volume) * K.BEVERAGE_HYDRATION_FACTOR[normalize_type(drink_type)]


def day_totals(entries: list[dict], day: str, tz_offset_min: int = 0) -> dict[str, Any]:
    """Raw and hydrating ml for one local calendar day, plus a per-beverage split."""
    raw = eff = 0.0
    by_type: dict[str, float] = {}
    used = []
    for e in entries:
        if local_date_of(e.get("date"), tz_offset_min) != day:
            continue
        try:
            vol = float(e.get("volume"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(vol) or vol <= 0:
            continue
        t = normalize_type(e.get("type"))
        raw += vol
        eff += vol * K.BEVERAGE_HYDRATION_FACTOR[t]
        by_type[t] = by_type.get(t, 0.0) + vol
        used.append({"id": e.get("id"), "time": e.get("date"), "ml": round(vol), "type": t})
    return {"raw_ml": round(raw), "effective_ml": round(eff), "by_type": {k: round(v) for k, v in by_type.items()}, "entries": used}


# --- reminders -----------------------------------------------------------------------------------------------------------

def reminder_plan(goal_ml: float | None, effective_ml: float, now_min: int, wake_min: int = 7 * 60, sleep_min: int = 22 * 60,
                  due_window_min: int = 60) -> dict[str, Any]:
    """Reminder slots every HYDRATION_REMINDER_EVERY_MIN inside waking hours, ending HYDRATION_REMINDER_BEFORE_SLEEP_MIN before sleep.
    A slot is 'needed' only when the user is behind the day's even pace by at least the tolerance, so reminders follow progress,
    stop at the goal and never nag. ``due_now`` is the latest needed slot within the last ``due_window_min`` minutes (an hour in the app's own view)."""
    base = {"enabled": False, "slots": [], "due_now": None, "next": None, "reason": None}
    if goal_ml is None:
        return {**base, "reason": "no_target"}
    if effective_ml >= goal_ml:
        return {**base, "reason": "goal_reached"}
    if sleep_min <= wake_min:   # waking window wraps midnight (night shift): keep it simple and quiet
        return {**base, "reason": "unsupported_hours"}
    cutoff = sleep_min - K.HYDRATION_REMINDER_BEFORE_SLEEP_MIN
    span = max(1, cutoff - wake_min)
    slots, t = [], wake_min + K.HYDRATION_REMINDER_EVERY_MIN
    while t <= cutoff:
        expected = goal_ml * min(1.0, (t - wake_min) / span)
        needed = effective_ml + K.HYDRATION_REMINDER_TOLERANCE_ML <= expected
        status = "past" if t < now_min else "upcoming"
        slots.append({"time": fmt_hhmm(t), "minutes": t, "expected_ml": round(expected), "needed": needed, "status": status})
        t += K.HYDRATION_REMINDER_EVERY_MIN
    due = [s for s in slots if s["needed"] and 0 <= now_min - s["minutes"] < due_window_min]
    nxt = next((s for s in slots if s["needed"] and s["minutes"] >= now_min), None)
    return {"enabled": True, "slots": slots, "due_now": due[-1]["time"] if due else None, "next": nxt["time"] if nxt else None, "reason": None}


# --- streak and garden ---------------------------------------------------------------------------------------------------

def streak(met_dates: list[str], today: date) -> dict[str, Any]:
    """Consecutive goal days. Today being unfinished never breaks it, and a break is described without blame."""
    met = set(met_dates)
    best = run = 0
    prev = None
    for d in sorted(met):
        cur = date.fromisoformat(d)
        run = run + 1 if prev is not None and cur - prev == timedelta(days=1) else 1
        best, prev = max(best, run), cur
    day = today if today.isoformat() in met else today - timedelta(days=1)
    current = 0
    while day.isoformat() in met:
        current += 1
        day -= timedelta(days=1)
    msg = f"{current} days in a row at your goal." if current >= 2 else "You reached your goal yesterday." if current == 1 else "Every day is a fresh start."
    return {"current": current, "best": best, "message": msg}


def garden(total_ml: float, days_met: int) -> dict[str, Any]:
    """Bubbles' oasis: a pure function of cumulative ml and goal days. It only ever grows."""
    levels = K.HYDRATION_GARDEN_LEVELS
    idx = max(i for i, (need, _n) in enumerate(levels) if days_met >= need)
    name = levels[idx][1]
    nxt = levels[idx + 1] if idx + 1 < len(levels) else None
    prev_need = levels[idx][0]
    return {"level": idx, "name": name, "caption": GARDEN_CAPTIONS.get(name, ""), "goal_days": int(days_met),
            "total_litres": round(max(0.0, total_ml) / 1000.0, 1), "next_level": nxt[1] if nxt else None,
            "days_to_next": (nxt[0] - days_met) if nxt else 0,
            "progress": round((days_met - prev_need) / (nxt[0] - prev_need), 2) if nxt else 1.0}


def new_state() -> dict[str, Any]:
    return {"total_ml": 0.0, "met_dates": []}


def add_ml(state: dict, effective_ml: float) -> dict:
    return {**state, "total_ml": round(float(state.get("total_ml") or 0) + max(0.0, effective_ml), 1)}


def mark_met(state: dict, day: str) -> dict:
    dates = list(state.get("met_dates") or [])
    if day not in dates:
        dates = sorted(dates + [day])[-400:]
    return {**state, "met_dates": dates}


# --- overview ------------------------------------------------------------------------------------------------------------

def overview(entries: list[dict], *, day: str, now_min: int | None, goal: dict, state: dict, tz_offset_min: int = 0,
             wake_min: int = 7 * 60, sleep_min: int = 22 * 60, today: str | None = None) -> dict[str, Any]:
    totals = day_totals(entries, day, tz_offset_min)
    goal_ml = goal["goal_ml"]
    is_today = today is None or day == today
    out: dict[str, Any] = {"date": day, "goal": goal, "raw_ml": totals["raw_ml"], "effective_ml": totals["effective_ml"],
                           "by_type": totals["by_type"], "entries": totals["entries"], "presets": PRESETS,
                           "beverage_factors": K.BEVERAGE_HYDRATION_FACTOR}
    if goal_ml is None:
        out.update(percent=None, remaining_ml=None, reminders=reminder_plan(None, 0, 0), streak=None, garden=None, message=goal["message"])
        return out
    pct = round(100 * totals["effective_ml"] / goal_ml)
    out["percent"] = min(pct, 100)
    out["remaining_ml"] = max(0, goal_ml - totals["effective_ml"])
    out["reminders"] = reminder_plan(goal_ml, totals["effective_ml"], now_min, wake_min, sleep_min) if is_today and now_min is not None \
        else {"enabled": False, "slots": [], "due_now": None, "next": None, "reason": "not_today"}
    met = list(state.get("met_dates") or [])
    if totals["effective_ml"] >= goal_ml and day not in met:
        met = sorted(met + [day])
    out["streak"] = streak(met, date.fromisoformat(today or day))
    out["garden"] = garden(float(state.get("total_ml") or 0), len(set(met)))
    if totals["effective_ml"] >= goal_ml:
        out["message"] = "You've reached today's drinks target. Nicely done; sip as you like from here."
    elif pct >= 60:
        out["message"] = "Good progress today."
    else:
        out["message"] = "A glass of water whenever you're ready."
    return out


# --- loaders -------------------------------------------------------------------------------------------------------------

def load_state(db: Any, uid: str) -> dict:
    return doc_store.get(db, uid, "hydration_state", "garden") or new_state()


def save_state(db: Any, uid: str, state: dict) -> None:
    doc_store.put(db, uid, "hydration_state", "garden", state)


def load_entries(db: Any, uid: str, days: int) -> list[dict]:
    return list_domain(db, "hydration", DOMAINS["hydration"], uid, days)["entries"]


def exercise_minutes_on(db: Any, uid: str, day: str, tz_offset_min: int = 0, days: int = 3) -> float:
    """Minutes of logged activity on a local day (activity tracker); 0 if unreadable."""
    try:
        entries = list_domain(db, "activity", DOMAINS["activity"], uid, days)["entries"]
    except Exception:  # noqa: BLE001 - a convenience input; the goal still works without it
        return 0.0
    total = 0.0
    for e in entries:
        if local_date_of(e.get("date"), tz_offset_min) == day:
            try:
                total += float(e.get("duration") or 0)
            except (TypeError, ValueError):
                pass
    return min(total, 600.0)
