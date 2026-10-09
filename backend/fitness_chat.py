"""Chat as the front door to Fitness: deterministic answers about the user's own plan, and a kind, firm response to
restriction language or a request to eat below the safe floor. No model is involved, so it works with no AI keys and can
never invent a number: every figure is read from plan_engine / the saved plan. Plan CHANGES are never made from chat; Bubbles
points to the screen where the user confirms them.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

import clinical_constants as K
import doc_store
import fitness_api as F
import nutrition_calc as N
import plan_engine
import transformation as T

_I = re.IGNORECASE
INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("calories_left", re.compile(r"\b(calories?|kcal)\b.{0,25}\b(left|remaining|remain)\b|\bhow (much|many).{0,25}\b(left|remaining)\b.{0,15}\b(today|eat)", _I)),
    ("calorie_target", re.compile(r"\b(how many (calories|kcal)|calorie (target|goal|budget|need)|daily (calories|kcal)|my (calorie|kcal) )\b.{0,40}|\bhow much (should|can|do) i eat\b", _I)),
    ("protein_target", re.compile(r"\b(how much|what'?s my|my)\b.{0,15}\bprotein\b", _I)),
    ("plan_today", re.compile(r"\bwhat (should|can|do) i (eat|have|cook)\b|\b(today'?s|my) (meal plan|diet plan|meals)\b|\bwhat'?s (for|on) (breakfast|lunch|dinner)\b", _I)),
    ("workout_today", re.compile(r"\b(today'?s|my) (workout|exercise|training)\b|\bwhat (workout|exercise) (should|do) i\b|\bwhat'?s my workout\b", _I)),
    ("swap_meal", re.compile(r"\b(swap|change|replace|switch)\b.{0,20}\b(breakfast|lunch|dinner|snack|meal)\b", _I)),
    ("why_changed", re.compile(r"\bwhy did my (plan|calories|target|budget|goal) (change|go (up|down)|drop|increase)", _I)),
    ("start_strict", re.compile(r"\b(start|begin|try|want)\b.{0,25}\b(strict|transformation|transform)\b|\bheavy transformation\b", _I)),
]


def classify(text: str) -> str | None:
    """-> 'support' (restriction language), 'below_floor', an intent name, or None. Pure."""
    text = text or ""
    if T.restriction_language(text):
        return "support"
    if T.below_floor_request(text, K.INTAKE_FLOOR_KCAL["female"]) is not None:
        return "below_floor"
    for name, rx in INTENTS:
        if rx.search(text):
            return name
    return None


def route_for(text: str) -> str | None:
    kind = classify(text)
    if kind in ("support", "below_floor"):
        return "fitness_support"
    return "fitness_answer" if kind else None


def pause_active_plan(db: Any, uid: str) -> bool:
    return _pause_active_plan(db, uid)


def _pause_active_plan(db: Any, uid: str) -> bool:
    try:
        plan = doc_store.get(db, uid, "transform_plan", "current")
        if plan and plan.get("status") == "active":
            doc_store.put(db, uid, "transform_plan", "current", T.pause(plan, "restriction language in chat", safety=True))
            doc_store.put(db, uid, "safety_pause", "last", {"since": datetime.now(timezone.utc).date().isoformat(), "reason": "restriction language in chat"})
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _targets(db: Any, uid: str) -> tuple[dict | None, str | None]:
    profile = doc_store.get(db, uid, "profile", "me") or {}
    rec = F.records(db, uid)
    ep = F.engine_profile(profile, rec)
    gap = F.missing_fields(ep)
    if gap:
        return None, "Add your " + ", ".join(g.replace("_", " ") for g in gap) + " in Fitness, then Set up, and I can work this out for you."
    try:
        return plan_engine.build_targets(ep), None
    except N.CalcError as err:
        return None, str(err)


def _review_line() -> str:
    b = plan_engine.review_banner()
    return "" if b["reviewed"] else "\n\n(These are estimates and are still waiting for a clinician's review. They are not medical advice.)"


def reply(db: Any, uid: str, text: str, today: date | None = None) -> str:
    kind = classify(text)
    today = today or datetime.now(timezone.utc).date()
    if kind == "support":
        paused = _pause_active_plan(db, uid)
        return ("It sounds like food might feel really hard right now, and I'm glad you said it. You don't have to handle this on your own. "
                "Talking to a doctor, a counsellor, or someone you trust can really help, and it is okay to ask for that. "
                + ("I've paused your strict plan so the numbers can take a back seat. " if paused else "I won't push any numbers right now. ")
                + "If you ever feel unsafe or think you might hurt yourself, please contact your local emergency number or a crisis line straight away. "
                "I'm here whenever you want to talk.")
    if kind == "below_floor":
        value = T.below_floor_request(text, K.INTAKE_FLOOR_KCAL["female"])
        return (f"I can't plan around {value} calories a day. Eating that little can make you tired, dizzy and unwell, and it usually backfires. "
                f"The lowest Bubbles will ever plan is about {round(K.INTAKE_FLOOR_ABSOLUTE_KCAL)} to {round(K.INTAKE_FLOOR_KCAL['male'])} calories depending on your body. "
                "If a doctor has asked you to follow a very low calorie plan, please follow their guidance, since that needs medical supervision. "
                "Want me to build a steady plan that still helps you reach your goal?")
    if kind == "start_strict":
        return ("Strict transformation mode joins your diet, workouts and calorie log into one plan toward your target weight. "
                "It starts with a few short safety questions and you choose your foods and exercise before anything begins. "
                "You'll find it under Fitness, then Transform." + _review_line())
    if kind == "swap_meal":
        return ("I can show you swaps that keep the same calories and protein. Open Fitness, then Diet planner, and tap Swap on that meal. "
                "I don't change your plan from chat, so you always get to confirm it.")
    if kind == "why_changed":
        plan = doc_store.get(db, uid, "transform_plan", "current")
        proposal = doc_store.get(db, uid, "checkin_proposal", "current")
        if proposal:
            r = proposal["result"]
            return " ".join(r.get("messages", [])[:2] + r.get("reasoning", [])[:1]) or "Your weekly check-in is waiting for you under Fitness, then Transform."
        if plan:
            events = [h for h in plan.get("history", []) if h.get("event") in ("checkin_applied", "goal_changed", "paused", "resumed")]
            if events:
                last = events[-1]
                return f"The last change was '{last['event'].replace('_', ' ')}' on {str(last['ts'])[:10]}. Your weekly check-in shows the reasoning under Fitness, then Transform."
        return "I don't see a plan change yet. Your plan only changes after a weekly check-in that you confirm."
    if kind in ("calorie_target", "calories_left", "protein_target"):
        t, why = _targets(db, uid)
        if t is None:
            return why or "I need a few details first."
        if kind == "protein_target":
            return f"Your protein target is about {t['protein_g']} g a day (around {t['protein_g_per_kg']} g per kg). That's an estimate." + _review_line()
        if kind == "calories_left":
            entries = F._all_entries(db, uid, today.isoformat())
            eaten = F._sum(entries)["kcal"]
            workout = doc_store.get(db, uid, "workout_log", today.isoformat()) or {}
            burn = sum(float(w.get("kcal_estimate", 0)) for w in workout.get("sessions", []))
            b = plan_engine.day_budget(t, eaten, burn)
            if b["remaining_kcal"] >= 0:
                return f"You've logged about {b['eaten_kcal']} kcal, so roughly {b['remaining_kcal']} kcal are left for today (an estimate)." + _review_line()
            return f"You're about {abs(b['remaining_kcal'])} kcal over today, which is completely okay. Tomorrow is a fresh start." + _review_line()
        extra = f" That aims for about {t['pace_kg_per_week']} kg a week." if t["goal"] == "lose" and t["pace_kg_per_week"] else ""
        return (f"Your daily budget is about {t['kcal']} kcal, with around {t['protein_g']} g protein (an estimate, not an exact number)."
                + extra + (f" Bubbles won't go below {t['floor_kcal']} kcal." if t["goal"] == "lose" else "") + _review_line())
    if kind == "plan_today":
        doc = doc_store.get(db, uid, "meal_plan", "current")
        if not doc:
            return "You don't have a meal plan yet. Open Fitness, then Diet planner, and Bubbles will build one around the foods you like."
        days = doc["plan"]["days"]
        idx = (today - date.fromisoformat(str(doc.get("created", today.isoformat()))[:10])).days % max(1, len(days))
        meals = days[idx]["meals"]
        lines = [f"{m['label']}: {m['name']} (about {m['totals']['kcal']} kcal)" for m in meals]
        return "Here's today's plan:\n" + "\n".join(lines) + "\n\nThese are estimates. You can swap any meal in Fitness, then Diet planner." + _review_line()
    if kind == "workout_today":
        doc = doc_store.get(db, uid, "workout_plan", "current")
        if not doc:
            return "You don't have a workout plan yet. Open Fitness, then Workouts. It starts with a few quick safety questions."
        sessions = doc["plan"]["sessions"]
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][today.weekday()]
        today_s = next((s for s in sessions if s["day"] == wd), None)
        if not today_s:
            return "Today is a rest day in your plan. Rest is part of getting stronger. A gentle walk is always welcome."
        names = ", ".join(m["name"] for m in today_s["main"][:5])
        return f"Today is {today_s['label']} ({today_s['minutes']} minutes): {names}. Short on time? Tell me how many minutes you have and I'll point you to the shortened version in Workouts."
    return "I'm not sure how to help with that yet. Try Fitness from the menu."
