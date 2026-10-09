"""/cycle/* endpoints: overview, calendar, day logs, period start/end, settings, insights, report, factors, education,
partner view and data deletion.

All routes are authenticated (except the revocable partner link), owner-scoped and bounded. Data lives in owner-scoped
``doc_store`` documents (no schema change):

    cycle_day      key = ISO date   one day's log (see ``normalize_day_log``)
    cycle_settings key = "main"     mode, luteal override, privacy, pregnancy / postpartum dates
    cycle_index    key = "main"     period starts / ends (and starts the user removed) so history beyond 500 days survives
    cycle_partner  key = sha256(token)[:40]   opt-in, revocable partner link (predictions only)

When a period starts the existing ``cycle`` tracker domain is written too (health_logs.save_domain), and day logs are
mirrored as one idempotent analytics event, so insights and chat keep working - unless the user chose "local only".
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

import clinical_constants as K
import cycle_content as content
import cycle_engine as engine
import doc_store
from cycle_flags import assess_notes, compute_flags, day_flags
from db_access import is_permission_denied
from health_logs import DOMAINS, LBS_PER_KG, list_domain, save_domain

DAY_KIND, SETTINGS_KIND, INDEX_KIND, PARTNER_KIND, PARTNER_OWNER_KIND = "cycle_day", "cycle_settings", "cycle_index", "cycle_partner", "cycle_partner_owner"
ALL_KINDS = (DAY_KIND, SETTINGS_KIND, INDEX_KIND, PARTNER_KIND, PARTNER_OWNER_KIND)
ANALYTICS_TABLE = "extracted_health_events"
MAX_BODY_BYTES = 40_000
MAX_NOTES = 2000
MIN_YEAR = 1990
FLOWS = ("none", "spotting", "light", "medium", "heavy")
PRODUCTS = ("pad", "tampon", "cup", "disc", "period_underwear", "liner", "none")
DISCHARGES = ("none", "dry", "sticky", "creamy", "watery", "egg_white", "other")
PROTECTIONS = ("none", "condom", "pill", "iud", "withdrawal", "other")
OVULATION_TESTS = ("negative", "faint", "positive", "peak")
PREGNANCY_TESTS = ("negative", "faint", "positive")
PAIN_TYPES = ("cramps", "lower_back", "headache", "migraine", "breast", "pelvic", "ovulation", "joint", "other")
WEATHER_LABELS = {"bright": "Bright day", "steady": "Steady day", "heavier": "Heavier day"}
PARTNER_SHARES = ["Your next period as a date range", "A general phase hint"]
DAY_FIELDS = {"flow", "products", "soaking_hourly", "pain_level", "pain_types", "energy", "sleep_quality", "factors", "custom_factors",
              "discharge", "sex", "ovulation_test", "pregnancy_test", "bbt_c", "medications", "birth_control_taken", "period_start",
              "period_end", "notes"}
SETTINGS_FIELDS = {"mode", "age_group", "luteal_days", "temp_unit", "privacy", "pregnancy", "postpartum"}
DEFAULT_SETTINGS: dict[str, Any] = {
    "mode": "track", "age_group": "adult", "luteal_days": None, "temp_unit": "c", "privacy": {"local_only": False},
    "partner_share": {"enabled": False, "created_at": None}, "pregnancy": {"lmp": None, "due_date": None},
    "postpartum": {"delivery_date": None, "breastfeeding": None}, "mode_history": [],
}
CLINICIAN_QUESTIONS = {
    "cycle_length": "Is my cycle length something we should look into?",
    "sudden_change": "Could anything explain this change from my usual cycle?",
    "long_period": "Is the length of my periods typical, and is it worth checking anything?",
    "missed_periods": "What could explain my missing periods, and are any checks worth doing?",
    "bleeding_between_periods": "What could explain bleeding between my periods?",
    "spotting_between": "Is spotting between periods something to keep an eye on?",
    "bleeding_after_long_gap": "What should we check given bleeding after a long gap?",
    "severe_pain": "What could explain strong pain with my periods, and what could help?",
    "heavy_bleeding": "How should I handle very heavy bleeding in future?",
}


# --------------------------------------------------------------------------------------------------
# validation helpers (every failure is a 422 with a plain string)
# --------------------------------------------------------------------------------------------------

def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _clean_text(value: Any, label: str, limit: int) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, bool)):
        raise _bad(f"{label} must be text")
    text = str(value).replace(chr(0), "").encode("utf-8", "ignore").decode("utf-8").strip()
    return text[:limit] or None


def _enum(body: dict, key: str, allowed: tuple[str, ...]) -> str | None:
    value = body.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value not in allowed:
        raise _bad(f"{key} must be one of: {', '.join(allowed)}")
    return value


def _bool(body: dict, key: str, default: bool = False) -> bool:
    value = body.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise _bad(f"{key} must be true or false")
    return value


def _int(body: dict, key: str, lo: int, hi: int) -> int | None:
    value = body.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _bad(f"{key} must be a number")
    if value != value or not lo <= value <= hi or value != int(value):
        raise _bad(f"{key} must be a whole number from {lo} to {hi}")
    return int(value)


def _str_list(body: dict, key: str, max_items: int, max_len: int, allowed: tuple[str, ...] | None = None) -> list[str]:
    value = body.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise _bad(f"{key} must be a list")
    if len(value) > max_items:
        raise _bad(f"{key} can have at most {max_items} items")
    out: list[str] = []
    for item in value:
        text = _clean_text(item, key, max_len)
        if text is None:
            continue
        if allowed is not None and text not in allowed:
            raise _bad(f"{key} contains an unknown value")
        if text not in out:
            out.append(text)
    return out


def parse_day(value: Any, label: str = "date") -> date:
    day = engine.parse_day(value) if isinstance(value, (str, date)) and value != "" else None
    if day is None or (isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip())):
        raise _bad(f"{label} must be a calendar day like 2026-10-08")
    return day


def _utc_today() -> date:
    """The user's day (client timezone when sent). Name kept for existing callers."""
    from calc_core import local_today
    return local_today()


