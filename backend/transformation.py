"""Strict Transformation mode: screening, plan creation, daily view, weekly adaptive check-in, safety monitors, lifecycle.

Pure functions over plain dicts (persistence lives in fitness_api via doc_store). Everything here enforces
clinical_constants; the UI is never trusted: ``start`` re-runs ``screen`` on the server.
Tone: supportive, never shaming. Nothing here diagnoses; every refusal points to a clinician or a gentler plan.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import clinical_constants as K
import condition_rules
import diet_planner
import exercise_planner
import nutrition_calc as N
import plan_engine

CLEARANCE_VALID_DAYS = K.CLEARANCE_VALID_DAYS
STRICT_DEFAULT_PACE_PCT = K.PACE_PCT_PER_WEEK[1]   # strict mode starts at the top of the default band (still under the hard cap)


# ---------------------------------------------------------------------------------------------------
# screening
# ---------------------------------------------------------------------------------------------------

def _exclusion(code: str, label: str, message: str, clearable: bool, area: str | None = None) -> dict:
    """``area`` names what a clinician's go-ahead must cover for this exclusion to be lifted (None = cannot be lifted by a note)."""
    return {"code": code, "label": label, "message": message, "clearable": clearable, "area": area if clearable else None}


CLEARABLE_AREAS = tuple(list(K.STRICT_BLOCKING_CONDITIONS) + list(K.STRICT_BLOCKING_MEDICATIONS) + ["age", "surgery_injury", "exercise"])


def clearance_active(profile: dict, area: str | None = None, today: date | None = None) -> bool:
    """True if the user recorded that a clinician approved this plan (dated; expires after a year)."""
    ack = profile.get("clinician_clearance") or {}
    if not ack.get("cleared"):
        return False
    try:
        given = date.fromisoformat(str(ack.get("date"))[:10])
    except ValueError:
        return False
    today = today or date.today()
    if not 0 <= (today - given).days <= CLEARANCE_VALID_DAYS:
        return False
    areas = ack.get("areas")
    if not isinstance(areas, list) or not areas:      # a clearance must name what it covers; a blanket "cleared" opens nothing
        return False
    return area is None or area in areas


