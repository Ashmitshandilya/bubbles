"""Medication schedules, dose records, adherence, interaction checker, allergy warnings, GLP-1 tracker and doctor logbook.

Bubbles stores what the user enters. It NEVER changes a dose, never says to stop a medicine and never recommends a drug.
Every message about a missed dose, a side effect or a possible interaction points to "your pharmacist or prescriber".
Pure functions over plain dicts, plus loaders at the bottom.

Storage (doc_store, no schema change):
  * ``med_schedule`` / key = schedule id  -> the schedule (kinds: regular, as_needed, taper, cycle_pill, glp1)
  * ``med_dose``     / key = "<schedule id>:<YYYY-MM-DD>" -> {"doses": {"08:00": {status, at, reason?, snoozed_until?, site?}}}
  * ``glp1_log``     / key = date -> {appetite 1-5, nausea 0-10, notes?}
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import clinical_constants as K
import doc_store
from condition_rules import _pattern
from wellness_common import InputError, choice, fmt_hhmm, number, parse_date, parse_hhmm, text

KINDS = ("regular", "as_needed", "taper", "cycle_pill", "glp1")
STATUSES = ("taken", "skipped", "snoozed")
PHARMACIST = "ask your pharmacist or prescriber"
MISSED_MESSAGE = ("This dose looks like it slipped by. Every medicine is different, so check the leaflet or "
                  "ask your pharmacist or prescriber what to do about a missed dose.")
SITE_LABELS = {"abdomen_left": "left side of the tummy", "abdomen_right": "right side of the tummy", "thigh_left": "left thigh",
               "thigh_right": "right thigh", "upper_arm_left": "left upper arm", "upper_arm_right": "right upper arm"}
PRESCRIBER_NOTE = "Your prescriber decides your dose; Bubbles never suggests changes to it."
MAX_SCHEDULES = 40


# --- schedule input ------------------------------------------------------------------------------------------------------

def _label(body: dict, key: str, limit: int, required: bool = False) -> str | None:
    v = text(body.get(key), limit, key.replace("_", " "))
    if required and not v:
        raise InputError(f"{key.replace('_', ' ')} is required")
    return v


def normalize_schedule(body: dict, today: date) -> dict[str, Any]:
    """Validate a schedule request into the stored shape. Raises InputError with a user-safe message."""
    kind = choice(body.get("kind") or "regular", KINDS, "kind")
    out: dict[str, Any] = {"name": _label(body, "name", 120, True), "dose_label": _label(body, "dose_label", 80), "kind": kind,
                           "active": bool(body.get("active", True))}
    times_raw = body.get("times") or []
    if not isinstance(times_raw, list) or len(times_raw) > 8:
        raise InputError("times must be a list of up to 8 times like 08:00")
    times = sorted({fmt_hhmm(parse_hhmm(t, "time")) for t in times_raw})
    weekdays = body.get("weekdays") or []
    if not isinstance(weekdays, list) or any(isinstance(w, bool) or not isinstance(w, int) or not 0 <= w <= 6 for w in weekdays):
        raise InputError("weekdays must be numbers 0 (Monday) to 6 (Sunday)")
    out["weekdays"] = sorted(set(weekdays))
    if kind != "as_needed" and not times:
        raise InputError("add at least one time, like 08:00")
    out["times"] = [] if kind == "as_needed" else times
    start = parse_date(body.get("start_date") or today.isoformat(), "start date")
    out["start_date"] = start.isoformat()
    if body.get("end_date") not in (None, ""):
        end = parse_date(body["end_date"], "end date")
        if end < start:
            raise InputError("end date can't be before the start date")
        out["end_date"] = end.isoformat()
    if kind == "glp1":
        if len(out["weekdays"]) > 1:
            raise InputError("a weekly injection has one day of the week")
        if len(out["times"]) != 1:
            raise InputError("add the time of day for the dose")
    if kind == "taper":
        steps = body.get("taper_steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
            raise InputError("add the steps your prescriber gave you (1 to 12)")
        clean = []
        for s in steps:
            if not isinstance(s, dict):
                raise InputError("each taper step needs a date and a dose")
            step: dict[str, Any] = {"from_date": parse_date(s.get("from_date"), "step date").isoformat(),
                                    "dose_label": _label(s, "dose_label", 80, True)}
            if s.get("times"):
                step["times"] = sorted({fmt_hhmm(parse_hhmm(t, "time")) for t in s["times"]})
            clean.append(step)
        out["taper_steps"] = sorted(clean, key=lambda s: s["from_date"])
    if kind == "cycle_pill":
        cyc = body.get("cycle")
        if not isinstance(cyc, dict):
            raise InputError("add the pack type (21 days + 7 off, or 28 day) and the day the pack started")
        out["cycle"] = {"pattern": choice(cyc.get("pattern"), ("21_7", "28"), "pack type"),
                        "pack_start": parse_date(cyc.get("pack_start"), "pack start").isoformat()}
    pills = number(body.get("pill_count"), 0, 10000, "pill count")
    if pills is not None:
        out["pill_count"] = int(pills)
    units = number(body.get("units_per_dose"), 0.25, 10, "units per dose")
    out["units_per_dose"] = units if units is not None else 1.0
    alert = number(body.get("refill_alert_days"), 1, 60, "refill alert days")
    out["refill_alert_days"] = int(alert) if alert is not None else K.MED_REFILL_ALERT_DAYS
    return out


# --- what is scheduled on a day --------------------------------------------------------------------------------------------

def current_taper_step(sched: dict, day: date) -> dict | None:
    steps = [s for s in (sched.get("taper_steps") or []) if s["from_date"] <= day.isoformat()]
    return steps[-1] if steps else None


def doses_for_day(sched: dict, day: date) -> list[dict[str, Any]]:
    """[{time, dose_label, placebo}] scheduled for the day ([] if none, paused or outside the dates)."""
    if not sched.get("active", True) or sched.get("kind") == "as_needed":
        return []
    if day.isoformat() < sched.get("start_date", "0000") or (sched.get("end_date") and day.isoformat() > sched["end_date"]):
        return []
    if sched.get("weekdays") and day.weekday() not in sched["weekdays"]:
        return []
    label, times, placebo = sched.get("dose_label"), list(sched.get("times") or []), False
    if sched.get("kind") == "taper":
        step = current_taper_step(sched, day)
        if step is None:
            return []
        label, times = step["dose_label"], step.get("times") or times
    if sched.get("kind") == "cycle_pill":
        cyc = sched["cycle"]
        n = (day - date.fromisoformat(cyc["pack_start"])).days
        if n < 0:
            return []
        if n % 28 >= 21:
            if cyc["pattern"] == "21_7":
                return []                       # pill-free days
            placebo = True                      # 28-day pack: reminder pills
    return [{"time": t, "dose_label": label, "placebo": placebo} for t in times]


def pill_free_today(sched: dict, day: date) -> bool:
    if sched.get("kind") != "cycle_pill" or not sched.get("active", True):
        return False
    n = (day - date.fromisoformat(sched["cycle"]["pack_start"])).days
    return n >= 0 and n % 28 >= 21 and sched["cycle"]["pattern"] == "21_7"


def _status_of(rec: dict | None, time_min: int, now_min: int) -> str:
    window = K.MED_DOSE_WINDOW_MIN
    if rec:
        if rec.get("status") in ("taken", "skipped"):
            return rec["status"]
        if rec.get("status") == "snoozed":
            until = rec.get("snoozed_until")
            if until and now_min < parse_hhmm(until):
                return "snoozed"
    if now_min < time_min - window:
        return "upcoming"
    return "due" if now_min <= time_min + window else "late"


def due_list(schedules: list[dict], dose_docs: dict[str, dict], now_local: datetime) -> dict[str, Any]:
    """Today's doses with a status each: upcoming / due / late / taken / skipped / snoozed. 'late' is worded kindly and points
    to the pharmacist; it never says what to take."""
    day, now_min = now_local.date(), now_local.hour * 60 + now_local.minute
    items, as_needed, pill_free = [], [], []
    for s in schedules:
        if not s.get("active", True):
            continue
        recs = (dose_docs.get(s["id"]) or {}).get("doses", {})
        if s.get("kind") == "as_needed":
            taken = sum(1 for r in recs.values() if r.get("status") == "taken")
            if day.isoformat() >= s.get("start_date", "0000") and not (s.get("end_date") and day.isoformat() > s["end_date"]):
                as_needed.append({"schedule_id": s["id"], "name": s["name"], "dose_label": s.get("dose_label"), "taken_today": taken})
            continue
        if pill_free_today(s, day):
            pill_free.append({"schedule_id": s["id"], "name": s["name"], "message": "Pill-free day in this pack. No tablet is due."})
        for d in doses_for_day(s, day):
            tmin = parse_hhmm(d["time"])
            rec = recs.get(d["time"])
            status = _status_of(rec, tmin, now_min)
            item = {"schedule_id": s["id"], "name": s["name"], "dose_label": d["dose_label"], "time": d["time"], "status": status,
                    "placebo": d["placebo"], "kind": s["kind"],
                    "window": {"start": fmt_hhmm(tmin - K.MED_DOSE_WINDOW_MIN), "end": fmt_hhmm(tmin + K.MED_DOSE_WINDOW_MIN)}}
            if status == "late":
                item["message"] = MISSED_MESSAGE
            if status == "snoozed" and rec:
                item["snoozed_until"] = rec.get("snoozed_until")
            items.append(item)
    items.sort(key=lambda i: (i["time"], i["name"]))
    return {"date": day.isoformat(), "items": items, "as_needed": as_needed, "pill_free": pill_free,
            "counts": {k: sum(1 for i in items if i["status"] == k) for k in ("upcoming", "due", "late", "taken", "skipped", "snoozed")}}


# --- recording a dose ----------------------------------------------------------------------------------------------------

def record_dose(sched: dict, existing: dict | None, *, day: date, time_key: str | None, status: str, now_utc: datetime,
                now_local: datetime, reason: Any = None, snooze_minutes: Any = None, site: Any = None) -> tuple[dict, dict, float]:
    """Returns (dose doc payload, the record written, pill delta). Pill delta is negative when a tablet was taken, positive when
    a taken record is changed back; the caller applies it to the schedule's pill count."""
    status = choice(status, STATUSES, "status")
    payload = {"schedule_id": sched["id"], "date": day.isoformat(), "doses": dict((existing or {}).get("doses") or {})}
    if sched.get("kind") == "as_needed":
        if status != "taken":
            raise InputError("as-needed medicines are recorded when you take them")
        time_key = time_key or f"prn-{len(payload['doses']) + 1}"
    else:
        scheduled = [d["time"] for d in doses_for_day(sched, day)]
        if not time_key:
            raise InputError("choose which time you are recording")
        time_key = fmt_hhmm(parse_hhmm(time_key, "time"))
        if time_key not in scheduled:
            raise InputError("that time isn't on this medicine's schedule for that day")
    rec: dict[str, Any] = {"status": status, "at": now_utc.astimezone(timezone.utc).isoformat()}
    if status == "skipped":
        rec["reason"] = choice(reason or "other", K.MED_SKIP_REASONS, "reason")
        rec["message"] = ("Thanks for noting that. If a medicine is causing problems, mention it to your pharmacist or prescriber."
                          if rec["reason"] == "side_effects" else "Noted. No judgement; your record stays accurate.")
    if status == "snoozed":
        mins = int(number(snooze_minutes if snooze_minutes is not None else K.MED_SNOOZE_OPTIONS_MIN[1], 1, 600, "snooze minutes"))
        if mins not in K.MED_SNOOZE_OPTIONS_MIN:
            raise InputError("snooze can be " + ", ".join(str(m) for m in K.MED_SNOOZE_OPTIONS_MIN) + " minutes")
        rec["snoozed_until"] = fmt_hhmm(now_local.hour * 60 + now_local.minute + mins)
    if site not in (None, ""):
        rec["site"] = choice(site, K.GLP1_INJECTION_SITES, "site")
    prev = payload["doses"].get(time_key)
    payload["doses"][time_key] = rec
    units = float(sched.get("units_per_dose") or 1.0)
    delta = 0.0
    if status == "taken" and not (prev and prev.get("status") == "taken"):
        delta = -units
    elif status != "taken" and prev and prev.get("status") == "taken":
        delta = units
    rec["time"] = time_key
    return payload, rec, delta


