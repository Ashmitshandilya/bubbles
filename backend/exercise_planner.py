"""Exercise screening and weekly planning. Deterministic; never diagnoses; every limit comes from clinical_constants.

Flow: ``screen`` (PAR-Q-style) -> ``plan_week`` (adapts to conditions, injuries, BMI, age, equipment, level, pregnancy) ->
``adapt_session`` (pain / poor sleep / low energy / heavy period / too hard or easy) and ``time_box`` ("I only have 20 minutes").
"""
from __future__ import annotations

from typing import Any

import clinical_constants as K
import condition_rules
import nutrition_calc as N
from exercise_library import EQUIPMENT_GROUPS, LIB

STRENGTH_PATTERNS = ["squat", "hinge", "push", "pull", "core"]
SESSIONS_BY_DAYS = {1: ["mixed"], 2: ["strength", "strength"], 3: ["strength", "cardio", "strength"], 4: ["strength", "cardio", "strength", "cardio"],
                    5: ["strength", "cardio", "strength", "cardio", "mobility"], 6: ["strength", "cardio", "strength", "cardio", "strength", "mobility"]}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_SLOTS = {1: [2], 2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 3, 4, 5], 6: [0, 1, 2, 3, 4, 5]}
INJURY_ALIAS = {"back": "lower_back", "low_back": "lower_back", "knees": "knee", "shoulders": "shoulder", "wrists": "wrist"}
CARDIO_BASE_MIN = {"cleared_gentle": 60, 1: 90, 2: 120, 3: 150}


def screen(answers: dict[str, Any] | None, clinician_cleared: bool = False) -> dict[str, Any]:
    """PAR-Q-style screen. ``answers`` maps question keys to booleans (True = yes). Missing answers count as 'not answered', not 'no'."""
    answers = answers or {}
    keys = [k for k, _q in K.PARQ_QUESTIONS]
    unanswered = [k for k in keys if k not in answers]
    yes = [k for k in keys if answers.get(k) is True]
    blocking = [k for k in yes if k in K.PARQ_BLOCKING_KEYS]
    adapt = [k for k in yes if k not in K.PARQ_BLOCKING_KEYS]
    if unanswered:
        mode, msg = "incomplete", "Please answer every question so Bubbles can keep your plan safe."
    elif blocking and not clinician_cleared:
        mode = "clinician_first"
        msg = ("Please check with a doctor before starting an exercise plan. Until then Bubbles only suggests easy walking and gentle stretching. "
               "If you get chest pain, dizziness or fainting, stop and get medical help.")
    elif "pregnant" in yes:
        mode, msg = "pregnancy", "Bubbles will use gentle, pregnancy-appropriate movement. Please follow your midwife's or doctor's advice."
    else:
        mode, msg = "full", "Thanks. Bubbles will adapt your plan to your answers."
    return {"mode": mode, "message": msg, "blocking": blocking, "adapt": adapt, "unanswered": unanswered, "cleared": mode in ("full", "pregnancy")}


def _flags(profile: dict, injuries: list[str], bmi_value: float, age: float, screen_res: dict) -> set[str]:
    rules = condition_rules.classify(profile.get("conditions"), profile.get("medications"))
    flags: set[str] = set()
    for inj in injuries or []:
        key = str(inj).lower().strip().replace(" ", "_")
        flags.add(INJURY_ALIAS.get(key, key))
    if rules["hypertension"]:
        flags.add("hypertension")
    if rules["osteoporosis"]:
        flags.add("osteoporosis")
    if rules["joint"]:
        flags.add("joint")
    if profile.get("pregnant") or screen_res.get("mode") == "pregnancy" or rules["pregnancy_hint"]:
        flags.add("pregnancy")
    if profile.get("postpartum"):
        flags.add("postpartum")
    if bmi_value >= K.BMI_OBESE or "joint" in flags:
        flags.add("high_impact")
    if age >= K.CAUTION_AGE:
        flags.add("balance")
        flags.add("high_impact")
    return flags