def screen(profile: dict, scoff: list[bool] | None, *, months_since_period: float | None = None, red_flag_days_ago: int | None = None,
           recent_surgery_or_injury: bool = False, safety_pause_days_ago: int | None = None, today: date | None = None) -> dict[str, Any]:
    """Decide whether strict mode may start. ``profile`` is the body profile (age, weight, height, target, conditions, ...)."""
    today = today or date.today()
    ex: list[dict] = []
    cautions: list[str] = []
    cleared_used: list[str] = []
    try:
        p = plan_engine.normalise_profile(profile)
    except N.CalcError as err:
        return {"decision": "incomplete", "exclusions": [], "cautions": [], "message": str(err), "alternative": "complete_profile", "scoff_positive": False}
    rules = condition_rules.classify(p["conditions"], p["medications"])
    age, weight, height, target = p["age"], p["weight_kg"], p["height_cm"], p["target_weight_kg"]

    if age < K.MIN_ADULT_AGE:
        ex.append(_exclusion("under_18", "Under 18", "Strict plans are only for adults. A growing body needs steady fuel. Bubbles can still help you eat well and enjoy movement, and a doctor or school nurse can guide any weight questions.", False))
    if p["pregnant"] or p["breastfeeding"] or profile.get("trying_to_conceive") or rules["pregnancy_hint"]:
        ex.append(_exclusion("pregnancy", "Pregnancy, breastfeeding or trying to conceive", "Your body needs extra care right now, so Bubbles will not plan a calorie deficit. Your midwife, doctor or dietitian is the right guide.", False))
    scoff_yes = sum(1 for a in (scoff or []) if a is True)
    scoff_known = scoff is not None and len(scoff) >= len(K.SCOFF_QUESTIONS)
    ed_history = "eating disorder" in rules["blocking"] or bool(profile.get("eating_disorder_history"))
    if not scoff_known:
        ex.append(_exclusion("scoff_missing", "A few questions first", "Please answer the five short questions about eating so Bubbles can keep you safe.", False))
    elif scoff_yes >= K.SCOFF_POSITIVE_AT or ed_history:
        ex.append(_exclusion("eating_concern", "Eating-related worries", "Thank you for being honest. Because food feels hard right now, a strict plan could do more harm than good. Please talk with a doctor or a mental-health professional who knows about eating. Bubbles can offer gentle, no-numbers support.", False))
    cur_bmi = N.bmi(weight, height)
    if target is None:
        ex.append(_exclusion("no_target", "Choose a target", "Pick a target weight first.", False))
    else:
        if N.bmi(target, height) < K.MIN_TARGET_BMI:
            ex.append(_exclusion("target_low", "Target weight too low", "That target is below the usual healthy range for your height, so Bubbles will not plan toward it. A doctor or dietitian can help set a safe goal.", False))
        if target >= weight - 0.5:
            ex.append(_exclusion("not_loss", "Strict mode is for weight loss", "Your target is not below your current weight. Bubbles can build a gentle maintenance or gain plan instead.", False))
    if cur_bmi < K.MIN_START_BMI_FOR_LOSS:
        ex.append(_exclusion("underweight", "Weight already low", "Your weight is already below the usual range, so Bubbles will not plan weight loss. Please talk to a doctor or dietitian.", False))
    if months_since_period is not None and months_since_period >= K.SAFETY_MISSED_PERIOD_MONTHS and not (p["pregnant"] or rules["pregnancy_hint"]):
        ex.append(_exclusion("missed_periods", "Missed periods", "Missing periods for three months or more can mean your body is short of energy. Please see a doctor before any strict plan.", False))
    if red_flag_days_ago is not None and 0 <= red_flag_days_ago <= K.RED_FLAG_LOOKBACK_DAYS:
        ex.append(_exclusion("recent_red_flag", "A recent warning symptom", f"You reported a warning symptom in the last {K.RED_FLAG_LOOKBACK_DAYS} days. Please see a doctor first. Bubbles will be here when you are ready.", False))
    if safety_pause_days_ago is not None and 0 <= safety_pause_days_ago < K.SAFETY_COOLDOWN_DAYS:
        ex.append(_exclusion("recent_safety_pause", "A recent safety pause", f"Bubbles paused a plan for your safety in the last {K.SAFETY_COOLDOWN_DAYS} days. Please rest, eat well, and check in with a clinician before starting again.", False))
    if age >= K.MAX_AGE_WITHOUT_CLEARANCE and not clearance_active(profile, "age", today):
        ex.append(_exclusion("age_70", "Age 70 or over", "At your age a doctor should agree to a strict plan first. If they have, you can record that.", True, "age"))
    if recent_surgery_or_injury or "recent surgery or injury" in rules["blocking"]:
        if not clearance_active(profile, "surgery_injury", today):
            ex.append(_exclusion("surgery_injury", "Recent surgery or injury", "Please wait until your doctor or physiotherapist says you are ready.", True, "surgery_injury"))

    for label in rules["blocking"]:
        if label in ("eating disorder", "pregnancy or breastfeeding", "recent surgery or injury"):
            continue
        area = label
        if not clearance_active(profile, area, today):
            ex.append(_exclusion("condition:" + label.lower().replace(" ", "_"), label.capitalize(), f"{label.capitalize()} is on your record. A strict plan needs your doctor's agreement first. If they have approved it, you can record that.", True, label))
        else:
            cleared_used.append(label)
    for label in rules["cautions"]:
        cautions.append(label)
    if age >= K.CAUTION_AGE:
        cautions.append("age over 60")
    cautions = list(dict.fromkeys(cautions))

    if ex:
        decision = "refused"
        kinds = {e["code"] for e in ex}
        alt = ("support" if "eating_concern" in kinds else "clinician" if any(e["clearable"] or e["code"] in ("missed_periods",) for e in ex) else "gentle")
        if "scoff_missing" in kinds and len(kinds) == 1:
            decision, alt = "incomplete", "answer_questions"
    else:
        decision, alt = ("allowed_with_cautions" if cautions else "allowed"), None
    return {"decision": decision, "exclusions": ex, "cautions": cautions, "alternative": alt, "scoff_positive": scoff_yes >= K.SCOFF_POSITIVE_AT, "cleared_areas": cleared_used,
            "bmi": round(cur_bmi, 1), "gentle_available": decision == "refused" and alt in ("gentle", "clinician"),
            "message": ("You can start. Here is what to expect." if not ex else "Strict mode is not right for you at the moment. Here is why, and what Bubbles can do instead.")}