def apply_pill_delta(sched: dict, delta: float) -> dict:
    if sched.get("pill_count") is None or not delta:
        return sched
    return {**sched, "pill_count": max(0, round(sched["pill_count"] + delta))}


def refill_status(sched: dict, today: date) -> dict[str, Any] | None:
    """Days of tablets left from the pill count and the schedule; alert at the user's threshold."""
    if sched.get("pill_count") is None or not sched.get("active", True):
        return None
    left = sched["pill_count"]
    per_dose = float(sched.get("units_per_dose") or 1.0)
    if sched.get("kind") == "as_needed":
        return {"pills_left": left, "days_left": None, "alert": left <= 0, "message": "No tablets left on your count." if left <= 0 else None}
    week = sum(len(doses_for_day(sched, today + timedelta(days=i))) for i in range(7))
    per_day = week * per_dose / 7.0
    if per_day <= 0:
        return {"pills_left": left, "days_left": None, "alert": False, "message": None}
    days_left = left / per_day
    alert = days_left <= sched.get("refill_alert_days", K.MED_REFILL_ALERT_DAYS)
    return {"pills_left": left, "days_left": round(days_left, 1), "alert": alert,
            "message": (f"You may have about {int(days_left)} days of {sched['name']} left, a good time to ask for a refill." if alert else None)}


