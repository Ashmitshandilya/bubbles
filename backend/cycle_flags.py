"""Clinician-prompt flags for the cycle section (clinical review packet section 9). Bubbles never diagnoses.

Each flag is ``{"id", "severity": "info" | "talk" | "urgent", "title", "message", "detail"}``. Wording is deliberately kind:
"it may be worth mentioning to a clinician", never "you have". Thresholds all come from ``clinical_constants``.
Free-text notes go through ``safety_engine.assess_safety`` first (``assess_notes``); an URGENT/EMERGENCY result replaces
every other cycle message.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any, Mapping

import clinical_constants as K
from safety_engine import assess_safety, emergency_response, urgent_fallback_response

SEVERITY_ORDER = {"urgent": 0, "talk": 1, "info": 2}


def _flag(fid: str, severity: str, title: str, message: str, detail: str | None = None) -> dict:
    return {"id": fid, "severity": severity, "title": title, "message": message, "detail": detail}


URGENT_BLEEDING = _flag(
    "heavy_bleeding", "urgent", "Heavy bleeding needs urgent advice",
    "Soaking through a pad or tampon every hour for two hours or more can need urgent care. Please contact a doctor or your local "
    "emergency service now, or go to the nearest emergency department. If you are pregnant or have recently given birth, please treat this as urgent.",
    "You marked that you are soaking a pad or tampon every hour.")


def assess_notes(*texts: str | None) -> dict | None:
    """The safety engine's deterministic response when free text sounds urgent, else None."""
    text = " \n".join(t for t in texts if t).strip()
    if not text:
        return None
    assessment = assess_safety(text)
    if assessment.state == "EMERGENCY":
        return {"state": "EMERGENCY", "level": assessment.level, "message": emergency_response(assessment)}
    if assessment.state == "URGENT":
        return {"state": "URGENT", "level": assessment.level, "message": urgent_fallback_response(assessment)}
    return None


def day_flags(log: Mapping[str, Any] | None, mode: str = "track") -> list[dict]:
    """Flags raised by one day's own entries (shown straight after saving)."""
    out = []
    if not log:
        return out
    if log.get("soaking_hourly"):
        out.append(URGENT_BLEEDING)
    if (log.get("pain_level") or 0) >= K.SEVERE_PAIN_LEVEL:
        out.append(_severe_pain(log["pain_level"]))
    if mode == "pregnancy" and log.get("flow") in ("spotting", "light", "medium", "heavy"):
        out.append(_pregnancy_bleeding())
    if log.get("pregnancy_test") == "positive" and mode != "pregnancy":
        out.append(_positive_test())
    return out


def _severe_pain(level: int | float) -> dict:
    return _flag("severe_pain", "talk", "Strong pain is worth mentioning",
                 f"You rated pain {level:g} out of 10. Strong pain is worth raising with a clinician, especially if it is new, getting worse, "
                 "or stops you doing normal things. If it feels like an emergency, please get urgent help.",
                 "Pain at or above 8 out of 10.")


def _pregnancy_bleeding() -> dict:
    return _flag("pregnancy_bleeding", "talk", "Bleeding during pregnancy",
                 "You logged bleeding while in pregnancy mode. Please contact your midwife, doctor or maternity unit today to talk it through; "
                 "if it is heavy or comes with strong pain, get urgent help.", None)


def _positive_test() -> dict:
    return _flag("positive_pregnancy_test", "info", "A positive pregnancy test",
                 "You logged a positive pregnancy test. A clinician can confirm it and talk through next steps. "
                 "If this applies to you, you can switch to Pregnancy mode in the Modes tab; your data is never deleted when you switch.", None)