# ---------------------------------------------------------------------------------------------------
# preview / start
# ---------------------------------------------------------------------------------------------------

def commit_text(floor_kcal: float, pace_cap_kg: float) -> list[str]:
    return [
        "This plan is an estimate based on what you told Bubbles. Real results vary and may be slower.",
        f"Your daily calories will not go below {round(floor_kcal)}, and your loss will not be planned faster than about {pace_cap_kg:.1f} kg a week.",
        "Stop and talk to a doctor if you notice: " + "; ".join(K.PLAN_PAUSE_SYMPTOMS) + ".",
        "Bubbles will pause the plan if it sees warning signs. Pausing is normal and not a failure.",
        "This is not medical advice and does not replace your doctor or dietitian.",
    ]


def preview(profile: dict, selections: dict | None = None) -> dict[str, Any]:
    """Targets, a diet week and a workout week for the chosen foods / equipment. Does not save anything."""
    selections = selections or {}
    pace = selections.get("pace_pct_per_week") or STRICT_DEFAULT_PACE_PCT
    p = {**profile, "pace_pct_per_week": pace}
    targets = plan_engine.build_targets(p)
    prefs = {"diet_style": selections.get("diet_style") or profile.get("diet_style"), "allergies": profile.get("allergies") or [],
             "dislikes": selections.get("dislikes") or profile.get("dislikes") or [], "likes": selections.get("likes") or profile.get("likes") or [],
             "must_include": selections.get("foods") or [], "goal": targets["goal"],
             "conditions": condition_rules.classify(profile.get("conditions"), profile.get("medications")), "menstruating": bool(profile.get("menstruating"))}
    meals = int(selections.get("meals_per_day") or 4)
    diet = diet_planner.plan_week(targets, prefs, meals_per_day=meals if meals in (3, 4, 5) else 4)
    exercise = None
    screen_result = selections.get("exercise_screen")
    if screen_result:
        exercise = exercise_planner.plan_week(
            {**profile, "weight_kg": targets["current_weight_kg"], "age": targets["age"]}, days_per_week=int(selections.get("days_per_week") or 4),
            minutes=int(selections.get("session_minutes") or 40), equipment=selections.get("equipment") or "none", level=int(selections.get("level") or 1),
            screen_result=screen_result, injuries=selections.get("injuries") or [])
    return {"targets": targets, "diet": diet, "exercise": exercise, "good_day": good_day(targets, exercise),
            "commit_text": commit_text(targets["floor_kcal"], N.weekly_pace_cap_kg(targets["current_weight_kg"])), "pause_symptoms": list(K.PLAN_PAUSE_SYMPTOMS)}


def good_day(targets: dict, exercise: dict | None) -> list[str]:
    water = f"about {round(targets['water_ml'] / 250)} glasses of water" if targets.get("water_ml") else "water as your doctor advises"
    lines = [f"Eat around {targets['kcal']} kcal with about {targets['protein_g']} g protein. Close is good enough.", f"Drink {water}.",
             f"Aim for about {targets['steps']:,} steps.", f"Sleep {targets['sleep_hours'][0]:g} to {targets['sleep_hours'][1]:g} hours."]
    if exercise and exercise.get("ok"):
        lines.append(f"Move on {len(exercise['sessions'])} days this week. Rest days count too.")
    lines.append("A day off-plan is normal. Just carry on with the next meal.")
    return lines