def _today(raw: Any = None) -> date:
    """The user's local 'today' when the client supplies it (within a day of UTC), else the UTC date."""
    if raw in (None, ""):
        return _utc_today()
    day = parse_day(raw, "today")
    return day if abs((day - _utc_today()).days) <= 1 else _utc_today()


def _check_log_date(day: date) -> None:
    if day < _utc_today() - timedelta(days=3650) or day.year < MIN_YEAR:
        raise _bad("date is too far in the past")
    if day > _utc_today() + timedelta(days=1):
        raise _bad("Pick a date up to today")


def normalize_day_log(body: Any) -> dict:
    """Strictly validated, fully populated day log (see frontend/app/lib/cycle-types.ts DayLog)."""
    if not isinstance(body, dict):
        raise _bad("Request body must be a JSON object")
    unknown = sorted(set(body) - DAY_FIELDS)
    if unknown:
        raise _bad(f"Unknown field: {unknown[0]}")
    sex = body.get("sex")
    if sex is not None:
        if not isinstance(sex, dict) or set(sex) - {"had", "protection"}:
            raise _bad("sex must be an object with had and protection")
        sex = {"had": _bool(sex, "had"), "protection": _enum(sex, "protection", PROTECTIONS)}
    bbt = body.get("bbt_c")
    if bbt in (None, ""):
        bbt = None
    else:
        if isinstance(bbt, bool) or not isinstance(bbt, (int, float)) or bbt != bbt:
            raise _bad("bbt_c must be a number")
        lo, hi = K.BBT_VALID_C
        if not lo <= bbt <= hi:
            raise _bad(f"Temperature must be between {lo:g} and {hi:g} °C")
        bbt = round(float(bbt), 2)
    birth_control = body.get("birth_control_taken")
    if birth_control is not None and not isinstance(birth_control, bool):
        raise _bad("birth_control_taken must be true, false or empty")
    factors = _str_list(body, "factors", 40, 60)
    for factor in factors:
        if factor not in content.CHIP_BY_ID:
            raise _bad("factors contains an unknown factor")
    return {
        "flow": _enum(body, "flow", FLOWS), "products": _str_list(body, "products", 7, 20, PRODUCTS),
        "soaking_hourly": _bool(body, "soaking_hourly"), "pain_level": _int(body, "pain_level", 0, 10),
        "pain_types": _str_list(body, "pain_types", 9, 20, PAIN_TYPES), "energy": _int(body, "energy", 1, 5),
        "sleep_quality": _int(body, "sleep_quality", 1, 5), "factors": factors,
        "custom_factors": _str_list(body, "custom_factors", 10, 40), "discharge": _enum(body, "discharge", DISCHARGES), "sex": sex,
        "ovulation_test": _enum(body, "ovulation_test", OVULATION_TESTS), "pregnancy_test": _enum(body, "pregnancy_test", PREGNANCY_TESTS),
        "bbt_c": bbt, "medications": _str_list(body, "medications", 10, 60), "birth_control_taken": birth_control,
        "period_start": _bool(body, "period_start"), "period_end": _bool(body, "period_end"),
        "notes": _clean_text(body.get("notes"), "notes", MAX_NOTES),
    }


async def _json_body(request: Request, required: bool = True) -> dict:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request is too large")
    if not raw.strip():
        if required:
            raise _bad("Request body must be valid JSON")
        return {}
    try:
        body = await request.json()
    except (ValueError, RecursionError):
        raise _bad("Request body must be valid JSON")
    if not isinstance(body, dict):
        raise _bad("Request body must be a JSON object")
    return body


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10] if not isinstance(value, datetime) else value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


def _log(component: str, operation: str, error: Exception) -> None:
    try:
        from logging_util import logger
        logger.warning(component=component, operation=operation, error=error, fallback_action="continued_without")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------------------------------

def _logs(db: Any, uid: str) -> dict[date, dict]:
    out: dict[date, dict] = {}
    for doc in doc_store.list_docs(db, uid, DAY_KIND, limit=doc_store.LIST_LIMIT):
        day = engine.parse_day(doc.get("key"))
        if day and isinstance(doc.get("payload"), dict):
            out[day] = doc["payload"]
    return out