def _allowed(move: dict, flags: set[str], equipment: set[str], level: int, mode: str) -> bool:
    if not set(move["equipment"]) <= equipment:
        return False
    if move["level"] > level:
        return False
    if set(move["avoid"]) & flags:
        return False
    if "high_impact" in flags and move["impact"] >= 2:
        return False
    if "joint" in flags and move["impact"] >= 2:
        return False
    if mode in ("clinician_first",) and not (move["category"] == "mobility" or move["id"] in ("walk-slow", "walk-brisk", "march", "chair-cardio")):
        return False
    if mode in ("pregnancy",) and (move["impact"] >= 2 or move["category"] == "strength" and move["level"] >= 3):
        return False
    return True


def _equipment(equipment: str | list[str] | None) -> set[str]:
    if isinstance(equipment, (list, tuple, set)):
        out: set[str] = {"none", "mat", "chair", "step"}
        for e in equipment:
            out |= EQUIPMENT_GROUPS.get(str(e), {str(e)})
        return out
    return set(EQUIPMENT_GROUPS.get(str(equipment or "none"), EQUIPMENT_GROUPS["none"]))


def _pick(pattern: str, pool: list[dict], seed: int, prefer_level: int) -> dict | None:
    cand = [m for m in pool if m["pattern"] == pattern and (m["category"] in ("strength", "core"))]
    if not cand:
        return None
    cand.sort(key=lambda m: (abs(m["level"] - prefer_level), m["id"]))
    top = cand[:max(1, min(3, len(cand)))]
    return top[seed % len(top)]


