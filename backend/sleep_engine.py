"""Sleep: score, regularity, 7-day debt, streak, weekday pattern, naps, tag insights and a wind-down time.

Pure functions over plain dicts, plus two thin loaders at the bottom. Copy is kind and non-shaming; patterns are
phrased as tendencies ("tends to"), never causes; Bubbles does not detect sleep disorders.

Storage (no schema change):
  * the night itself goes through the existing tracker, ``health_logs.save_domain('sleep')`` (duration, quality, notes),
    so the insight/analytics code keeps seeing it;
  * everything the tracker table has no column for (bedtime, wake time, tags, naps, cycle phase) lives in the doc
    ``sleep_tags`` keyed by the night's date. A doc was chosen over a notes prefix because it is structured, queryable
    by date and does not put tag text into free-text notes that other readers show;
  * the user's goal is the doc ``sleep_goal`` / key ``me``.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import clinical_constants as K
import doc_store
from health_logs import DOMAINS, list_domain
from wellness_common import InputError, fmt_hhmm, number, parse_hhmm

TAG_LABELS = {"caffeine": "caffeine", "alcohol": "alcohol", "stress": "a stressful day", "late_meal": "a late meal",
              "screen": "late screen time", "exercise": "exercise that day"}
PHASES = ("period", "follicular", "ovulation", "luteal")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DISCLAIMER = ("Sleep patterns here are your own logs, not a medical test. Bubbles can't detect sleep disorders; "
              "if sleep problems keep going, a clinician is the right person to ask.")


# --- goal ----------------------------------------------------------------------------------------------------------------

def goal_for_age(age: float | None) -> dict[str, Any]:
    """Recommended range for the age band and the midpoint used as the default goal."""
    if age is None:
        lo, hi, group = K.SLEEP_HOURS_ADULT[0], K.SLEEP_HOURS_ADULT[1], "adult"
    elif age <= K.SLEEP_CHILD_MAX_AGE:
        (lo, hi), group = K.SLEEP_HOURS_CHILD, "child"
    elif age <= K.SLEEP_TEEN_MAX_AGE:
        (lo, hi), group = K.SLEEP_HOURS_TEEN, "teen"
    elif age >= K.SLEEP_OLDER_MIN_AGE:
        (lo, hi), group = K.SLEEP_HOURS_OLDER, "older"
    else:
        (lo, hi), group = K.SLEEP_HOURS_ADULT, "adult"
    return {"min": lo, "max": hi, "target": round((lo + hi) / 2, 1), "group": group}


def resolve_goal(age: float | None, stored: dict | None) -> dict[str, Any]:
    rec = goal_for_age(age)
    hours = None
    if stored and stored.get("hours") is not None:
        try:
            h = float(stored["hours"])
            hours = h if K.SLEEP_GOAL_BOUNDS_H[0] <= h <= K.SLEEP_GOAL_BOUNDS_H[1] else None
        except (TypeError, ValueError):
            hours = None
    out = {"hours": hours if hours is not None else rec["target"], "source": "you" if hours is not None else "age",
           "recommended_min": rec["min"], "recommended_max": rec["max"], "age_group": rec["group"]}
    for k in ("bedtime", "wake_time"):
        if stored and stored.get(k):
            out[k] = stored[k]
    return out


def normalize_goal(body: dict) -> dict[str, Any]:
    hours = number(body.get("hours"), *K.SLEEP_GOAL_BOUNDS_H, "hours", required=True)
    out: dict[str, Any] = {"hours": round(hours * 4) / 4}   # quarter-hour steps
    for key in ("bedtime", "wake_time"):
        if body.get(key) not in (None, ""):
            out[key] = fmt_hhmm(parse_hhmm(body[key], key.replace("_", " ")))
    return out


# --- one night's details (bedtime, wake, tags, naps) ---------------------------------------------------------------------

def normalize_details(body: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("bedtime", "wake"):
        if body.get(key) not in (None, ""):
            out[key] = fmt_hhmm(parse_hhmm(body[key], key))
    tags = body.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 12:
            raise InputError("tags must be a short list")
        clean = []
        for t in tags:
            v = str(t).strip().lower().replace(" ", "_").replace("-", "_")
            if v not in K.SLEEP_TAGS:
                raise InputError("tags can be: " + ", ".join(K.SLEEP_TAGS))
            if v not in clean:
                clean.append(v)
        out["tags"] = clean
    nap = number(body.get("nap_minutes"), 0, K.SLEEP_NAP_MAX_MIN, "nap minutes")
    if nap:
        out["nap_minutes"] = round(nap)
    phase = body.get("cycle_phase")
    if phase not in (None, ""):
        p = str(phase).strip().lower()
        if p not in PHASES:
            raise InputError("cycle phase must be one of " + ", ".join(PHASES))
        out["cycle_phase"] = p
    return out


def duration_hours(bedtime: str, wake: str) -> float:
    """Hours asleep between a bedtime and the next wake time (crosses midnight when needed)."""
    b, w = parse_hhmm(bedtime, "bedtime"), parse_hhmm(wake, "wake time")
    minutes = (w - b) % 1440
    if minutes == 0:
        raise InputError("bedtime and wake time can't be the same")
    return round(minutes / 60, 2)


# --- per-night table -----------------------------------------------------------------------------------------------------

def nightly(entries: list[dict], details: dict[str, dict], today: date) -> list[dict[str, Any]]:
    """One row per date, oldest first. The longest entry of a date is the night; any other entry counts as a nap."""
    by_day: dict[str, list[dict]] = {}
    for e in entries:
        d, h = str(e.get("date") or "")[:10], e.get("duration")
        try:
            h = float(h)
        except (TypeError, ValueError):
            continue
        if len(d) == 10 and d <= today.isoformat() and 0 < h <= 24 and math.isfinite(h):
            by_day.setdefault(d, []).append({**e, "duration": h})
    rows = []
    for d in sorted(by_day):
        items = sorted(by_day[d], key=lambda e: e["duration"], reverse=True)
        night, extras = items[0], items[1:]
        det = details.get(d) or {}
        quality = night.get("quality")
        rows.append({"date": d, "hours": night["duration"], "quality": float(quality) if isinstance(quality, (int, float)) else None,
                     "bedtime": det.get("bedtime"), "wake": det.get("wake"), "tags": list(det.get("tags") or []),
                     "has_details": bool(det), "cycle_phase": det.get("cycle_phase"),
                     "nap_minutes": round(sum(x["duration"] * 60 for x in extras) + (det.get("nap_minutes") or 0))})
    return rows


# --- measures ------------------------------------------------------------------------------------------------------------

def _spread(minutes: list[int]) -> float:
    """Standard deviation of clock times in minutes, wrap-around safe (23:50 and 00:10 are 20 minutes apart)."""
    ref = minutes[0]
    offs = [((m - ref + 720) % 1440) - 720 for m in minutes]
    mean = sum(offs) / len(offs)
    return math.sqrt(sum((o - mean) ** 2 for o in offs) / len(offs))


def regularity(nights: list[dict]) -> dict[str, Any] | None:
    """Typical day-to-day variation in minutes: the average of the bedtime and wake-time variation. Falls back to the
    variation in hours slept (basis 'duration') for people who only log how long they slept."""
    need = K.SLEEP_MIN_NIGHTS_FOR_REGULARITY
    parts = []
    for key in ("bedtime", "wake"):
        vals = [parse_hhmm(n[key]) for n in nights if n.get(key)]
        if len(vals) >= need:
            parts.append(_spread(vals))
    basis = "times"
    if not parts:
        durations = [n["hours"] * 60 for n in nights]
        if len(durations) < need:
            return None
        mean = sum(durations) / len(durations)
        parts, basis = [math.sqrt(sum((d - mean) ** 2 for d in durations) / len(durations))], "duration"
    minutes = round(sum(parts) / len(parts))
    return {"minutes": minutes, "basis": basis, "consistent": minutes <= K.SLEEP_REGULARITY_GOOD_MINUTES}


def score(avg_hours: float | None, goal_hours: float, regularity_minutes: float | None, avg_quality: float | None,
          upper_hours: float | None = None) -> dict[str, Any] | None:
    """0-100 sleep score. Duration (50), regularity (30), quality (20); a part with no data is left out and the rest re-weighted."""
    if avg_hours is None or goal_hours <= 0:
        return None
    w = K.SLEEP_SCORE_WEIGHTS
    parts: dict[str, float] = {}
    dur = min(1.0, max(0.0, avg_hours / goal_hours))
    if upper_hours and avg_hours > upper_hours + 1:   # a long way over the recommended range scores a little less, never zero
        dur = max(0.6, 1 - 0.1 * (avg_hours - upper_hours - 1))
    parts["duration"] = dur
    if regularity_minutes is not None:
        good, zero = K.SLEEP_REGULARITY_GOOD_MINUTES, K.SLEEP_REGULARITY_ZERO_MINUTES
        parts["regularity"] = 1.0 if regularity_minutes <= good else max(0.0, 1 - (regularity_minutes - good) / (zero - good))
    if avg_quality is not None:
        parts["quality"] = min(1.0, max(0.0, avg_quality / 10))
    total = sum(w[k] for k in parts)
    value = max(0, min(100, round(100 * sum(w[k] * v for k, v in parts.items()) / total)))
    label = ("Restful" if value >= 80 else "Good" if value >= 65 else "Okay" if value >= 45 else "A lighter stretch")
    return {"value": value, "label": label, "parts": {k: round(v * 100) for k, v in parts.items()}}


def sleep_debt(nights: list[dict], goal_hours: float, today: date) -> dict[str, Any] | None:
    """Shortfall against the user's own goal over the last 7 days, from logged nights only. Surplus does not 'pay back' debt."""
    start = (today - timedelta(days=K.SLEEP_DEBT_WINDOW_DAYS - 1)).isoformat()
    recent = [n for n in nights if n["date"] >= start]
    if not recent:
        return None
    hours = round(sum(max(0.0, goal_hours - n["hours"]) for n in recent), 1)
    if hours < 1:
        msg = "You're close to your sleep goal this week."
    elif hours <= 4:
        msg = (f"About {hours:g} h under your goal across {len(recent)} logged nights. "
               "An earlier night or two can help; there is no need to make it all up at once.")
    else:
        msg = (f"Sleep has been on the lighter side this week (about {hours:g} h under your goal). Be gentle with yourself; "
               "a calm wind-down tonight may help. If it keeps up, it could be worth mentioning to a clinician.")
    return {"hours": hours, "nights_logged": len(recent), "window_days": K.SLEEP_DEBT_WINDOW_DAYS,
            "partial": len(recent) < K.SLEEP_DEBT_MIN_NIGHTS, "message": msg}