def _settings(db: Any, uid: str) -> dict:
    stored = doc_store.get(db, uid, SETTINGS_KIND, "main") or {}
    merged = {**DEFAULT_SETTINGS, **{k: v for k, v in stored.items() if k in DEFAULT_SETTINGS}}
    for key in ("privacy", "partner_share", "pregnancy", "postpartum"):
        merged[key] = {**DEFAULT_SETTINGS[key], **(stored.get(key) if isinstance(stored.get(key), dict) else {})}
    if merged["mode"] not in engine.MODES:
        merged["mode"] = "track"
    return merged


def _index(db: Any, uid: str) -> dict:
    stored = doc_store.get(db, uid, INDEX_KIND, "main") or {}
    return {k: [d for d in (stored.get(k) or []) if isinstance(d, str)] for k in ("starts", "ends", "suppressed")}


def _tracker_starts(db: Any, uid: str) -> set[date]:
    """Period starts from the older /health/cycle tracker (primary or compat store)."""
    try:
        entries = list_domain(db, "cycle", DOMAINS["cycle"], uid, 730)["entries"]
    except Exception as exc:  # noqa: BLE001 - the tracker being unreadable must not break the cycle page
        _log("CYCLE", "tracker_starts", exc)
        return set()
    return {d for d in (engine.parse_day(e.get("date")) for e in entries if e.get("phase", "period") == "period") if d}


def _context(db: Any, uid: str, today: date) -> dict:
    settings = _settings(db, uid)
    logs = _logs(db, uid)
    index = _index(db, uid)
    tracker = _tracker_starts(db, uid)
    suppressed = {engine.parse_day(s) for s in index["suppressed"]}
    extra_starts = {d for d in (*(engine.parse_day(s) for s in index["starts"]), *tracker) if d and d not in suppressed}
    extra_ends = [d for d in (engine.parse_day(s) for s in index["ends"]) if d]
    state = engine.analyse(
        logs, today=today, extra_starts=extra_starts, extra_ends=extra_ends, mode=settings["mode"], luteal_days=settings["luteal_days"],
        delivery_date=engine.parse_day(settings["postpartum"].get("delivery_date")), lmp=engine.parse_day(settings["pregnancy"].get("lmp")),
        due_date=engine.parse_day(settings["pregnancy"].get("due_date")))
    state["age_group"] = settings["age_group"]
    return {"settings": settings, "logs": logs, "state": state, "tracker_starts": tracker, "index": index}


def _sync_index(db: Any, uid: str, day: date, *, start: bool | None = None, end: bool | None = None, tracker_starts: set[date] = frozenset()) -> None:
    index = _index(db, uid)
    iso = day.isoformat()
    for key, flag in (("starts", start), ("ends", end)):
        if flag is None:
            continue
        values = set(index[key])
        values.add(iso) if flag else values.discard(iso)
        index[key] = sorted(values)[-300:]
    if start is not None:
        suppressed = set(index["suppressed"])
        if start:
            suppressed.discard(iso)
        elif day in tracker_starts:
            suppressed.add(iso)   # the old tracker still has this start; remember that the user took it off
        index["suppressed"] = sorted(suppressed)[-100:]
    doc_store.put(db, uid, INDEX_KIND, "main", index)


def _mirror_day(db: Any, uid: str, day: date, log: dict | None, local_only: bool) -> None:
    """One idempotent analytics event per logged day so insights / chat can see symptoms (best effort)."""
    key = f"cycle_day:{day.isoformat()}"
    try:
        existing = (db.table(ANALYTICS_TABLE).select("id").eq("user_id", uid).eq("extracted_data->_prov->>key", key).execute().data or [])
        symptoms = [content.CHIP_BY_ID[f]["label"] for f in (log or {}).get("factors", []) if content.CHIP_BY_ID[f]["signal"] == "symptom"][:8]
        pain = (log or {}).get("pain_level") or 0
        notable = bool(log) and not local_only and (symptoms or pain >= 1 or log.get("flow") not in (None, "none"))
        if not notable:
            for row in existing:
                db.table(ANALYTICS_TABLE).delete().eq("id", row["id"]).eq("user_id", uid).execute()
            return
        data = {"name": "cycle day log", "date": day.isoformat(), "symptoms": symptoms, "flow": log.get("flow"), "severity": pain or None,
                "_prov": {"source": "tracker", "domain": "cycle", "store": "mirror", "feature": "cycle_day", "key": key}}
        data = {k: v for k, v in data.items() if v not in (None, [], "")}
        if existing:
            db.table(ANALYTICS_TABLE).update({"extracted_data": data}).eq("id", existing[0]["id"]).eq("user_id", uid).execute()
        else:
            db.table(ANALYTICS_TABLE).insert({"user_id": uid, "event_type": "menstrual_symptom", "confidence": 1.0,
                                              "extraction_status": "confirmed", "user_confirmed": True, "message_id": None,
                                              "extracted_data": data}).execute()
    except Exception as exc:  # noqa: BLE001
        _log("CYCLE", "mirror_day", exc)