def make_plan(profile: dict, selections: dict, screening: dict, acknowledged: bool, today: date | None = None) -> dict[str, Any]:
    """Create the saved plan document. Raises ValueError if screening does not allow it or the user did not acknowledge."""
    today = today or date.today()
    if screening.get("decision") not in ("allowed", "allowed_with_cautions"):
        raise ValueError("Strict mode is not available for this profile")
    if not acknowledged:
        raise ValueError("Please read and accept the commit screen first")
    pv = preview(profile, selections)
    t = pv["targets"]
    return {
        "id": uuid.uuid4().hex[:12], "status": "active", "mode": "strict", "version": 1, "start_date": today.isoformat(),
        "start_weight_kg": t["current_weight_kg"], "target_weight_kg": t["target_weight_kg"], "pace_pct_per_week": selections.get("pace_pct_per_week") or STRICT_DEFAULT_PACE_PCT,
        "targets": t, "selections": {k: v for k, v in selections.items() if k != "exercise_screen"}, "exercise_screen": selections.get("exercise_screen"),
        "screening": {"decision": screening["decision"], "cautions": screening.get("cautions", []), "scoff_positive": screening.get("scoff_positive", False),
                      "cleared_areas": screening.get("cleared_areas", [])},
        "acknowledged_at": datetime.now(timezone.utc).isoformat(), "constants_status": plan_engine.review_banner()["status"],
        "diet_preview": pv["diet"], "weeks_on_plan": 0, "last_break_week": 0, "history": [{"ts": datetime.now(timezone.utc).isoformat(), "event": "started", "clearance_used": screening.get("cleared_areas", [])}], "paused": None,
    }


# ---------------------------------------------------------------------------------------------------
# today
# ---------------------------------------------------------------------------------------------------

def today_view(plan: dict, eaten: dict, water_ml: float = 0.0, workout_kcal: float = 0.0, steps: float = 0.0) -> dict[str, Any]:
    t = plan["targets"]
    budget = plan_engine.day_budget(t, eaten.get("kcal", 0), workout_kcal)
    msg = ("You are on a pause. Take your time." if plan.get("status") == "paused" else
           "Nice and steady. Keep going." if budget["remaining_kcal"] >= 0 else "A little over today. That is okay. Tomorrow is a fresh start.")
    return {"budget": budget, "protein": {"eaten_g": round(eaten.get("protein_g", 0)), "target_g": t["protein_g"]},
            "water": {"drunk_ml": round(water_ml), "target_ml": t.get("water_ml")}, "steps": {"done": round(steps), "target": t["steps"]},
            "message": msg, "label": "estimate"}


# ---------------------------------------------------------------------------------------------------
# safety monitors
# ---------------------------------------------------------------------------------------------------

_RESTRICT = [
    ("starve", re.compile(r"\b(starv(e|ing) myself|starve myself|stop eating (completely|altogether)|not eat(ing)? (anything )?for (days|\d+ days))\b", re.I)),
    ("purge", re.compile(r"\b((?:make|made|making) myself (throw up|sick|vomit)|purg(e|ing)|laxatives? to lose|throw(ing)? up (after|my) (eating|food|meals?))\b", re.I)),
    ("punish", re.compile(r"\b(punish(ing)? myself (for|with) (eating|food)|i (don'?t|do not) deserve (to eat|food))\b", re.I)),
    ("control", re.compile(r"\b(can'?t stop thinking about food|lost control (of|over) (my )?eating|binge(d|ing)? (again|all|every)|food (is )?(all i think|controls my life))\b", re.I)),
    ("skip_all", re.compile(r"\b(skip(ping)? (all )?(my )?meals|only (drink|eat) (water|tea|coffee) (all day|today))\b", re.I)),
]
_KCAL_REQUEST = re.compile(r"\b(\d{3,4})\s*(?:k?cal(?:ories)?)\b", re.I)