# --- adherence ----------------------------------------------------------------------------------------------------------

def adherence(schedules: list[dict], dose_docs: dict[tuple[str, str], dict], now_local: datetime, days: int = 30) -> dict[str, Any]:
    """Taken / skipped / not recorded over the window. Placebo pills and as-needed medicines are not counted. Today only counts
    doses whose window has passed. 'Not recorded' means no record, not necessarily missed."""
    today, now_min = now_local.date(), now_local.hour * 60 + now_local.minute
    per: dict[str, dict[str, int]] = {}
    for s in schedules:
        c = per.setdefault(s["id"], {"taken": 0, "skipped": 0, "not_recorded": 0})
        for i in range(days):
            day = today - timedelta(days=i)
            recs = (dose_docs.get((s["id"], day.isoformat())) or {}).get("doses", {})
            for d in doses_for_day(s, day):
                if d["placebo"]:
                    continue
                st = (recs.get(d["time"]) or {}).get("status")
                if st in ("taken", "skipped"):
                    c[st] += 1
                elif day < today or now_min > parse_hhmm(d["time"]) + K.MED_DOSE_WINDOW_MIN:
                    c["not_recorded"] += 1
    total = {k: sum(c[k] for c in per.values()) for k in ("taken", "skipped", "not_recorded")}
    return {"window_days": days, "total": total, "per_schedule": per, **_adherence_summary(total)}