def _purge_mirrors(db: Any, uid: str) -> int:
    """Remove the analytics events this feature and the cycle tracker mirrored (used by local-only mode)."""
    try:
        rows = (db.table(ANALYTICS_TABLE).delete().eq("user_id", uid).eq("extracted_data->_prov->>domain", "cycle")
                .eq("extracted_data->_prov->>store", "mirror").execute().data or [])
        return len(rows)
    except Exception as exc:  # noqa: BLE001
        if not is_permission_denied(exc):
            _log("CYCLE", "purge_mirrors", exc)
        return 0


# --------------------------------------------------------------------------------------------------
# response builders
# --------------------------------------------------------------------------------------------------

def _phase_json(phase: str | None, estimated: bool = True) -> dict | None:
    if not phase:
        return None
    info = content.PHASE_INFO[phase]
    return {"id": phase, "label": info["label"], "summary": info["summary"], "estimated": estimated}


def _weather(state: dict, log: dict | None) -> dict | None:
    if state["mode"] == "pregnancy":
        phase = None
    else:
        phase = state["phase"]
    pms = state.get("pms")
    pms_today = bool(pms and pms["from"] <= state["today"] <= pms["to"])
    tone = engine.weather_tone(phase, log, pms_today)
    lines = content.WEATHER_LINES[tone].get(phase or "none") or content.WEATHER_LINES[tone]["none"]
    return {"tone": tone, "label": WEATHER_LABELS[tone], "line": lines[state["today"].toordinal() % len(lines)]}


def _stats_json(state: dict) -> dict:
    s = state["length_stats"]
    return {"cycles_used": s["n"], "average_length": round(s["mean"], 1) if s["mean"] is not None else None, "sd": s["sd"],
            "shortest": s["min"], "longest": s["max"], "recent_lengths": state["lengths"],
            "period_length_average": state["period_length_average"], "regularity": state["regularity"], "irregular": state["irregular"]}


def build_overview(ctx: dict) -> dict:
    state, settings, logs = ctx["state"], ctx["settings"], ctx["logs"]
    today, mode = state["today"], state["mode"]
    flags = compute_flags(state, logs)
    log = logs.get(today)
    has_data = bool(state["starts"] or logs)
    pregnancy = state["pregnancy"]
    if pregnancy:
        pregnancy = {**pregnancy, "note": content.PREGNANCY_WEEK_NOTES.get(pregnancy["week"], ""),
                     "next_step": content.PREGNANCY_NEXT_STEPS[pregnancy["trimester"]]}
        pregnancy.pop("lmp", None)
    postpartum = state["postpartum"]
    if postpartum:
        postpartum = {**postpartum, "note": content.POSTPARTUM_NOTES["lochia" if postpartum["lochia_expected"] else "settling"]}
    empty = None
    if mode == "pregnancy" and not pregnancy:
        empty = "Add your due date or the first day of your last period in the Modes tab to see your week."
    elif not has_data:
        empty = "Log the first day of your last period (a past date is fine) and Bubbles will start learning your rhythm."
    elif not state["starts"]:
        empty = "Mark the first day of a period to start predictions."
    notices = [content.NOT_CONTRACEPTION_NOTICE]
    if mode in ("postpartum", "perimenopause"):
        notices.append(content.POSTPARTUM_NOTES["low_confidence"] if mode == "postpartum" else content.PERIMENOPAUSE_NOTE)
    elif mode == "birth_control":
        notices.append(content.BIRTH_CONTROL_NOTE)
    elif mode == "conceive":
        notices.append(content.CONCEIVE_NOTE)
    return _jsonable({
        "status": "success", "today": today, "mode": mode, "mode_label": content.MODE_LABELS[mode], "has_data": has_data,
        "cycle_day": state["cycle_day"] if mode != "pregnancy" else None, "phase": _phase_json(state["phase"]) if mode != "pregnancy" else None,
        "last_period_start": state["last_start"], "next_period": state["next_period"], "ovulation": state["ovulation"],
        "fertile_window": state["fertile_window"], "fertility_note": state["fertility_note"], "confidence": state["confidence"],
        "confidence_note": state["confidence_note"], "stats": _stats_json(state), "pms": state["pms"], "flags": flags,
        "urgent": next((f for f in flags if f["severity"] == "urgent"), None), "weather": _weather(state, log),
        "pregnancy": pregnancy, "postpartum": postpartum, "today_log": log, "notices": notices,
        "privacy": {"local_only": bool(settings["privacy"].get("local_only"))}, "empty_state": empty,
    })


def _day_response(ctx: dict, day: date, *, safety: dict | None = None, with_overview: bool = False, saved: bool | None = None) -> dict:
    state, log = ctx["state"], ctx["logs"].get(day)
    cycle_day, phase = engine.locate(state, day) if state["mode"] != "pregnancy" else (None, None)
    out = {"status": "success", "date": day.isoformat(), "log": log, "cycle_day": cycle_day, "phase": _phase_json(phase),
           "flags": [] if safety else day_flags(log, state["mode"]), "safety": safety,
           "overview": build_overview(ctx) if with_overview and not safety else None}
    if saved is not None:
        out["saved"] = saved
    return out