def streak(nights: list[dict], goal_hours: float, today: date) -> dict[str, Any]:
    """Consecutive calendar nights within half an hour of (or above) the goal. A gap or a short night just resets the count."""
    ok = {n["date"] for n in nights if n["hours"] >= goal_hours - K.SLEEP_ON_TRACK_TOLERANCE_H}
    logged = {n["date"] for n in nights}
    best = run = 0
    prev = None
    for d in sorted(ok):
        cur = date.fromisoformat(d)
        run = run + 1 if prev is not None and cur - prev == timedelta(days=1) else 1
        best, prev = max(best, run), cur
    current = 0
    day = today if today.isoformat() in logged else today - timedelta(days=1)   # tonight's sleep may not be logged yet
    while day.isoformat() in ok:
        current += 1
        day -= timedelta(days=1)
    msg = (f"{current} nights in a row near your goal." if current >= 2 else "Last night was near your goal." if current == 1
           else "A fresh start is always available. Tonight counts.")
    return {"current": current, "best": best, "message": msg}


def weekday_pattern(nights: list[dict]) -> dict[str, Any] | None:
    groups: dict[int, list[float]] = {}
    for n in nights:
        groups.setdefault(date.fromisoformat(n["date"]).weekday(), []).append(n["hours"])
    avgs = {d: sum(v) / len(v) for d, v in groups.items() if len(v) >= K.SLEEP_WEEKDAY_MIN_NIGHTS}
    if len(avgs) < 3:
        return None
    best, worst = max(avgs, key=avgs.get), min(avgs, key=avgs.get)
    if avgs[best] - avgs[worst] < K.SLEEP_WEEKDAY_MIN_SPREAD_H:
        return None
    return {"best": {"weekday": WEEKDAYS[best], "hours": round(avgs[best], 1)}, "worst": {"weekday": WEEKDAYS[worst], "hours": round(avgs[worst], 1)},
            "message": f"You tend to sleep longest on {WEEKDAYS[best]}s and shortest on {WEEKDAYS[worst]}s."}