def restriction_language(text: str) -> list[str]:
    """Codes of worrying restriction / disordered-eating phrases in a user's message (empty when none)."""
    return [code for code, rx in _RESTRICT if rx.search(text or "")]


def below_floor_request(text: str, floor_kcal: float) -> int | None:
    """If the user asks to eat/diet on fewer calories than the floor ("I want to eat 800 calories"), return that number."""
    for m in _KCAL_REQUEST.finditer(text or ""):
        value = int(m.group(1))
        start = max(0, m.start() - 60)
        context = (text or "")[start:m.start()].lower()
        if value < floor_kcal and re.search(r"\b(eat|eating|diet|intake|limit|target|budget|have|consume|live on|survive on|plan)\b", context):
            return value
    return None


def safety_monitors(plan: dict, *, intake_days: list[dict], exercise_min_week: float = 0.0, trend_rate_kg_week: float | None = None,
                    recent_rates: list[float] | None = None, week_change_kg: float | None = None, months_without_period: float | None = None,
                    symptoms: dict | None = None, restriction_codes: list[str] | None = None) -> list[dict]:
    """Return triggered monitors: [{code, action: 'pause'|'check_in', message}]. ``intake_days``: [{'date','kcal'}] for logged days in the last week."""
    out: list[dict] = []
    floor = plan["targets"]["floor_kcal"]
    low_days = [d for d in intake_days if 0 < d["kcal"] < floor]
    if len(low_days) >= K.SAFETY_LOW_INTAKE_DAYS_OF_7:
        out.append({"code": "low_intake", "action": "pause", "message": f"You logged less than {round(floor)} kcal on {len(low_days)} days this week. Eating too little can make you feel unwell and slow your progress. Bubbles is pausing the strict plan so you can eat enough, and suggests checking in with a doctor or dietitian."})
    rates = list(recent_rates or ([] if trend_rate_kg_week is None else [trend_rate_kg_week]))
    if len(rates) >= K.SAFETY_RAPID_LOSS_WEEKS and all(-r > K.SAFETY_RAPID_LOSS_KG_PER_WEEK for r in rates[-K.SAFETY_RAPID_LOSS_WEEKS:]):
        out.append({"code": "rapid_loss", "action": "pause", "message": "Your weight has been dropping faster than is recommended. Bubbles is easing your plan. Please mention this to a doctor."})
    if week_change_kg is not None and week_change_kg >= K.SAFETY_REGAIN_KG_IN_WEEK:
        out.append({"code": "regain_spike", "action": "check_in", "message": "Your weight went up quickly this week. That is often water, salt or your cycle. Bubbles will not change your plan because of one week."})
    avg_logged = (sum(d["kcal"] for d in intake_days if d["kcal"] > 0) / max(1, len([d for d in intake_days if d["kcal"] > 0]))) if intake_days else None
    if avg_logged is not None and avg_logged < floor * 1.1 and exercise_min_week >= K.SAFETY_HIGH_EXERCISE_MIN_PER_WEEK:
        out.append({"code": "low_energy_availability", "action": "pause", "message": "You are eating little and exercising a lot. That mix can leave the body short of energy. Bubbles is pausing the plan. Please talk to a doctor or sports dietitian."})
    if months_without_period is not None and months_without_period >= K.SAFETY_MISSED_PERIOD_MONTHS:
        out.append({"code": "missed_periods", "action": "pause", "message": "Missing periods for three months or more can be a sign your body needs more energy. Bubbles is pausing the strict plan. Please see a doctor."})
    s = symptoms or {}
    if any(s.get(k) for k in ("dizzy", "fainting", "palpitations", "chest_pain")):
        out.append({"code": "symptom", "action": "pause", "message": "Dizziness, fainting, a racing heartbeat or chest pain need medical attention. Bubbles is pausing the plan. If it is severe or sudden, get urgent help."})
    if restriction_codes:
        out.append({"code": "restriction_language", "action": "pause", "message": "It sounds like food feels really hard right now. You are not alone, and you do not have to handle this alone. Bubbles is pausing the numbers. Please talk to a doctor, a counsellor, or someone you trust."})
    kcal = [d["kcal"] for d in intake_days if d["kcal"] > 0]
    if len(kcal) >= 4 and (max(kcal) - min(kcal)) >= K.SAFETY_BINGE_RESTRICT_SWING_KCAL:
        out.append({"code": "intake_swings", "action": "check_in", "message": "Your days have been very different from each other. Eating regularly, even a little more on low days, tends to feel better. Want to look at meal timing together?"})
    return out