# --------------------------------------------------------------------------------------------------
# mutations (sync; the async routes call them through the thread pool)
# --------------------------------------------------------------------------------------------------

def save_day(db: Any, uid: str, day: date, log: dict, today: date, *, safety: dict | None = None) -> dict:
    ctx = _context(db, uid, today)
    previous = ctx["logs"].get(day) or {}
    local_only = bool(ctx["settings"]["privacy"].get("local_only"))
    doc_store.put(db, uid, DAY_KIND, day.isoformat(), log, when=f"{day.isoformat()}T12:00:00+00:00")
    if bool(previous.get("period_start")) != log["period_start"] or bool(previous.get("period_end")) != log["period_end"]:
        _sync_index(db, uid, day, start=log["period_start"], end=log["period_end"], tracker_starts=ctx["tracker_starts"])
    if log["period_start"] and not previous.get("period_start") and day not in ctx["tracker_starts"] and not local_only:
        _write_tracker_start(db, uid, day)
    _mirror_day(db, uid, day, log, local_only)
    return _day_response(_context(db, uid, today), day, safety=safety, with_overview=True, saved=True)


def _write_tracker_start(db: Any, uid: str, day: date) -> None:
    try:
        save_domain(db, "cycle", DOMAINS["cycle"], uid, {"phase": "period", "date": day.isoformat()})
    except Exception as exc:  # noqa: BLE001 - the cycle document is the source of truth; the tracker copy is a convenience
        _log("CYCLE", "tracker_start", exc)


def mark_period(db: Any, uid: str, day: date, today: date, *, start: bool) -> dict:
    ctx = _context(db, uid, today)
    log = {**normalize_day_log({}), **(ctx["logs"].get(day) or {})}
    if start:
        log["period_start"] = True
    else:
        near = [s for s in ctx["state"]["all_starts"] if s <= day and (day - s).days <= K.PERIOD_MAX_PLAUSIBLE_DAYS - 1]
        if not near:
            raise _bad("Bubbles cannot find a period start in the 14 days before that date. Log when it started first.")
        log["period_end"] = True
    return save_day(db, uid, day, log, today)


# --------------------------------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------------------------------

def _merge_settings(current: dict, patch: dict, today: date) -> dict:
    if not isinstance(patch, dict):
        raise _bad("Request body must be a JSON object")
    if "partner_share" in patch or "mode_history" in patch:
        raise _bad("Partner sharing is changed with /cycle/partner-view")
    unknown = sorted(set(patch) - SETTINGS_FIELDS)
    if unknown:
        raise _bad(f"Unknown setting: {unknown[0]}")
    new = {**current, "privacy": dict(current["privacy"]), "pregnancy": dict(current["pregnancy"]), "postpartum": dict(current["postpartum"])}
    if "mode" in patch:
        new["mode"] = _enum(patch, "mode", engine.MODES) or current["mode"]
    if "age_group" in patch:
        new["age_group"] = _enum(patch, "age_group", ("adult", "teen")) or current["age_group"]
    if "temp_unit" in patch:
        new["temp_unit"] = _enum(patch, "temp_unit", ("c", "f")) or current["temp_unit"]
    if "luteal_days" in patch:
        new["luteal_days"] = _int(patch, "luteal_days", K.LUTEAL_RANGE_DAYS[0], K.LUTEAL_RANGE_DAYS[1])
    for group, fields in (("privacy", ("local_only",)), ("pregnancy", ("lmp", "due_date")), ("postpartum", ("delivery_date", "breastfeeding"))):
        if group not in patch:
            continue
        part = patch[group]
        if not isinstance(part, dict) or set(part) - set(fields):
            raise _bad(f"{group} has unknown fields")
        for field in fields:
            if field not in part:
                continue
            value = part[field]
            if field == "local_only":
                new[group][field] = _bool(part, field)
            elif field == "breastfeeding":
                if value is not None and not isinstance(value, bool):
                    raise _bad("breastfeeding must be true, false or empty")
                new[group][field] = value
            else:
                day = None if value in (None, "") else parse_day(value, field)
                if day is not None:
                    low, high = {"lmp": (-300, 0), "due_date": (-30, 300), "delivery_date": (-1100, 0)}[field]
                    if not today + timedelta(days=low) <= day <= today + timedelta(days=high):
                        raise _bad(f"{field} is out of range")
                new[group][field] = day.isoformat() if day else None
    if new["mode"] != current["mode"]:
        new["mode_history"] = [*current["mode_history"], {"mode": new["mode"], "since": today.isoformat()}][-20:]
    return new


# --------------------------------------------------------------------------------------------------
# insights / report
# --------------------------------------------------------------------------------------------------