def _adherence_summary(c: dict[str, int]) -> dict[str, Any]:
    n = c["taken"] + c["skipped"] + c["not_recorded"]
    if n < K.MED_ADHERENCE_MIN_DOSES:
        return {"percent": None, "scheduled": n, "message": "Not enough doses yet to show a percentage. Every record you add helps."}
    pct = round(100 * c["taken"] / n)
    msg = ("Steady routine. Nicely done." if pct >= K.MED_ADHERENCE_STEADY_PCT else
           "Some doses weren't recorded. A pill box or an extra reminder can help; if remembering is hard, "
           "it's worth mentioning to your pharmacist or prescriber.")
    return {"percent": pct, "scheduled": n, "message": msg}


# --- interactions and allergies -------------------------------------------------------------------------------------------

def _clean_names(names: Any, limit: int = 30) -> list[str]:
    if not isinstance(names, list) or len(names) > limit:
        raise InputError(f"names must be a list of up to {limit} medicines")
    out = []
    for n in names:
        v = text(n, 100, "name")
        if v and v.lower() not in [o.lower() for o in out]:
            out.append(v)
    return out


def _classes_of(name: str) -> set[str]:
    low = name.lower().replace("_", " ").strip()
    found = set()
    for cls, words in K.DRUG_CLASSES.items():
        pat = _pattern(tuple(words))
        if pat and pat.search(low):
            found.add(cls)
    return found


_LEVEL_ORDER = {"high": 0, "moderate": 1, "timing": 2}