# ---------------------------------------------------------------------------------------------------
# weekly check-in
# ---------------------------------------------------------------------------------------------------

def weekly_checkin(plan: dict, weights: list[tuple[str, float]], daily_intake: list[dict], *, exercise_min_week: float = 0.0, today: date | None = None,
                   in_luteal_or_period: bool = False, symptoms: dict | None = None, months_without_period: float | None = None,
                   restriction_codes: list[str] | None = None, past_weekly_rates: list[float] | None = None) -> dict[str, Any]:
    """Adaptive check-in. ``weights``: all recent (iso date, kg); ``daily_intake``: [{'date','kcal'}] (logged days only, newest last)."""
    today = today or date.today()
    t = plan["targets"]
    floor = t["floor_kcal"]
    cutoff7 = (today - timedelta(days=7)).isoformat()
    week_intake = [d for d in daily_intake if d["date"] > cutoff7 and d["kcal"] > 0]
    week_weights = [w for w in weights if w[0] > cutoff7]
    trend = N.weight_trend(weights)
    rate = N.trend_rate_kg_per_week(trend, 14)
    rates = list(past_weekly_rates or []) + ([rate] if rate is not None else [])
    week_change = None
    if len(trend) >= 2:
        prev = [p for p in trend if p["date"] <= cutoff7]
        if prev:
            week_change = round(trend[-1]["weight_kg"] - prev[-1]["weight_kg"], 2)

    monitors = safety_monitors(plan, intake_days=week_intake, exercise_min_week=exercise_min_week, trend_rate_kg_week=rate, recent_rates=rates,
                               week_change_kg=week_change, months_without_period=months_without_period, symptoms=symptoms, restriction_codes=restriction_codes)
    pauses = [m for m in monitors if m["action"] == "pause"]
    base = {"trend": trend[-30:], "trend_rate_kg_per_week": rate, "monitors": monitors, "label": "estimate", "reasoning": []}
    if pauses:
        return {**base, "decision": "pause", "new_kcal": None, "change_kcal": 0, "messages": [m["message"] for m in pauses],
                "next_step": "Eat enough, rest, and talk to a clinician. Bubbles will check in gently before any restart.", "options": []}
    if len(week_intake) < K.STRICT_MIN_LOG_DAYS_FOR_CHECKIN or len(week_weights) < K.STRICT_MIN_WEIGH_INS_FOR_CHECKIN:
        return {**base, "decision": "insufficient_data", "new_kcal": t["kcal"], "change_kcal": 0,
                "messages": [f"Bubbles needs at least {K.STRICT_MIN_LOG_DAYS_FOR_CHECKIN} logged food days and {K.STRICT_MIN_WEIGH_INS_FOR_CHECKIN} weigh-ins in a week to adjust anything. Your plan stays the same."], "options": []}

    messages: list[str] = [m["message"] for m in monitors]
    reasoning = base["reasoning"]
    current = float(t["kcal"])
    planned_pace = t["pace_kg_per_week"]
    new_kcal = current
    weeks_data = (today - date.fromisoformat(trend[0]["date"])).days / 7.0 if trend else 0
    avg_intake = sum(d["kcal"] for d in daily_intake if d["date"] > (today - timedelta(days=14)).isoformat() and d["kcal"] > 0) / max(
        1, len([d for d in daily_intake if d["date"] > (today - timedelta(days=14)).isoformat() and d["kcal"] > 0]))
    expenditure = None
    if weeks_data >= K.STRICT_MIN_WEEKS_FOR_EXPENDITURE_ESTIMATE and rate is not None and len(trend) >= 2:
        change14 = rate * 2.0
        expenditure = N.estimate_expenditure(avg_intake, change14, 14)
        if expenditure is not None:
            reasoning.append(f"From what you ate and how your trend moved, your body seems to use about {round(expenditure)} kcal a day (an estimate).")
    if in_luteal_or_period and rate is not None and rate > -planned_pace * 0.5:
        messages.append("Your weight can rise a little around your period because of water. Bubbles is not changing anything because of this week.")
        decision = "continue"
    elif expenditure is not None:
        desired_deficit = t["deficit_kcal"]
        target = expenditure - desired_deficit
        step = max(-K.MAX_WEEKLY_CALORIE_CHANGE, min(K.MAX_WEEKLY_CALORIE_CHANGE, target - current))
        new_kcal = max(float(floor), current + step)
        if rate is not None and -rate > N.weekly_pace_cap_kg(t["current_weight_kg"]):
            new_kcal = min(current + K.MAX_WEEKLY_CALORIE_CHANGE, max(new_kcal, current))   # losing too fast: never cut further
            messages.append("You are losing faster than planned, so Bubbles is nudging your calories up.")
        decision = "adjust" if abs(new_kcal - current) >= 25 else "continue"
        if decision == "adjust":
            direction = "down" if new_kcal < current else "up"
            messages.append(f"Bubbles is moving your daily calories {direction} by about {abs(round(new_kcal - current))} to keep you on a steady pace.")
        else:
            messages.append("You are on a steady pace. No change needed.")
    else:
        decision = "continue"
        messages.append("Keep logging. After two weeks Bubbles can learn how your body responds.")
    plateau = False
    flat = [r for r in rates[-K.PLATEAU_WEEKS:]]
    if len(flat) >= K.PLATEAU_WEEKS and all(abs(r) < t["current_weight_kg"] * K.PLATEAU_PCT_PER_WEEK / 100.0 for r in flat):
        plateau = True
    options: list[str] = []
    if plateau:
        messages.append("Your trend has been flat for a few weeks. This happens to almost everyone.")
        options = ["Take a one to two week break at maintenance calories.", "Add a short walk on most days.", "Check that portions and oils are being logged.", "Wait another week. The scale lags behind real changes."]
    if plan.get("weeks_on_plan", 0) - plan.get("last_break_week", 0) >= K.DIET_BREAK_AFTER_WEEKS:
        options.append(f"You have been at it for {K.DIET_BREAK_AFTER_WEEKS} weeks. A {K.DIET_BREAK_WEEKS[0]}-{K.DIET_BREAK_WEEKS[1]} week break at maintenance can help.")
    return {**base, "decision": decision, "new_kcal": round(new_kcal), "change_kcal": round(new_kcal - current), "messages": messages,
            "plateau": plateau, "options": options, "expenditure_estimate": round(expenditure) if expenditure else None}