def nap_summary(nights: list[dict], window_days: int) -> dict[str, Any]:
    total = sum(n["nap_minutes"] for n in nights)
    with_naps = sum(1 for n in nights if n["nap_minutes"] > 0)
    return {"total_minutes": total, "days_with_naps": with_naps, "window_days": window_days,
            "note": "Naps are shown separately and are not counted in your night score or sleep debt."}


def _compare(label: str, with_: list[float], without: list[float]) -> dict[str, Any] | None:
    if len(with_) < K.SLEEP_INSIGHT_MIN_PER_GROUP or len(without) < K.SLEEP_INSIGHT_MIN_PER_GROUP:
        return None
    if len(with_) + len(without) < K.SLEEP_INSIGHT_MIN_NIGHTS:
        return None
    diff = round((sum(with_) / len(with_) - sum(without) / len(without)) * 60)
    if abs(diff) < K.SLEEP_INSIGHT_MIN_DIFF_MIN:
        return None
    more_less = "more" if diff > 0 else "less"
    return {"label": label, "with_n": len(with_), "without_n": len(without), "diff_minutes": diff,
            "confidence": "moderate" if min(len(with_), len(without)) >= 7 else "low",
            "text": (f"On nights with {label}, you tended to sleep about {abs(diff)} min {more_less} "
                     f"({len(with_)} nights compared with {len(without)}). That's a pattern in your own logs, not proof of a cause.")}