def check_interactions(names: Any) -> list[dict[str, Any]]:
    """Pairs among ``names`` that match the curated list (the pharmacist-reviewed table). Warnings only, never prohibitions."""
    clean = _clean_names(names)
    classes = {n: _classes_of(n) for n in clean}
    found, seen = [], set()
    for rule in K.INTERACTION_RULES:
        for a in (n for n in clean if rule["a"] in classes[n]):
            for b in (n for n in clean if n != a and classes[n] & set(rule["b"])):
                key = (rule["id"], frozenset((a.lower(), b.lower())))
                if key in seen:
                    continue
                seen.add(key)
                found.append({"rule": rule["id"], "names": [a, b], "level": rule["level"], "concern": rule["concern"],
                              "message": _interaction_message(a, b, rule)})
    return sorted(found, key=lambda f: (_LEVEL_ORDER[f["level"]], f["rule"]))


def _interaction_message(a: str, b: str, rule: dict) -> str:
    if rule["level"] == "timing":
        return f"{a} and {b}: {rule['plain']}. Check with your pharmacist about the best timing."
    word = "can interact" if rule["level"] == "high" else "may interact"
    return f"{a} and {b} {word}: {rule['plain']}. Please check with your pharmacist or prescriber about taking them together."


def allergy_warnings(med_names: list[str], allergies: list[str]) -> list[dict[str, Any]]:
    """A medicine whose name, or drug family, matches something the user recorded an allergy to."""
    out = []
    for med in med_names:
        mc = _classes_of(med)
        for allergen in allergies:
            low_a, low_m = allergen.lower().strip(), med.lower().strip()
            pat = _pattern((low_a,)) if low_a else None
            direct = bool(low_a) and (low_a == low_m or bool(pat and pat.search(low_m)))
            family = bool(mc & _classes_of(allergen))
            if direct or family:
                out.append({"medicine": med, "allergen": allergen,
                            "message": f"You recorded an allergy to {allergen}, and {med} may be related. Please check with your pharmacist before taking it."})
    return out


# --- optional RxNav lookup (fail-soft, off by default) -------------------------------------------------------------------------
# NIH retired the RxNav *interaction* API in 2024, so the curated list above stays the source of interaction rules. RxNav's name
# service is still online and is used only to turn a brand name into its generic ingredient so the curated list can match it.

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


def rxnav_enabled() -> bool:
    return os.getenv("BUBBLES_ENABLE_RXNAV", "").strip().lower() in ("1", "true", "yes", "on")


def _http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as resp:   # noqa: S310 - fixed https host
        return json.loads(resp.read().decode("utf-8"))


def rxnav_ingredients(name: str, transport: Callable[[str], dict] | None = None, enabled: bool | None = None) -> list[str]:
    """Generic ingredient names for a brand/generic name, or [] when disabled, unknown or the service fails."""
    if not (rxnav_enabled() if enabled is None else enabled):
        return []
    fetch = transport or _http_json
    try:
        q = urllib.parse.quote(name[:100])
        ids = (fetch(f"{RXNAV_BASE}/rxcui.json?name={q}").get("idGroup") or {}).get("rxnormId") or []
        if not ids or not re.fullmatch(r"[0-9]{1,10}", str(ids[0])):
            return []
        related = fetch(f"{RXNAV_BASE}/rxcui/{ids[0]}/related.json?tty=IN").get("relatedGroup") or {}
        names = [p.get("name") for g in related.get("conceptGroup") or [] for p in g.get("conceptProperties") or []]
        return [str(n).lower() for n in names if n][:5]
    except Exception:  # noqa: BLE001 - lookup is a bonus; any failure falls back to the curated list
        return []


def expand_names(names: list[str], transport: Callable[[str], dict] | None = None, enabled: bool | None = None) -> list[str]:
    out = list(names)
    for n in names[:10]:   # a bounded number of third-party lookups per request
        for g in rxnav_ingredients(n, transport, enabled):
            if g not in [o.lower() for o in out]:
                out.append(g)
    return out[:60]


# --- GLP-1 ---------------------------------------------------------------------------------------------------------------------