def compute_flags(state: Mapping[str, Any], logs: Mapping[date, Mapping[str, Any]]) -> list[dict]:
    """All flags for the overview, most important first."""
    today: date = state["today"]
    mode: str = state["mode"]
    cycles = state["cycles"]
    flags: list[dict] = []

    recent = {d: l for d, l in logs.items() if today - timedelta(days=2) <= d <= today}
    if any(l.get("soaking_hourly") for l in recent.values()):
        flags.append(URGENT_BLEEDING)

    pains = [(d, l["pain_level"]) for d, l in logs.items() if today - timedelta(days=2) <= d <= today and isinstance(l.get("pain_level"), (int, float))]
    if pains and max(p for _d, p in pains) >= K.SEVERE_PAIN_LEVEL:
        flags.append(_severe_pain(max(p for _d, p in pains)))

    if mode == "pregnancy":
        if any(l.get("flow") in ("spotting", "light", "medium", "heavy") for d, l in logs.items() if today - timedelta(days=3) <= d <= today):
            flags.append(_pregnancy_bleeding())
        return _sorted(flags)

    softer = mode in ("postpartum", "perimenopause", "birth_control")
    teen = state.get("age_group") == "teen"
    lo, hi = K.CYCLE_NORMAL_RANGE_DAYS[0], (K.CYCLE_ADOLESCENT_RANGE_DAYS if teen else K.CYCLE_NORMAL_RANGE_DAYS)[1]

    done = [c for c in cycles if c["gap"] is not None and K.CYCLE_PLAUSIBLE_DAYS[0] <= c["gap"] <= K.CYCLE_PLAUSIBLE_DAYS[1]]
    if done:
        gap = done[-1]["gap"]
        if gap < lo or gap > hi:
            flags.append(_flag(
                "cycle_length", "info" if softer else "talk", "Your last cycle was outside the typical range",
                f"Your last cycle was {gap} days. Cycles of {lo} to {hi} days are common, and one longer or shorter cycle often has a simple "
                "explanation. If it keeps happening, it may be worth mentioning to a clinician.",
                f"Typical range used: {lo}-{hi} days."))
        if state["length_stats"]["n"] >= K.CYCLE_MIN_CYCLES_FOR_PREDICTION and len(state["lengths"]) >= 3:
            prior = state["lengths"][:-1]
            usual = mean(prior)
            if state["lengths"][-1] == gap and abs(gap - usual) > K.CYCLE_SUDDEN_CHANGE_DAYS and lo <= gap <= hi:
                flags.append(_flag("sudden_change", "info", "A bigger change than usual",
                                   f"Your last cycle was {gap} days, about {abs(gap - usual):.0f} days different from your usual. "
                                   "Cycles shift for many reasons; if the change lasts, you may want to mention it to a clinician.", None))

    last = cycles[-1] if cycles else None
    if last and last["period_days"] and last["period_days"] > K.PERIOD_NORMAL_MAX_DAYS:
        flags.append(_flag("long_period", "info" if mode == "postpartum" else "talk", "A longer period than usual",
                           f"Your last period lasted about {last['period_days']} days. Bleeding for more than {K.PERIOD_NORMAL_MAX_DAYS} days "
                           "is worth mentioning to a clinician, especially if it is heavy or happens again.", None))

    starts = state["starts"]
    gaps = [(b - a).days for a, b in zip(starts, starts[1:])]
    recent_short = [g for g in gaps[-3:] if K.PERIOD_MERGE_WITHIN_DAYS < g < K.CYCLE_PLAUSIBLE_DAYS[0]]
    if recent_short:
        flags.append(_flag("bleeding_between_periods", "info" if softer else "talk", "Bleeding between periods",
                           "You logged bleeding a short time after a period. This can have many everyday causes; if it happens more than once, "
                           "it may be worth mentioning to a clinician.", None))
    elif _spotting_between(state, logs):
        flags.append(_flag("spotting_between", "info", "Spotting between periods",
                           "You logged spotting between periods. This is common and often settles by itself; if it keeps happening, "
                           "you could mention it at your next appointment.", None))

    if len(starts) >= 2 and mode != "postpartum":
        before = (starts[-1] - starts[-2]).days
        if before >= round(K.POSTMENOPAUSAL_AFTER_MONTHS_WITHOUT_PERIOD * 30.4) and (today - starts[-1]).days <= 60:
            flags.append(_flag("bleeding_after_long_gap", "talk", "Bleeding after a long break",
                               "You logged bleeding after about a year or more without a period. Bleeding after a gap like that is worth "
                               "mentioning to a clinician soon, even if it was light.", None))

    if mode in ("track", "conceive") and starts:
        due_len = state["predicted_length"]
        missed = sum(1 for k in range(1, 40)
                     if starts[-1] + timedelta(days=k * due_len + K.MISSED_PERIOD_GRACE_DAYS) < today)
        if missed >= K.MISSED_CYCLES_FLAG:
            flags.append(_flag("missed_periods", "talk", "No period logged for a while",
                               f"No period has been logged for about {missed} cycles. If you have had periods you have not logged, you can add them. "
                               "If not, and you are not pregnant, it is worth speaking to a clinician; many things can cause this and they can help.",
                               f"Last period logged: {starts[-1].isoformat()}."))
    elif mode == "perimenopause" and starts and (today - starts[-1]).days > round(K.POSTMENOPAUSAL_AFTER_MONTHS_WITHOUT_PERIOD * 30.4):
        flags.append(_flag("long_gap_perimenopause", "info", "A long gap between periods",
                           "It has been about a year or more since your last logged period. If any bleeding returns after a gap like that, "
                           "it is worth mentioning to a clinician.", None))

    if any(l.get("pregnancy_test") == "positive" for d, l in logs.items() if today - timedelta(days=14) <= d <= today):
        flags.append(_positive_test())
    return _sorted(flags)


def _spotting_between(state: Mapping[str, Any], logs: Mapping[date, Mapping[str, Any]]) -> bool:
    today = state["today"]
    nxt = state.get("next_period")
    days = 0
    for d, log in logs.items():
        if log.get("flow") != "spotting" or not (today - timedelta(days=30) <= d <= today):
            continue
        start = max((s for s in state["starts"] if s <= d), default=None)
        if start is None or (d - start).days < 8:
            continue
        if nxt and (nxt["earliest"] - d).days < 4:
            continue  # spotting just before a period is common
        days += 1
    return days >= 2


def _sorted(flags: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in sorted(flags, key=lambda f: SEVERITY_ORDER[f["severity"]]):
        if f["id"] not in seen:
            seen.add(f["id"])
            out.append(f)
    return out