def tag_insights(nights: list[dict]) -> list[dict[str, Any]]:
    """Tag and cycle-phase patterns. Only nights that have a details doc count (a night with no tags logged is unknown, not 'none')."""
    tagged = [n for n in nights if n["has_details"]]
    out = []
    for tag in K.SLEEP_TAGS:
        found = _compare(TAG_LABELS[tag], [n["hours"] for n in tagged if tag in n["tags"]], [n["hours"] for n in tagged if tag not in n["tags"]])
        if found:
            out.append({"tag": tag, **found})
    phased = [n for n in tagged if n["cycle_phase"]]
    for phase in PHASES:
        found = _compare(f"the {phase} phase of your cycle", [n["hours"] for n in phased if n["cycle_phase"] == phase],
                         [n["hours"] for n in phased if n["cycle_phase"] != phase])
        if found:
            out.append({"tag": f"cycle_phase:{phase}", **found})
    return sorted(out, key=lambda i: -abs(i["diff_minutes"]))


def winddown(goal_hours: float, *, bedtime: str | None = None, wake: str | None = None, recent_bedtimes: list[str] | None = None,
             recent_wakes: list[str] | None = None) -> dict[str, Any]:
    """Suggested wind-down reminder time. Bedtime comes from, in order: the user's chosen bedtime; their recent usual bedtime
    (3+ logged); a wake time minus the sleep goal (chosen wake, recent usual wake, or 07:00)."""
    def usual(times: list[str] | None) -> int | None:
        vals = [parse_hhmm(t) for t in (times or []) if t]
        if len(vals) < K.SLEEP_MIN_NIGHTS_FOR_REGULARITY:
            return None
        ref = vals[0]
        offs = sorted(((v - ref + 720) % 1440) - 720 for v in vals)
        return (ref + offs[len(offs) // 2]) % 1440

    if bedtime:
        bed, basis = parse_hhmm(bedtime), "your chosen bedtime"
    elif (u := usual(recent_bedtimes)) is not None:
        bed, basis = u, "your usual bedtime"
    else:
        w = parse_hhmm(wake) if wake else usual(recent_wakes)
        basis = "your wake time and sleep goal" if w is not None else "a 07:00 wake time and your sleep goal"
        bed = ((w if w is not None else 7 * 60) - round(goal_hours * 60)) % 1440
    return {"bedtime": fmt_hhmm(bed), "winddown": fmt_hhmm(bed - K.SLEEP_WINDDOWN_MINUTES), "basis": basis,
            "message": f"A gentle wind-down around {fmt_hhmm(bed - K.SLEEP_WINDDOWN_MINUTES)} (based on {basis}) can help you ease into bed."}


# --- overview ------------------------------------------------------------------------------------------------------------

def overview(entries: list[dict], details: dict[str, dict], *, goal: dict, today: date, days: int = 30) -> dict[str, Any]:
    since = (today - timedelta(days=days - 1)).isoformat()
    nights = [n for n in nightly(entries, details, today) if n["date"] >= since]
    gaps = []
    out: dict[str, Any] = {"goal": goal, "window_days": days, "nights_logged": len(nights), "disclaimer": DISCLAIMER}
    hours_goal = goal["hours"]
    if not nights:
        gaps.append("No sleep logged in this period yet.")
        out.update(average_hours=None, score=None, last_night=None, regularity=None, debt=None,
                   streak=streak([], hours_goal, today), weekday=None, naps=nap_summary([], days), insights=[],
                   winddown=winddown(hours_goal, bedtime=goal.get("bedtime"), wake=goal.get("wake_time")))
        out["data_gaps"] = gaps
        return out
    avg = sum(n["hours"] for n in nights) / len(nights)
    qualities = [n["quality"] for n in nights if n["quality"] is not None]
    reg = regularity(nights)
    out["average_hours"] = round(avg, 2)
    out["score"] = score(avg, hours_goal, reg["minutes"] if reg else None, sum(qualities) / len(qualities) if qualities else None,
                         goal.get("recommended_max"))
    last = nights[-1]
    out["last_night"] = {"date": last["date"], "hours": last["hours"], "quality": last["quality"],
                         "score": (score(last["hours"], hours_goal, None, last["quality"], goal.get("recommended_max")) or {}).get("value")}
    out["regularity"] = reg
    out["debt"] = sleep_debt(nights, hours_goal, today)
    out["streak"] = streak(nights, hours_goal, today)
    out["weekday"] = weekday_pattern(nights)
    out["naps"] = nap_summary(nights, days)
    out["insights"] = tag_insights(nights)
    out["winddown"] = winddown(hours_goal, bedtime=goal.get("bedtime"), wake=goal.get("wake_time"),
                               recent_bedtimes=[n["bedtime"] for n in nights[-14:] if n.get("bedtime")],
                               recent_wakes=[n["wake"] for n in nights[-14:] if n.get("wake")])
    out["series"] = [{"date": n["date"], "hours": n["hours"], "quality": n["quality"]} for n in nights]
    if reg is None:
        gaps.append("Log a few more nights to see how regular your sleep is.")
    elif reg["basis"] == "duration":
        gaps.append("Add bedtime and wake time to your logs for a better regularity measure.")
    if not any(n["has_details"] for n in nights):
        gaps.append("Add tags such as caffeine or screen time to your sleep logs to look for patterns.")
    elif not out["insights"]:
        gaps.append("Not enough tagged nights yet for patterns; they need at least "
                    f"{K.SLEEP_INSIGHT_MIN_PER_GROUP} nights with and without a tag.")
    out["data_gaps"] = gaps
    return out


# --- loaders -------------------------------------------------------------------------------------------------------------

def load_goal(db: Any, uid: str) -> dict | None:
    return doc_store.get(db, uid, "sleep_goal", "me")


def load_details(db: Any, uid: str, limit: int = 400) -> dict[str, dict]:
    return {str(d["key"]): d["payload"] for d in doc_store.list_docs(db, uid, "sleep_tags", limit=limit)}


def load_entries(db: Any, uid: str, days: int) -> list[dict]:
    return list_domain(db, "sleep", DOMAINS["sleep"], uid, days)["entries"]