# ---------------------------------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------------------------------

def _log(plan: dict, event: str, **extra) -> None:
    plan["history"] = (plan.get("history") or [])[-199:] + [{"ts": datetime.now(timezone.utc).isoformat(), "event": event, **extra}]


def pause(plan: dict, reason: str = "user", safety: bool = False) -> dict:
    existing = plan.get("paused") or {}
    if plan.get("status") == "paused" and existing.get("safety"):
        return plan        # a safety pause (and its cooldown) can never be replaced by an ordinary one
    plan = {**plan}
    plan["status"], plan["paused"] = "paused", {"since": date.today().isoformat(), "reason": reason[:200], "safety": safety}
    _log(plan, "paused", reason=reason[:200], safety=safety)
    return plan


def can_resume(plan: dict, today: date | None = None) -> tuple[bool, str]:
    today = today or date.today()
    paused = plan.get("paused") or {}
    if plan.get("status") != "paused":
        return False, "The plan is not paused"
    if paused.get("safety"):
        since = date.fromisoformat(paused.get("since", today.isoformat()))
        if (today - since).days < K.SAFETY_COOLDOWN_DAYS:
            return False, f"Bubbles paused your plan for safety. Please wait at least {K.SAFETY_COOLDOWN_DAYS} days, eat well, and check in with a clinician."
    return True, "You can resume. Bubbles will re-check your answers first."