def normalize_glp1_log(body: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    appetite = number(body.get("appetite"), 1, 5, "appetite")
    nausea = number(body.get("nausea"), 0, 10, "nausea")
    if appetite is None and nausea is None:
        raise InputError("add appetite (1 to 5) or nausea (0 to 10)")
    if appetite is not None:
        out["appetite"] = round(appetite)
    if nausea is not None:
        out["nausea"] = round(nausea)
    return out


def next_site(last_site: str | None) -> str:
    sites = K.GLP1_INJECTION_SITES
    return sites[(sites.index(last_site) + 1) % len(sites)] if last_site in sites else sites[0]


def glp1_overview(sched: dict | None, dose_docs: dict[tuple[str, str], dict], logs: list[dict], now_local: datetime) -> dict[str, Any]:
    """Dose-day countdown, next injection site, recent appetite/nausea and gentle protein/fluid prompts. No dose advice."""
    out: dict[str, Any] = {"schedule": None, "note": PRESCRIBER_NOTE, "nudges": [], "recent_logs": logs[:14]}
    nudges = out["nudges"]
    if sched:
        today = now_local.date()
        nxt = next((today + timedelta(days=i) for i in range(8) if doses_for_day(sched, today + timedelta(days=i))), None)
        recs = (dose_docs.get((sched["id"], today.isoformat())) or {}).get("doses", {})
        done_today = any(r.get("status") == "taken" for r in recs.values())
        if nxt == today and done_today:
            nxt = next((today + timedelta(days=i) for i in range(1, 9) if doses_for_day(sched, today + timedelta(days=i))), None)
        last_site = None
        for (sid, d), doc in sorted(dose_docs.items(), key=lambda kv: kv[0][1], reverse=True):
            if sid != sched["id"]:
                continue
            sites = [r["site"] for r in (doc.get("doses") or {}).values() if r.get("status") == "taken" and r.get("site")]
            if sites:
                last_site = sites[-1]
                break
        site = next_site(last_site)
        days_until = (nxt - today).days if nxt else None
        out["schedule"] = {"schedule_id": sched["id"], "name": sched["name"], "dose_label": sched.get("dose_label"),
                           "next_dose_date": nxt.isoformat() if nxt else None, "days_until": days_until,
                           "dose_day_today": nxt == today,
                           "reminder": ("Today is your dose day." if nxt == today else "Your dose day is tomorrow." if days_until == 1 else None),
                           "suggested_site": site, "suggested_site_label": SITE_LABELS[site], "last_site": last_site,
                           "site_note": "Rotating the spot each time is usually suggested. Follow the instructions you were given."}
    nudges.append("Small, protein-rich meals can help when you do not feel like eating much.")
    nudges.append("Sip fluids through the day; dehydration can make nausea feel worse.")
    recent = logs[:7]
    nauseas = [l["nausea"] for l in recent if l.get("nausea") is not None]
    appetites = [l["appetite"] for l in recent if l.get("appetite") is not None]
    if nauseas and max(nauseas) >= K.GLP1_NAUSEA_TALK_AT:
        nudges.append("Your nausea has been strong lately. Please tell your prescriber or pharmacist; they can help, and they decide any change.")
    if appetites and sum(appetites) / len(appetites) <= 2:
        nudges.append("Your appetite has been low. Try to keep eating regular small meals, and mention it at your next check-in.")
    return out


# --- doctor logbook -----------------------------------------------------------------------------------------------------------

def logbook(schedules: list[dict], dose_docs: dict[tuple[str, str], dict], now_local: datetime, days: int,
            allergies: list[str], glp1_logs: list[dict] | None = None) -> dict[str, Any]:
    """Data for a printable medication logbook: each medicine, how it was taken, skip reasons, allergies and interaction flags."""
    today = now_local.date()
    adh = adherence(schedules, dose_docs, now_local, days)
    meds, lines = [], [f"Medication logbook, last {days} days (generated {today.isoformat()} by Bubbles)", ""]
    for s in schedules:
        reasons: dict[str, int] = {}
        last_taken = None
        for (sid, d), doc in dose_docs.items():
            if sid != s["id"] or d < (today - timedelta(days=days - 1)).isoformat():
                continue
            for r in (doc.get("doses") or {}).values():
                if r.get("status") == "skipped":
                    reasons[r.get("reason", "other")] = reasons.get(r.get("reason", "other"), 0) + 1
                if r.get("status") == "taken" and (last_taken is None or d > last_taken):
                    last_taken = d
        c = adh["per_schedule"].get(s["id"], {"taken": 0, "skipped": 0, "not_recorded": 0})
        summary = _adherence_summary(c)
        entry = {"name": s["name"], "dose_label": s.get("dose_label"), "kind": s["kind"], "schedule": describe(s), "active": s.get("active", True),
                 "taken": c["taken"], "skipped": c["skipped"], "not_recorded": c["not_recorded"], "percent": summary["percent"],
                 "skip_reasons": reasons, "last_taken": last_taken}
        meds.append(entry)
        pct = f", {summary['percent']}% of scheduled doses recorded as taken" if summary["percent"] is not None else ""
        lines.append(f"- {s['name']} {s.get('dose_label') or ''} ({entry['schedule']}): taken {c['taken']}, skipped {c['skipped']}, "
                     f"not recorded {c['not_recorded']}{pct}.")
        if reasons:
            lines.append("    Skip reasons: " + ", ".join(f"{k.replace('_', ' ')} x{v}" for k, v in reasons.items()))
    names = [s["name"] for s in schedules if s.get("active", True)]
    flags = check_interactions(names) if names else []
    allergy = allergy_warnings(names, allergies)
    lines += ["", "Allergies: " + (", ".join(allergies) if allergies else "none recorded")]
    if flags:
        lines.append("Possible interactions to ask about: " + "; ".join(f"{f['names'][0]} + {f['names'][1]}" for f in flags))
    lines += ["", "Recorded by the patient in the Bubbles app. Not a prescription or medical advice."]
    return {"generated_on": today.isoformat(), "window_days": days, "medications": meds, "allergies": allergies,
            "interaction_flags": flags, "allergy_warnings": allergy, "adherence": {k: adh[k] for k in ("total", "percent", "scheduled", "message")},
            "glp1_logs": (glp1_logs or [])[:30], "text": "\n".join(lines)}


def describe(s: dict) -> str:
    if s["kind"] == "as_needed":
        return "as needed"
    days = "daily" if not s.get("weekdays") else "on " + ", ".join(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[d] for d in s["weekdays"])
    base = f"{days} at {', '.join(s.get('times') or [])}"
    if s["kind"] == "cycle_pill":
        base += " (21 days on, 7 off)" if s["cycle"]["pattern"] == "21_7" else " (28-day pack)"
    if s["kind"] == "taper":
        base += " (stepped plan from your prescriber)"
    return base


# --- loaders ------------------------------------------------------------------------------------------------------------------

def load_schedules(db: Any, uid: str) -> list[dict]:
    docs = doc_store.list_docs(db, uid, "med_schedule", limit=MAX_SCHEDULES * 2)
    out = [{**d["payload"], "id": str(d["key"])} for d in docs]
    return sorted(out, key=lambda s: (s["name"].lower(), s["id"]))[:MAX_SCHEDULES]


def load_schedule(db: Any, uid: str, sid: str) -> dict | None:
    p = doc_store.get(db, uid, "med_schedule", sid)
    return {**p, "id": sid} if p else None


def save_schedule(db: Any, uid: str, sched: dict) -> dict:
    body = {k: v for k, v in sched.items() if k != "id"}
    doc_store.put(db, uid, "med_schedule", sched["id"], body)
    return sched


def load_dose_docs(db: Any, uid: str, days: int) -> dict[tuple[str, str], dict]:
    """{(schedule id, date): payload} for the recent window. Newest first, capped by doc_store.LIST_LIMIT."""
    since = (datetime.now(timezone.utc).date() - timedelta(days=days + 2)).isoformat()
    out: dict[tuple[str, str], dict] = {}
    for d in doc_store.list_docs(db, uid, "med_dose", limit=doc_store.LIST_LIMIT):
        p = d["payload"]
        if p.get("date") and p["date"] >= since and p.get("schedule_id"):
            out[(p["schedule_id"], p["date"])] = p
    return out


def dose_docs_for_day(all_docs: dict[tuple[str, str], dict], day: str) -> dict[str, dict]:
    return {sid: p for (sid, d), p in all_docs.items() if d == day}


def save_dose_doc(db: Any, uid: str, payload: dict) -> None:
    key = f"{payload['schedule_id']}:{payload['date']}"
    doc_store.put(db, uid, "med_dose", key, payload, when=f"{payload['date']}T12:00:00+00:00")


def load_glp1_logs(db: Any, uid: str, limit: int = 30) -> list[dict]:
    return [{"date": d["key"], **d["payload"]} for d in doc_store.list_docs(db, uid, "glp1_log", limit=limit)]