def _tracker_series(db: Any, uid: str) -> dict[str, list[tuple[date, float]]]:
    out: dict[str, list[tuple[date, float]]] = {"sleep_hours": [], "tracker_mood": [], "weight_kg": []}
    plan = (("sleep", "duration", "sleep_hours", 1.0), ("mood", "mood", "tracker_mood", 1.0), ("weight", "weight", "weight_kg", 1 / LBS_PER_KG))
    for slug, field, target, factor in plan:
        try:
            entries = list_domain(db, slug, DOMAINS[slug], uid, 365)["entries"]
        except Exception as exc:  # noqa: BLE001
            _log("CYCLE", f"tracker_{slug}", exc)
            continue
        for e in entries:
            day, value = engine.parse_day(e.get("date")), e.get(field)
            if day and isinstance(value, (int, float)) and not isinstance(value, bool):
                out[target].append((day, float(value) * factor))
    return out


def build_insights(db: Any, uid: str, today: date) -> dict:
    ctx = _context(db, uid, today)
    result = engine.compute_insights(ctx["state"], ctx["logs"], _tracker_series(db, uid))
    notes = ["Patterns come from what you logged, so days you did not log are not counted.",
             "A pattern is not a cause: sleep, stress, illness and many other things move these numbers too."]
    if ctx["state"]["mode"] in ("birth_control", "postpartum", "perimenopause", "pregnancy"):
        notes.append("Phases are rougher estimates in your current mode, so read these patterns lightly.")
    return {"status": "success", **_jsonable(result), "notes": notes,
            "disclaimer": "These are patterns in your own logs, not causes, and not medical advice."}


def build_report(db: Any, uid: str, today: date, months: int, include_notes: bool) -> dict:
    ctx = _context(db, uid, today)
    state, logs = ctx["state"], ctx["logs"]
    since = today - timedelta(days=int(months * 30.4))
    window_logs = {d: l for d, l in logs.items() if since <= d <= today}
    cycles = [c for c in state["cycles"] if c["start"] >= since][-24:]
    counts: dict[str, int] = {}
    for log in window_logs.values():
        for f in set(log.get("factors", [])):
            chip = content.CHIP_BY_ID[f]
            if chip["signal"] == "symptom":
                counts[chip["label"]] = counts.get(chip["label"], 0) + 1
    logged = len(window_logs) or 1
    symptoms = [{"label": k, "days": v, "share": round(v / logged, 2)} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:12]]
    pains = [l["pain_level"] for l in window_logs.values() if l.get("pain_level") is not None]
    meds = sorted({m for l in window_logs.values() for m in l.get("medications", [])})[:30]
    flags = compute_flags(state, logs)
    questions = [CLINICIAN_QUESTIONS[f["id"]] for f in flags if f["id"] in CLINICIAN_QUESTIONS]
    questions += ["Is my overall pattern typical for me?", "Is there anything I should keep tracking before the next visit?"]
    s = state["length_stats"]
    notes = None
    if include_notes:
        notes = [{"date": d.isoformat(), "text": l["notes"]} for d, l in sorted(window_logs.items(), reverse=True) if l.get("notes")][:20]
    nxt = state["next_period"]
    return _jsonable({
        "status": "success", "generated_on": today, "mode": state["mode"], "mode_label": content.MODE_LABELS[state["mode"]],
        "window": {"from": since, "to": today, "months": months},
        "summary": {"cycles_tracked": s["n"], "average_length": round(s["mean"], 1) if s["mean"] is not None else None, "sd": s["sd"],
                    "shortest": s["min"], "longest": s["max"], "period_length_average": state["period_length_average"],
                    "regularity": state["regularity"], "last_period_start": state["last_start"],
                    "next_period_estimate": nxt["date"] if nxt else None, "confidence": state["confidence"]},
        "cycles": [{"start": c["start"], "length": c["length"], "period_days": c["period_days"]} for c in cycles],
        "symptoms": symptoms,
        "pain": {"logged_days": len(pains), "average": round(mean(pains), 1) if pains else None, "maximum": max(pains) if pains else None,
                 "days_at_or_above_severe": sum(1 for p in pains if p >= K.SEVERE_PAIN_LEVEL)},
        "flags": flags, "medications": meds, "questions_for_clinician": questions, "notes": notes,
        "disclaimers": list(content.DISCLAIMER_LINES),
    })


# --------------------------------------------------------------------------------------------------
# partner view
# --------------------------------------------------------------------------------------------------

def _partner_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:40]


def _partner_status(settings: dict) -> dict:
    share = settings["partner_share"]
    return {"status": "success", "enabled": bool(share.get("enabled")), "created_at": share.get("created_at"),
            "shares": PARTNER_SHARES if share.get("enabled") else []}