def resume(plan: dict, new_screening: dict, today: date | None = None) -> dict:
    ok, why = can_resume(plan, today)
    if not ok:
        raise ValueError(why)
    if new_screening.get("decision") not in ("allowed", "allowed_with_cautions"):
        raise ValueError("Strict mode is not available right now")
    plan = {**plan, "status": "active", "paused": None}
    _log(plan, "resumed")
    return plan


def edit_goal(profile: dict, plan: dict, new_target_kg: float, screening: dict) -> dict:
    """Change the target weight (re-checks the BMI floor). Keeps a snapshot in history."""
    if screening.get("decision") not in ("allowed", "allowed_with_cautions"):
        raise ValueError("Strict mode is not available for this profile")
    pv = preview({**profile, "weight_kg": plan["start_weight_kg"], "target_weight_kg": new_target_kg}, plan.get("selections"))
    new = {**plan, "target_weight_kg": new_target_kg, "targets": pv["targets"], "version": plan.get("version", 1) + 1}
    _log(new, "goal_changed", target=new_target_kg)
    return new


def maintenance_schedule(current_kcal: float, maintenance_kcal: float) -> list[dict]:
    """Gradual return to maintenance after finishing: +100 kcal a week."""
    out, kcal, week = [], float(current_kcal), 0
    while kcal < maintenance_kcal - 1 and week < 52:
        week += 1
        kcal = min(maintenance_kcal, kcal + K.MAINTENANCE_RETURN_KCAL_PER_WEEK)
        out.append({"week": week, "kcal": round(kcal)})
    return out


def finish(plan: dict, current_weight_kg: float, maintenance_kcal: float, today: date | None = None) -> dict:
    ok, why = (True, "") if plan.get("status") != "paused" or not (plan.get("paused") or {}).get("safety") else can_resume(plan, today)
    if not ok:
        raise ValueError(why)      # finishing must not be a way around the safety cooldown
    plan = {**plan, "status": "completed", "finished_at": date.today().isoformat(), "end_weight_kg": current_weight_kg}
    plan["maintenance"] = maintenance_schedule(plan["targets"]["kcal"], maintenance_kcal)
    _log(plan, "completed", weight=current_weight_kg)
    return plan


def progress_report(plan: dict, weights: list[tuple[str, float]], intake_days: list[dict]) -> dict[str, Any]:
    """Facts only, for the user to share with a doctor."""
    trend = N.weight_trend(weights)
    logged = [d["kcal"] for d in intake_days if d["kcal"] > 0]
    return {"plan_started": plan.get("start_date"), "status": plan.get("status"), "start_weight_kg": plan.get("start_weight_kg"),
            "target_weight_kg": plan.get("target_weight_kg"), "latest_weight_kg": trend[-1]["weight_kg"] if trend else None,
            "trend_weight_kg": trend[-1]["trend_kg"] if trend else None, "avg_logged_kcal": round(sum(logged) / len(logged)) if logged else None,
            "days_logged": len(logged), "daily_target_kcal": plan["targets"]["kcal"], "history": plan.get("history", [])[-30:],
            "note": "Estimates from self-reported data. Not a medical record or diagnosis."}