def _volume_week(week_index: int) -> tuple[int, bool]:
    """-> (build week w, is_deload). Every DELOAD_EVERY_WEEKS-th week repeats the previous build week at lower volume."""
    return max(1, week_index - week_index // K.DELOAD_EVERY_WEEKS), week_index % K.DELOAD_EVERY_WEEKS == 0


def _sets_reps(level: int, w: int, deload: bool) -> tuple[int, int]:
    """Progression by +1 rep a week (10 -> 15), then +1 set and back to 10 reps (2x15 -> 3x10 is equal volume)."""
    base_sets = 2 if level == 1 else 3
    extra = max(0, w - 1)
    sets, reps = (base_sets, 10 + extra) if extra < 6 else (base_sets + 1, 10 + min(extra - 6, 5))
    return (max(1, sets - 1) if deload else sets), reps


def cardio_minutes_for_week(start_min: float, w: int, deload: bool) -> int:
    minutes = start_min * ((1.0 + K.MAX_WEEKLY_VOLUME_INCREASE) ** (w - 1))
    minutes = min(minutes, K.WHO_MODERATE_MIN_PER_WEEK[1])
    return int(round(minutes * (0.7 if deload else 1.0)))


def _strength_session(pool: list[dict], minutes: int, level: int, w: int, deload: bool, seed: int, weight_kg: float, label: str) -> dict:
    sets, reps = _sets_reps(level, w, deload)
    per_ex = sets * (1.0 if level == 1 else 1.3) + 0.5
    work = max(8, minutes - (10 if minutes >= 25 else 5))
    n = int(max(3, min(8, work // per_ex)))
    patterns = (STRENGTH_PATTERNS + ["squat", "pull", "hinge"])[:n]
    moves, used = [], set()
    for i, pat in enumerate(patterns):
        m = _pick(pat, [x for x in pool if x["id"] not in used], seed + i, level)
        if m:
            used.add(m["id"])
            moves.append({"id": m["id"], "name": m["name"], "sets": sets, "reps": reps, "rest_s": 60 if level == 1 else 75, "cue": m["cue"],
                          "category": m["category"], "level": m["level"]})
    kcal = N.met_burn("strength_light", work, weight_kg)["kcal"] if moves else 0
    return {"type": "strength", "label": label, "minutes": minutes, "main": moves, "kcal_estimate": kcal}


def _cardio_session(pool: list[dict], minutes: int, level: int, seed: int, weight_kg: float, label: str, rpe_cap: int | None) -> dict:
    options = [m for m in pool if m["category"] == "cardio" and m["level"] <= level]
    options.sort(key=lambda m: (-(m["level"] == level), m["impact"], m["id"]))
    pick = options[seed % min(len(options), 3)] if options else None
    work = max(5, minutes - (10 if minutes >= 25 else 4))
    if not pick:
        return {"type": "cardio", "label": label, "minutes": minutes, "main": [], "kcal_estimate": 0}
    intervals = level >= 2 and pick["impact"] <= 1 and "hiit" not in pick["met"] and rpe_cap is None
    main = [{"id": pick["id"], "name": pick["name"], "minutes": work, "intensity": f"effort {K.RPE_TARGET_MODERATE[0]}-{K.RPE_TARGET_MODERATE[1] if rpe_cap is None else min(rpe_cap, K.RPE_TARGET_MODERATE[1])} out of 10",
             "intervals": "alternate 3 minutes steady with 1 minute a little harder" if intervals else None, "cue": pick["cue"]}]
    kcal = N.met_burn(pick["met"], work, weight_kg)["kcal"]
    return {"type": "cardio", "label": label, "minutes": minutes, "main": main, "kcal_estimate": kcal, "vigorous": pick["met"] in ("running", "hiit", "skipping", "cycling_vigorous", "swimming_vigorous")}


def _mobility_session(pool: list[dict], minutes: int, seed: int, label: str) -> dict:
    mob = sorted([m for m in pool if m["category"] == "mobility" and m["pattern"] == "mobility"], key=lambda m: m["id"])
    n = max(4, min(10, minutes // 3))
    chosen = [mob[(seed * 3 + i) % len(mob)] for i in range(min(n, len(mob)))] if mob else []
    return {"type": "mobility", "label": label, "minutes": minutes, "main": [{"id": m["id"], "name": m["name"], "seconds": 40, "cue": m["cue"]} for m in chosen], "kcal_estimate": 0}


def _warm_cool(pool: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    mob = sorted([m for m in pool if m["category"] == "mobility" and m["pattern"] == "mobility"], key=lambda m: m["id"])
    if not mob:
        return [], []
    pick = lambda start, k: [mob[(start + i * 2) % len(mob)] for i in range(k)]
    f = lambda ms, sec: [{"id": m["id"], "name": m["name"], "seconds": sec, "cue": m["cue"]} for m in ms]
    return f(pick(seed, 3), 30), f(pick(seed + 5, 3), 40)


def plan_week(profile: dict, *, days_per_week: int = 3, minutes: int = 40, equipment: Any = "none", level: int = 1, week_index: int = 1,
              screen_result: dict | None = None, injuries: list[str] | None = None, current_active_min_per_week: float | None = None) -> dict[str, Any]:
    """One week of sessions. ``profile`` needs weight_kg, height_cm, age (conditions/medications/pregnant optional)."""
    body = N.check_body(profile.get("weight_kg"), profile.get("height_cm"), profile.get("age"), required=("weight_kg", "height_cm", "age"))
    weight, height, age = body["weight_kg"], body["height_cm"], body["age"]
    days = max(1, min(int(days_per_week), 6))
    minutes = max(10, min(int(minutes), 120))
    level = max(1, min(int(level), 3))
    week_index = max(1, min(int(week_index), 104))
    sr = screen_result or {"mode": "full", "message": "", "cleared": True}
    mode = sr.get("mode", "full")
    if mode == "incomplete":
        return {"ok": False, "reason": sr["message"], "screen": sr}
    bmi_value = N.bmi(weight, height)
    flags = _flags(profile, injuries or [], bmi_value, age, sr)
    if mode == "clinician_first":
        level, days, minutes = 1, min(days, 5), min(minutes, 30)
    equipment_set = _equipment(equipment)
    pool = [m for m in LIB.values() if _allowed(m, flags, equipment_set, level, mode)]
    w, deload = _volume_week(week_index)
    rpe_cap = 5 if mode in ("pregnancy", "clinician_first") or "pregnancy" in flags else None
    start = current_active_min_per_week if current_active_min_per_week is not None else CARDIO_BASE_MIN.get(level, 90)
    if mode == "clinician_first":
        start = CARDIO_BASE_MIN["cleared_gentle"]
    start = max(40.0, min(float(start), 200.0))
    weekly_cardio = cardio_minutes_for_week(start, w, deload)

    kinds = SESSIONS_BY_DAYS[days]
    if mode == "clinician_first":
        kinds = ["cardio" if k != "mobility" else k for k in kinds[:days]]
    strength_days = sum(1 for k in kinds if k == "strength")
    cardio_days = sum(1 for k in kinds if k == "cardio") or 1
    per_cardio = max(15, min(90, weekly_cardio // max(cardio_days, 1)))
    # add a short walk to strength days if the week would otherwise miss the cardio target (counted below)
    sessions = []
    slots = DAY_SLOTS[days]
    for i, kind in enumerate(kinds):
        seed = week_index + i
        warm, cool = _warm_cool(pool, seed)
        label = {"strength": "Strength", "cardio": "Cardio", "mobility": "Mobility and stretching", "mixed": "Full body"}[kind] + (f" {chr(65 + i // 2)}" if kind == "strength" else "")
        if kind == "strength":
            body = _strength_session(pool, minutes, level, w, deload, seed, weight, label)
        elif kind == "cardio":
            body = _cardio_session(pool, max(per_cardio + (10 if per_cardio >= 25 else 4), 20), level, seed, weight, label, rpe_cap)
        elif kind == "mixed":
            body = _strength_session(pool, minutes, level, w, deload, seed, weight, label)
        else:
            body = _mobility_session(pool, min(minutes, 30), seed, label)
        body.update(day=WEEKDAYS[slots[i]], warmup=warm if body["type"] != "mobility" else [], cooldown=cool if body["type"] != "mobility" else [])
        sessions.append(body)

    cardio_min = sum(max(0, s["minutes"] - 10) for s in sessions if s["type"] == "cardio")
    vigorous_min = sum(max(0, s["minutes"] - 10) for s in sessions if s.get("vigorous"))
    moderate_equivalent = cardio_min + vigorous_min  # vigorous minutes count double
    strength_n = sum(1 for s in sessions if s["type"] in ("strength", "mixed"))
    notes: list[str] = []
    if mode == "clinician_first":
        notes.append("Easy walking and stretching only until a doctor clears you.")
    if "pregnancy" in flags:
        notes.append("In pregnancy, gentle movement is usually fine, but please follow your midwife's or doctor's advice. Stop if you feel dizzy, short of breath, or have pain or bleeding.")
    if "postpartum" in flags:
        notes.append("After a baby, start gently and build slowly. Talk to your doctor about core and pelvic-floor work.")
    if deload:
        notes.append("This is an easier week on purpose. Rest is part of getting stronger.")
    rules = condition_rules.classify(profile.get("conditions"), profile.get("medications"))
    if rules["diabetes"]:
        notes.append("With diabetes, check how exercise affects your glucose, carry a fast sugar source, and avoid long sessions on an empty stomach unless your doctor has said it is fine.")
    if rules["asthma"]:
        notes.append("Warm up slowly and keep your reliever inhaler nearby.")
    if rules["hypertension"]:
        notes.append("Avoid holding your breath while lifting. Keep effort moderate and ask your doctor about limits.")
    if "balance" in flags and age >= K.CAUTION_AGE:
        notes.append("Balance work is included. Hold on to something stable when needed.")
    who_ok = (moderate_equivalent >= K.WHO_MODERATE_MIN_PER_WEEK[0]) and strength_n >= K.WHO_STRENGTH_DAYS_MIN
    if not who_ok:
        notes.append("This is a building week. A common goal is about 150 minutes of moderate activity and 2 days of strength work, so add easy walks whenever you can.")
    return {"ok": True, "week_index": week_index, "deload": deload, "level": level, "sessions": sessions, "mode": mode, "flags": sorted(flags), "notes": notes,
            "summary": {"cardio_minutes": cardio_min, "moderate_equivalent_minutes": moderate_equivalent, "strength_days": strength_n,
                        "meets_who": who_ok, "rest_days": [d for j, d in enumerate(WEEKDAYS) if j not in slots],
                        "kcal_estimate": sum(s["kcal_estimate"] for s in sessions)},
            "who": {"moderate_min_week": list(K.WHO_MODERATE_MIN_PER_WEEK), "strength_days_min": K.WHO_STRENGTH_DAYS_MIN}, "label": "estimate",
            "screen": sr, "pool_size": len(pool)}


def weekly_volume(plan: dict) -> dict[str, float]:
    """Training volume used by the progression tests: strength set-reps and cardio minutes."""
    strength = sum(m["sets"] * m["reps"] for s in plan["sessions"] if s["type"] in ("strength", "mixed") for m in s["main"])
    cardio = sum(max(0, s["minutes"] - 10) for s in plan["sessions"] if s["type"] == "cardio")
    return {"strength": float(strength), "cardio": float(cardio)}


def adapt_session(session: dict, feedback: dict, pool_profile: dict | None = None, equipment: Any = "none", level: int = 1) -> dict[str, Any]:
    """Change one session in response to how the user feels. Pain with serious signs is never coached through."""
    msgs: list[str] = []
    out = {**session, "main": [dict(m) for m in session.get("main", [])]}
    area = str(feedback.get("pain_area") or "").lower().replace(" ", "_")
    if feedback.get("chest_pain") or feedback.get("dizzy") or feedback.get("fainting") or int(feedback.get("pain_severity") or 0) >= 7:
        return {"session": {**out, "main": []}, "stop": True, "messages": ["Please stop exercising. If you have chest pain, fainting, severe dizziness or severe pain, get medical help now."]}
    if feedback.get("pain") and area:
        avoid = {"knee": "knee", "back": "lower_back", "lower_back": "lower_back", "shoulder": "shoulder", "wrist": "wrist", "neck": "neck"}.get(area, area)
        before = len(out["main"])
        out["main"] = [m for m in out["main"] if avoid not in LIB.get(m["id"], {}).get("avoid", [])]
        if len(out["main"]) < before:
            msgs.append(f"Moves that load your {area.replace('_', ' ')} were removed. If the pain lasts or gets worse, please see a clinician.")
        else:
            msgs.append("Stay in a comfortable range and see a clinician if pain lasts more than a few days.")
    cut = 1.0
    if feedback.get("poor_sleep"):
        cut = min(cut, 0.8)
        msgs.append("Short on sleep, so today is a little lighter.")
    if feedback.get("low_energy"):
        cut = min(cut, 0.7)
        msgs.append("Low energy: a lighter session still counts.")
    if feedback.get("heavy_period"):
        cut = min(cut, 0.8)
        msgs.append("Heavy period day: go gently and listen to your body. Easy movement is fine if it feels good.")
    if cut < 1.0:
        for m in out["main"]:
            if "sets" in m:
                m["sets"] = max(1, round(m["sets"] * cut))
            if "minutes" in m:
                m["minutes"] = max(5, round(m["minutes"] * cut))
        out["minutes"] = max(10, round(out.get("minutes", 30) * cut))
    rpe = feedback.get("rpe_avg")
    done = feedback.get("completed_pct")
    suggestion = None
    if isinstance(rpe, (int, float)) and isinstance(done, (int, float)):
        if rpe >= 8:
            suggestion = "regress"
            msgs.append("That felt very hard. Next time Bubbles will make it a little easier.")
        elif rpe <= 4 and done >= 90:
            suggestion = "progress"
            msgs.append("That felt comfortable. Next time Bubbles will nudge it up a little.")
    return {"session": out, "stop": False, "messages": msgs, "next_step": suggestion}


def time_box(session: dict, minutes: int) -> dict[str, Any]:
    """Fit a session into `minutes` (for example 20) by keeping the most important moves and shortening cardio."""
    minutes = max(5, min(int(minutes), 120))
    out = {**session, "main": [dict(m) for m in session.get("main", [])], "warmup": session.get("warmup", [])[:2], "cooldown": session.get("cooldown", [])[:1]}
    if session.get("type") in ("strength", "mixed"):
        per = 3.5
        keep = int(max(2, min(len(out["main"]), (minutes - 5) // per)))
        out["main"] = out["main"][:keep]
        for m in out["main"]:
            m["sets"] = max(1, min(m["sets"], 2))
    else:
        for m in out["main"]:
            if "minutes" in m:
                m["minutes"] = max(5, minutes - 6)
    out["minutes"] = minutes
    return out