def partner_create(db: Any, uid: str) -> dict:
    settings = _settings(db, uid)
    if settings["privacy"].get("local_only"):
        raise _bad("Turn off local-only mode before sharing with a partner")
    old = doc_store.get(db, uid, PARTNER_OWNER_KIND, "main")
    if old and old.get("key"):
        doc_store.delete(db, uid, PARTNER_KIND, old["key"])
    token = secrets.token_urlsafe(24)
    key = _partner_key(token)
    now = datetime.now(timezone.utc).isoformat()
    doc_store.put(db, uid, PARTNER_KIND, key, {"uid": uid, "enabled": True, "created_at": now})
    doc_store.put(db, uid, PARTNER_OWNER_KIND, "main", {"key": key, "created_at": now})
    settings["partner_share"] = {"enabled": True, "created_at": now}
    doc_store.put(db, uid, SETTINGS_KIND, "main", settings)
    return {**_partner_status(settings), "token": token, "share_path": f"/cycle/partner/{token}"}


def partner_revoke(db: Any, uid: str) -> dict:
    settings = _settings(db, uid)
    old = doc_store.get(db, uid, PARTNER_OWNER_KIND, "main")
    if old and old.get("key"):
        doc_store.delete(db, uid, PARTNER_KIND, old["key"])
    doc_store.delete(db, uid, PARTNER_OWNER_KIND, "main")
    settings["partner_share"] = {"enabled": False, "created_at": None}
    doc_store.put(db, uid, SETTINGS_KIND, "main", settings)
    return _partner_status(settings)


def partner_public(db: Any, token: str) -> dict:
    gone = HTTPException(status_code=404, detail="This link is no longer active.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token or ""):
        raise gone
    rows = (db.table(doc_store.TABLE).select("*").eq("event_type", doc_store.EVENT_TYPE).eq("title", f"{PARTNER_KIND}:{_partner_key(token)}")
            .limit(1).execute().data or [])
    row = rows[0] if rows else None
    payload = ((row.get("data") or {}).get("payload") or {}) if row else {}
    uid = payload.get("uid")
    # only a link this server signed for its owner counts: a row a browser wrote straight to the database is never trusted
    if not row or not doc_store.row_is_valid(row) or not uid or str(row.get("user_id")) != str(uid) or not payload.get("enabled"):
        raise gone
    owner = doc_store.get(db, str(uid), PARTNER_OWNER_KIND, "main")
    if not owner or owner.get("key") != _partner_key(token):
        raise gone
    ctx = _context(db, str(uid), _utc_today())
    if not ctx["settings"]["partner_share"].get("enabled") or ctx["settings"]["privacy"].get("local_only"):
        raise gone
    state = ctx["state"]
    show = state["mode"] in ("track", "conceive", "birth_control", "perimenopause") and state["next_period"]
    nxt = state["next_period"]
    return _jsonable({
        "status": "success", "label": "Shared with you",
        "next_period": {"earliest": nxt["earliest"], "latest": nxt["latest"]} if show else None,
        "phase_hint": f"Bubbles estimates they may be in their {state['phase']} phase." if show and state["phase"] else None,
        "notice": "Shared by someone who chose to share their estimates. These are predictions, not facts, and are not a way to plan around pregnancy."})


# --------------------------------------------------------------------------------------------------
# delete everything
# --------------------------------------------------------------------------------------------------

def delete_all(db: Any, uid: str) -> dict:
    days = settings = partner = 0
    for kind in ALL_KINDS:
        rows = db.table(doc_store.TABLE).delete().eq("user_id", uid).eq("event_type", doc_store.EVENT_TYPE).eq("data->>kind", kind).execute().data or []
        days += len(rows) if kind == DAY_KIND else 0
        settings += len(rows) if kind == SETTINGS_KIND else 0
        partner += len(rows) if kind in (PARTNER_KIND, PARTNER_OWNER_KIND) else 0
    tracker = 0
    for table, filters in (("menstrual_cycles", {}), (ANALYTICS_TABLE, {"extracted_data->_prov->>domain": "cycle"})):
        try:
            query = db.table(table).delete().eq("user_id", uid)
            for key, value in filters.items():
                query = query.eq(key, value)
            tracker += len(query.execute().data or [])
        except Exception as exc:  # noqa: BLE001
            if not is_permission_denied(exc):
                _log("CYCLE", "delete_tracker", exc)
    return {"status": "success", "deleted": {"days": days, "settings": bool(settings), "partner": bool(partner), "tracker_entries": tracker}}


# --------------------------------------------------------------------------------------------------
# router
# --------------------------------------------------------------------------------------------------

def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def uid_of(authorization: str | None) -> str:
        return str(get_user(authorization).id)

    async def auth_async(authorization: str | None) -> str:
        return str((await run_in_threadpool(get_user, authorization)).id)

    @router.get("/cycle/overview")
    def overview(today: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        return build_overview(_context(db, uid, _today(today)))

    @router.get("/cycle/calendar")
    def calendar(month: str | None = Query(default=None), year: str | None = Query(default=None), today: str | None = Query(default=None),
                 authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        if (month is None) == (year is None):
            raise _bad("Pass either month=YYYY-MM or year=YYYY")
        if month is not None:
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
                raise _bad("month must look like 2026-10")
            first = date(int(month[:4]), int(month[5:]), 1)
            last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        else:
            if not re.fullmatch(r"\d{4}", year):
                raise _bad("year must look like 2026")
            first, last = date(int(year), 1, 1), date(int(year), 12, 31)
        if not MIN_YEAR <= first.year <= 2100:
            raise _bad("That year is out of range")
        ctx = _context(db, uid, _today(today))
        state = ctx["state"]
        return _jsonable({"status": "success", "month": month, "year": int(year) if year else None, "mode": state["mode"],
                          "confidence": state["confidence"], "days": engine.calendar_days(state, ctx["logs"], first, last)})

    @router.get("/cycle/day/{day}")
    def get_day(day: str, today: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        return _day_response(_context(db, uid, _today(today)), parse_day(day))

    @router.put("/cycle/day/{day}")
    async def put_day(day: str, request: Request, today: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid = await auth_async(authorization)
        parsed = parse_day(day)
        _check_log_date(parsed)
        log = normalize_day_log(await _json_body(request))
        safety = assess_notes(log["notes"], *log["custom_factors"], *log["medications"])
        return await run_in_threadpool(save_day, db, uid, parsed, log, _today(today), safety=safety)

    async def period(request: Request, authorization: str | None, start: bool):
        uid = await auth_async(authorization)
        body = await _json_body(request, required=False)
        if set(body) - {"date", "today"}:
            raise _bad("Only date is accepted")
        day = parse_day(body["date"]) if body.get("date") else _today(body.get("today"))
        _check_log_date(day)
        return await run_in_threadpool(mark_period, db, uid, day, _today(body.get("today")), start=start)

    @router.post("/cycle/period/start")
    async def period_start(request: Request, authorization: str | None = Header(default=None)):
        return await period(request, authorization, True)

    @router.post("/cycle/period/end")
    async def period_end(request: Request, authorization: str | None = Header(default=None)):
        return await period(request, authorization, False)

    @router.get("/cycle/settings")
    def get_settings(authorization: str | None = Header(default=None)):
        return {"status": "success", "settings": _settings(db, uid_of(authorization))}

    @router.put("/cycle/settings")
    async def put_settings(request: Request, today: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid = await auth_async(authorization)
        patch = await _json_body(request)

        def work() -> dict:
            now = _today(today)
            current = _settings(db, uid)
            new = _merge_settings(current, patch, now)
            doc_store.put(db, uid, SETTINGS_KIND, "main", new)
            if new["privacy"]["local_only"] and not current["privacy"]["local_only"]:
                _purge_mirrors(db, uid)
                if new["partner_share"]["enabled"]:
                    partner_revoke(db, uid)
                    new["partner_share"] = {"enabled": False, "created_at": None}
            return {"status": "success", "settings": _settings(db, uid), "overview": build_overview(_context(db, uid, now))}

        return await run_in_threadpool(work)

    @router.get("/cycle/insights")
    def insights(today: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        return build_insights(db, uid_of(authorization), _today(today))

    @router.get("/cycle/report")
    def report(months: str = Query(default="6"), include_notes: str = Query(default="false"), today: str | None = Query(default=None),
               authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        if not re.fullmatch(r"\d{1,2}", months) or not 1 <= int(months) <= 24:
            raise _bad("months must be a number from 1 to 24")
        if include_notes.lower() not in ("true", "false"):
            raise _bad("include_notes must be true or false")
        return build_report(db, uid, _today(today), int(months), include_notes.lower() == "true")

    @router.get("/cycle/factors")
    def factors(q: str | None = Query(default=None), group: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid_of(authorization)
        if q is not None and len(q) > 60:
            raise _bad("q is too long")
        if group is not None and group not in dict(content.CHIP_GROUPS):
            raise _bad("Unknown group")
        groups = content.chips_by_group(q, group)
        return {"status": "success", "total": sum(len(g["chips"]) for g in groups), "groups": groups, "query": q}

    @router.get("/cycle/education")
    def education(mode: str | None = Query(default=None), topic: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid_of(authorization)
        if mode is not None and mode not in engine.MODES:
            raise _bad("Unknown mode")
        if topic is not None and len(topic) > 60:
            raise _bad("topic is too long")
        return {"status": "success", "label": content.GENERAL_KNOWLEDGE_LABEL, "articles": content.articles(mode, topic)}

    @router.get("/cycle/partner-view")
    def partner_status(authorization: str | None = Header(default=None)):
        return _partner_status(_settings(db, uid_of(authorization)))

    @router.post("/cycle/partner-view")
    async def partner_action(request: Request, authorization: str | None = Header(default=None)):
        uid = await auth_async(authorization)
        body = await _json_body(request)
        action = body.get("action")
        if set(body) - {"action"} or action not in ("create", "revoke"):
            raise _bad("action must be create or revoke")
        return await run_in_threadpool(partner_create if action == "create" else partner_revoke, db, uid)

    @router.get("/cycle/partner/{token}")
    def partner_view(token: str):
        return JSONResponse(partner_public(db, token), headers={"Cache-Control": "no-store"})

    @router.delete("/cycle/data")
    def delete_data(confirm: str | None = Query(default=None), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        if confirm != "yes":
            raise _bad("Add confirm=yes to delete all cycle data")
        return delete_all(db, uid)

    return router
