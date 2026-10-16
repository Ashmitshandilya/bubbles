"""User-entered tracker endpoints: GET/POST /health/{domain}.

The frontend tracker pages (sleep, symptoms, activity, cycle and the generic
trackers) speak a small form-shaped contract:
    GET  /health/<domain>?days=N  -> {"status": "success", "entries": [{id, date, ...}]}
    POST /health/<domain>         -> form fields + "date"
Each domain below maps that contract onto the live canonical tables. All reads
and writes are scoped to the authenticated user and go through the trusted
backend (browsers never write health tables directly). Nutrition has no
canonical table in the 20-table baseline, so it is stored in the health_events
ledger.

Compatibility store: until supabase/migrations/20261006_coco_service_role_grants.sql
is applied, the live database denies the backend on most domain tables (Postgres
42501). Only that error triggers a fallback to extracted_health_events: the entry
is saved there as a confirmed event whose ``_row`` is the domain row, tagged
``_prov = {source: tracker, domain, store: compat}``. Reads always merge both
stores, so entries saved in compat mode stay visible after the grants arrive.
Every other database error surfaces normally.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from concurrent.futures import ThreadPoolExecutor

from db_access import is_permission_denied
from event_filters import DEAD_STATUSES, parse_moment, provenance
from ttl_cache import TTLCache

LBS_PER_KG = 2.2046226218
MAX_TEXT = 2000
ROW_LIMIT = 200
MAX_LAB_VALUE = 1e9
SOURCE = "user_logged"
COMPAT_TABLE = "extracted_health_events"
COMPAT_SCAN_LIMIT = 1000  # rows scanned when the server-side json filter is unavailable
# Whether this person has any compat-mode entry at all (a bool, keyed by user). Almost nobody does, and without this every tracker list
# read up to 1000 whole rows to find out. Cleared by _compat_insert; a miss reads as before.
_has_compat = TTLCache("tracker_has_compat", ttl_s=300, max_entries=20000)


def _text(body: dict, key: str, limit: int = MAX_TEXT) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        raise HTTPException(status_code=422, detail=f"{key} must be text")
    # NUL and lone surrogates are valid JSON but Postgres rejects them (a 500 otherwise).
    value = str(value).replace(chr(0), "").encode("utf-8", "ignore").decode("utf-8").strip()
    return value[:limit] or None


def _num(body: dict, key: str, lo: float, hi: float, label: str | None = None) -> float | None:
    value = body.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{label or key} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=422, detail=f"{label or key} must be a number")
    if not lo <= number <= hi:
        raise HTTPException(status_code=422, detail=f"{label or key} must be between {lo:g} and {hi:g}")
    return number


def _need(value: Any, label: str) -> Any:
    if value in (None, ""):
        raise HTTPException(status_code=422, detail=f"{label} is required")
    return value


def _when(body: dict, *keys: str) -> str:
    """First valid ISO date/datetime among body keys, else now (UTC)."""
    for key in keys:
        raw = body.get(key)
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{key} must be an ISO date")
        if not 1900 <= parsed.year <= 2100:
            raise HTTPException(status_code=422, detail=f"{key} is out of range")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _clean(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if v not in (None, "")}


# --- per-domain request -> row (to_row) and row -> entry (to_entry) -------------

def _sleep_row(b: dict) -> dict:
    hours = _need(_num(b, "duration", 0, 24, "duration"), "duration")
    quality = _num(b, "quality", 1, 10)
    when = _when(b, "date")
    return {"sleep_date": when[:10], "duration_minutes": round(hours * 60),
            "sleep_quality": round(quality) if quality is not None else None, "notes": _text(b, "notes")}


def _symptom_row(b: dict) -> dict:
    severity = _num(b, "severity", 1, 10)
    return {"symptom_name": _need(_text(b, "symptom", 200), "symptom"),
            "severity": round(severity) if severity is not None else None,
            "started_at": _when(b, "date"), "notes": _text(b, "notes")}


def _activity_row(b: dict) -> dict:
    return {"activity_type": _need(_text(b, "type", 100), "type"),
            "duration_minutes": round(_need(_num(b, "duration", 0, 1440, "duration"), "duration")),
            "intensity": _text(b, "intensity", 50), "notes": _text(b, "notes"),
            "activity_date": _when(b, "date")}


PHASES = {"period", "follicular", "ovulation", "luteal"}


def _cycle_row(b: dict) -> dict:
    phase = _text(b, "phase", 20) or "period"
    if phase not in PHASES:
        raise HTTPException(status_code=422, detail="phase must be one of " + ", ".join(sorted(PHASES)))
    # menstrual_cycles has no phase column; the logged phase rides in the symptoms jsonb.
    return {"start_date": _when(b, "date")[:10], "symptoms": {"phase": phase}, "flow_notes": _text(b, "notes")}


def _hydration_row(b: dict) -> dict:
    return {"amount_ml": round(_need(_num(b, "volume", 1, 10000, "volume"), "volume")),
            "drink_type": _text(b, "type", 50), "notes": _text(b, "notes"), "logged_at": _when(b, "date")}


def _mood_row(b: dict) -> dict:
    mood = _need(_num(b, "mood", 1, 10, "mood"), "mood")
    stress, anxiety = _num(b, "stress", 0, 10), _num(b, "anxiety", 0, 10)
    # ponytail: mood_logs has no stress/anxiety columns; they are folded into notes.
    extra = "; ".join(f"{k} {v:g}/10" for k, v in (("Stress", stress), ("Anxiety", anxiety)) if v is not None)
    notes = " | ".join(p for p in (_text(b, "notes"), extra) if p) or None
    return {"mood": f"{mood:g}/10", "intensity": round(mood), "notes": notes, "logged_at": _when(b, "date")}


def _nutrition_row(b: dict) -> dict:
    description = _need(_text(b, "description", 500), "description")
    calories = _num(b, "calories", 0, 10000)
    return {"event_type": "nutrition", "event_date": _when(b, "date"), "title": description[:120],
            "description": _text(b, "notes"),
            "data": _clean({"meal_type": _text(b, "meal_type", 30), "description": description, "calories": calories})}


EYE_SYMPTOMS = ("dry", "itchy", "red", "strained", "blurry", "watery", "headache")


def _eye_symptoms(raw: Any) -> list[str]:
    """Symptom chips from a list or a comma-separated string. Only the fixed vocabulary is accepted, each at most once."""
    if raw in (None, ""):
        return []
    parts = raw if isinstance(raw, list) else str(raw).split(",")
    chosen: list[str] = []
    for part in parts:
        word = str(part).strip().lower()
        if not word:
            continue
        if word not in EYE_SYMPTOMS:
            raise HTTPException(status_code=422, detail=f"eye symptom must be one of {', '.join(EYE_SYMPTOMS)}")
        if word not in chosen:
            chosen.append(word)
    return chosen


def _yes_no(b: dict, key: str) -> str | None:
    value = b.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    word = str(value).strip().lower()
    if word not in {"yes", "no"}:
        raise HTTPException(status_code=422, detail=f"{key} must be yes or no")
    return word


def _eyes_row(b: dict) -> dict:
    """One eye check: screen time, comfort, symptoms, glasses, 20-20-20 breaks and (optionally) the date of the last eye exam.
    Nothing is scored or interpreted here; it is the person's own record."""
    screen = _num(b, "screen_hours", 0, 18, "screen hours")
    comfort = _num(b, "comfort", 1, 5)
    breaks = _num(b, "breaks", 0, 48)
    symptoms = _eye_symptoms(b.get("symptoms"))
    glasses = _yes_no(b, "glasses")
    exam = None
    if b.get("last_exam") not in (None, ""):
        exam = _when(b, "last_exam")[:10]
        if exam > datetime.now(timezone.utc).date().isoformat():
            raise HTTPException(status_code=422, detail="last eye exam cannot be in the future")
    notes = _text(b, "notes")
    if screen is None and comfort is None and not symptoms and exam is None and breaks is None and glasses is None:
        raise HTTPException(status_code=422, detail="Add at least one detail about your eyes")
    data = _clean({"screen_hours": screen, "comfort": round(comfort) if comfort is not None else None,
                   "symptoms": ", ".join(symptoms) or None, "glasses": glasses,
                   "breaks": round(breaks) if breaks is not None else None, "last_exam": exam})
    return {"event_type": "eye_check", "event_date": _when(b, "date"), "title": "Eye check", "description": notes, "data": data}


def _weight_row(b: dict) -> dict:
    lbs = _need(_num(b, "weight", 50, 700, "weight"), "weight")
    notes = " | ".join(p for p in (_text(b, "notes"), _text(b, "time_of_day", 20)) if p) or None
    return {"weight_kg": round(lbs / LBS_PER_KG, 2), "notes": notes, "logged_at": _when(b, "date")}


def _vitals_row(b: dict) -> dict:
    row: dict[str, Any] = {"measured_at": _when(b, "date"), "notes": _text(b, "notes")}
    hr = _num(b, "heart_rate", 20, 300, "heart rate")
    if hr is not None:
        row["heart_rate_bpm"] = round(hr)
    temp_f = _num(b, "temperature", 80, 115, "temperature")
    if temp_f is not None:
        row["temperature_c"] = round((temp_f - 32) * 5 / 9, 1)
    bp = _text(b, "blood_pressure", 20)
    if bp:
        match = re.fullmatch(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", bp)
        if not match:
            raise HTTPException(status_code=422, detail="blood pressure must look like 120/80")
        row["systolic_bp"], row["diastolic_bp"] = int(match[1]), int(match[2])
    if not any(k in row for k in ("heart_rate_bpm", "temperature_c", "systolic_bp")):
        raise HTTPException(status_code=422, detail="Enter at least one vital sign")
    return row


def _medication_row(b: dict) -> dict:
    return {"medication_name": _need(_text(b, "name", 200), "name"), "dosage": _text(b, "dosage", 100),
            "reason": _text(b, "reason", 300), "notes": _text(b, "notes")}


def _condition_row(b: dict) -> dict:
    return {"condition_name": _need(_text(b, "condition_name", 200), "condition_name"),
            "status": _text(b, "status", 50), "diagnosed_date": _when(b, "diagnosed_date")[:10] if b.get("diagnosed_date") else None,
            "notes": _text(b, "notes")}


def _allergy_row(b: dict) -> dict:
    return {"allergen": _need(_text(b, "allergen", 200), "allergen"), "reaction": _text(b, "reaction_type", 100),
            "severity": _text(b, "severity", 30), "notes": _text(b, "notes")}


def _lab_row(b: dict) -> dict:
    row: dict[str, Any] = {"test_name": _need(_text(b, "test_name", 200), "test_name"), "unit": _text(b, "unit", 50),
                           "tested_at": _when(b, "test_date", "date"), "notes": _text(b, "notes")}
    raw_value = _text(b, "value", 50)
    if raw_value:
        try:
            number = float(raw_value)
        except ValueError:
            number = math.nan
        if math.isfinite(number) and abs(number) > MAX_LAB_VALUE:
            raise HTTPException(status_code=422, detail=f"value must be between -{MAX_LAB_VALUE:g} and {MAX_LAB_VALUE:g}")
        if math.isfinite(number):
            row["value"] = number
        else:  # non-numeric result (e.g. "positive", "nan") is kept, not dropped
            row["notes"] = " | ".join(p for p in (row["notes"], f"Result: {raw_value}") if p)
    rng = _text(b, "reference_range", 50)
    if rng:
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)\s*", rng)
        if match and all(abs(float(g)) <= MAX_LAB_VALUE for g in (match[1], match[2])):
            row["reference_min"], row["reference_max"] = float(match[1]), float(match[2])
        else:
            row["notes"] = " | ".join(p for p in (row["notes"], f"Reference: {rng}") if p)
    return row


def _report_row(b: dict) -> dict:
    return {"report_name": _need(_text(b, "title", 200), "title"), "report_type": _text(b, "report_type", 50),
            "report_date": _when(b, "report_date")[:10] if b.get("report_date") else None,
            "extracted_data": _clean({"findings": _text(b, "findings"), "notes": _text(b, "notes")}),
            "processing_status": "manual"}


def _visit_row(b: dict) -> dict:
    nxt = _text(b, "next_visit", 40)
    return {"visit_date": _when(b, "visit_date", "date"), "doctor_name": _text(b, "doctor_name", 200),
            "specialty": _text(b, "specialty", 100), "reason": _text(b, "reason", 500), "notes": _text(b, "notes"),
            "recommendations": f"Next visit: {nxt}" if nxt else None}


def _hours(minutes: Any) -> float | None:
    return round(minutes / 60, 2) if minutes is not None else None


DOMAINS: dict[str, dict[str, Any]] = {
    "sleep": dict(table="sleep_logs", date="sleep_date", windowed=True, to_row=_sleep_row,
                  to_entry=lambda r: {"duration": _hours(r.get("duration_minutes")), "quality": r.get("sleep_quality"), "notes": r.get("notes")}),
    "symptoms": dict(table="symptoms", date="started_at", windowed=True, to_row=_symptom_row,
                     to_entry=lambda r: {"symptom": r.get("symptom_name"), "severity": r.get("severity"), "notes": r.get("notes")}),
    "activity": dict(table="activity_logs", date="activity_date", windowed=True, to_row=_activity_row,
                     to_entry=lambda r: {"type": r.get("activity_type"), "duration": r.get("duration_minutes"), "intensity": r.get("intensity"), "notes": r.get("notes")}),
    "cycle": dict(table="menstrual_cycles", date="start_date", windowed=True, to_row=_cycle_row,
                  # symptoms defaults to a JSON array in the live table; only our own dict rows carry a phase.
                  to_entry=lambda r: {"phase": r["symptoms"].get("phase", "period") if isinstance(r.get("symptoms"), dict) else "period", "notes": r.get("flow_notes")}),
    "hydration": dict(table="hydration_logs", date="logged_at", windowed=True, to_row=_hydration_row,
                      to_entry=lambda r: {"volume": r.get("amount_ml"), "type": r.get("drink_type"), "notes": r.get("notes")}),
    "mood": dict(table="mood_logs", date="logged_at", windowed=True, to_row=_mood_row,
                 to_entry=lambda r: {"mood": r.get("intensity"), "notes": r.get("notes")}),
    "nutrition": dict(table="health_events", date="event_date", windowed=True, to_row=_nutrition_row, filters={"event_type": "nutrition"},
                      to_entry=lambda r: _clean({**(r.get("data") or {}), "notes": r.get("description")})),
    "eyes": dict(table="health_events", date="event_date", windowed=True, to_row=_eyes_row, filters={"event_type": "eye_check"},
                 to_entry=lambda r: _clean({**(r.get("data") or {}), "notes": r.get("description")})),
    "weight": dict(table="weight_logs", date="logged_at", windowed=True, to_row=_weight_row,
                   to_entry=lambda r: {"weight": round(r["weight_kg"] * LBS_PER_KG, 1) if r.get("weight_kg") is not None else None, "notes": r.get("notes")}),
    "vitals": dict(table="vital_signs", date="measured_at", windowed=True, to_row=_vitals_row,
                   to_entry=lambda r: {"heart_rate": r.get("heart_rate_bpm"),
                                       "blood_pressure": f"{r['systolic_bp']}/{r['diastolic_bp']}" if r.get("systolic_bp") and r.get("diastolic_bp") else None,
                                       "temperature": round(r["temperature_c"] * 9 / 5 + 32, 1) if r.get("temperature_c") is not None else None,
                                       "notes": r.get("notes")}),
    "medications": dict(table="medications", date="created_at", windowed=False, to_row=_medication_row,
                        to_entry=lambda r: {"name": r.get("medication_name"), "dosage": r.get("dosage"), "reason": r.get("reason"), "notes": r.get("notes")}),
    "conditions": dict(table="medical_conditions", date="created_at", windowed=False, to_row=_condition_row,
                       to_entry=lambda r: {"condition_name": r.get("condition_name"), "status": r.get("status"), "diagnosed_date": r.get("diagnosed_date"), "notes": r.get("notes")}),
    "allergies": dict(table="allergies", date="created_at", windowed=False, to_row=_allergy_row,
                      to_entry=lambda r: {"allergen": r.get("allergen"), "reaction_type": r.get("reaction"), "severity": r.get("severity"), "notes": r.get("notes")}),
    "labs": dict(table="lab_results", date="tested_at", windowed=False, to_row=_lab_row,
                 to_entry=lambda r: {"test_name": r.get("test_name"), "value": r.get("value"), "unit": r.get("unit"),
                                     "reference_range": f"{r['reference_min']:g}-{r['reference_max']:g}" if r.get("reference_min") is not None and r.get("reference_max") is not None else None,
                                     "notes": r.get("notes")}),
    "reports": dict(table="medical_reports", date="report_date", windowed=False, to_row=_report_row,
                    to_entry=lambda r: {"title": r.get("report_name"), "report_type": r.get("report_type"),
                                        "findings": (r.get("extracted_data") or {}).get("findings"), "notes": (r.get("extracted_data") or {}).get("notes")}),
    "visits": dict(table="doctor_visits", date="visit_date", windowed=False, to_row=_visit_row,
                   to_entry=lambda r: {"doctor_name": r.get("doctor_name"), "specialty": r.get("specialty"), "reason": r.get("reason"),
                                       "notes": r.get("notes"), "recommendations": r.get("recommendations")}),
}


def _to_entry(domain: dict, row: dict) -> dict:
    when = row.get(domain["date"]) or row.get("created_at")
    return _clean({"id": str(row["id"]), "date": when, **domain["to_entry"](row)})


# --- compatibility store: domain row -> analytics-friendly extracted_health_events ----
# extracted_data carries the superset keys the analytics/projection modules read (see
# .omc/plans/health-intel/audit-event-shapes.md), the domain row under "_row" (so the
# tracker can rebuild its entry) and "_prov" (so every reader can tell where it came from).
# Keys starting with an underscore are metadata: event_filters.clean_data() strips them.

def _day(value: Any) -> str:
    return str(value)[:10] if value else __import__("calc_core").local_today().isoformat()


def _ev_sleep(r: dict) -> dict:
    hours = _hours(r["duration_minutes"])
    return _clean({"name": "sleep", "duration_minutes": r["duration_minutes"], "hours": hours, "duration_hours": hours,
                   "value": hours, "amount": hours, "unit": "hours", "severity": r.get("sleep_quality"),
                   "date": _day(r["sleep_date"]), "notes": r.get("notes")})


def _ev_symptom(r: dict) -> dict:
    return _clean({"symptom": r["symptom_name"], "name": r["symptom_name"], "severity": r.get("severity"),
                   "date": _day(r["started_at"]), "notes": r.get("notes")})


def _ev_activity(r: dict) -> dict:
    return _clean({"name": r["activity_type"], "activity": r["activity_type"], "duration_minutes": r["duration_minutes"],
                   "minutes": r["duration_minutes"], "unit": "min", "intensity_label": r.get("intensity"),  # text, not the numeric `intensity` readers expect
                   "date": _day(r["activity_date"]), "notes": r.get("notes")})


def _ev_cycle(r: dict) -> dict:
    symptoms = r.get("symptoms")
    phase = symptoms.get("phase", "period") if isinstance(symptoms, dict) else "period"
    period = phase == "period"
    return _clean({"name": "period" if period else "cycle phase", "symptom": "menstrual flow" if period else None,
                   "is_start": period, "start_date": r["start_date"], "date": r["start_date"], "phase": phase,
                   "notes": r.get("flow_notes")})


def _ev_hydration(r: dict) -> dict:
    ml = r["amount_ml"]
    return _clean({"name": "water", "amount_ml": ml, "water_ml": ml, "amount": ml, "value": ml, "unit": "ml",
                   "drink_type": r.get("drink_type"), "date": _day(r["logged_at"]), "notes": r.get("notes")})


def _ev_mood(r: dict) -> dict:
    score = r["intensity"]
    return _clean({"name": "mood", "score": score, "mood_score": score, "severity": score,
                   "date": _day(r["logged_at"]), "notes": r.get("notes")})


def _ev_nutrition(r: dict) -> dict:
    data = r.get("data") or {}
    meal = data.get("description") or r.get("title")
    return _clean({"name": meal, "category": data.get("meal_type") or "meal", "meal_type": data.get("meal_type"),
                   "description": meal, "calories": data.get("calories"), "date": _day(r["event_date"]), "notes": r.get("description")})


def _ev_eyes(r: dict) -> dict:
    data = r.get("data") or {}
    return _clean({"name": "eye check", "category": "eyes", "screen_hours": data.get("screen_hours"), "eye_comfort": data.get("comfort"),
                   "eye_symptoms": data.get("symptoms"), "glasses": data.get("glasses"), "breaks": data.get("breaks"),
                   "last_exam": data.get("last_exam"), "date": _day(r["event_date"]), "notes": r.get("description")})


def _ev_weight(r: dict) -> dict:
    kg = r["weight_kg"]
    return _clean({"name": "weight", "weight_kg": kg, "value": kg, "amount": kg, "unit": "kg",
                   "date": _day(r["logged_at"]), "notes": r.get("notes")})


def _ev_vitals(r: dict) -> dict:
    hr, sys_bp, dia_bp, temp = r.get("heart_rate_bpm"), r.get("systolic_bp"), r.get("diastolic_bp"), r.get("temperature_c")
    one: dict[str, Any] = {"name": "vitals"}  # a single reading also gets the scalar value/unit readers expect
    if sum(x is not None for x in (hr, sys_bp, temp)) == 1:
        one = ({"name": "heart rate", "value": hr, "unit": "bpm"} if hr is not None
               else {"name": "blood pressure"} if sys_bp is not None
               else {"name": "temperature", "value": temp, "unit": "C"})
    return _clean({**one, "heart_rate_bpm": hr, "heart_rate": hr, "systolic_bp": sys_bp, "diastolic_bp": dia_bp,
                   "systolic": sys_bp, "diastolic": dia_bp, "temperature_c": temp, "temperature": temp,
                   "date": _day(r["measured_at"]), "notes": r.get("notes")})


def _ev_medication(r: dict) -> dict:
    return _clean({"name": r["medication_name"], "medication": r["medication_name"], "category": "medication",
                   "dosage": r.get("dosage"), "dose": r.get("dosage"), "reason": r.get("reason"),
                   "date": _day(None), "notes": r.get("notes")})


def _ev_condition(r: dict) -> dict:
    return _clean({"name": r["condition_name"], "condition_name": r["condition_name"], "category": "condition",
                   "status": r.get("status"), "diagnosed_date": r.get("diagnosed_date"), "date": _day(None), "notes": r.get("notes")})


def _ev_allergy(r: dict) -> dict:
    return _clean({"name": r["allergen"], "allergen": r["allergen"], "category": "allergy", "reaction": r.get("reaction"),
                   "severity_label": r.get("severity"), "date": _day(None), "notes": r.get("notes")})


def _ev_lab(r: dict) -> dict:
    return _clean({"name": r["test_name"], "test_name": r["test_name"], "value": r.get("value"), "unit": r.get("unit"),
                   "reference_min": r.get("reference_min"), "reference_max": r.get("reference_max"),
                   "date": _day(r["tested_at"]), "notes": r.get("notes")})


def _ev_visit(r: dict) -> dict:
    return _clean({"name": r.get("doctor_name") or r.get("specialty") or "doctor visit", "doctor_name": r.get("doctor_name"),
                   "specialty": r.get("specialty"), "reason": r.get("reason"), "recommendations": r.get("recommendations"),
                   "date": _day(r["visit_date"]), "notes": r.get("notes")})


def _ev_report(r: dict) -> dict:
    found = r.get("extracted_data") or {}
    return _clean({"name": r["report_name"], "title": r["report_name"], "report_type": r.get("report_type"),
                   "findings": found.get("findings"), "date": _day(r.get("report_date")), "notes": found.get("notes")})


COMPAT_EVENTS: dict[str, tuple[str, Callable[[dict], dict]]] = {
    "sleep": ("sleep", _ev_sleep), "symptoms": ("symptom", _ev_symptom), "activity": ("activity", _ev_activity),
    "cycle": ("menstrual_symptom", _ev_cycle), "hydration": ("hydration", _ev_hydration), "mood": ("mood", _ev_mood),
    "nutrition": ("food", _ev_nutrition), "eyes": ("eye_check", _ev_eyes), "weight": ("weight", _ev_weight), "vitals": ("vital_sign", _ev_vitals),
    "medications": ("medication", _ev_medication), "conditions": ("medical_condition", _ev_condition),
    "allergies": ("allergy", _ev_allergy), "labs": ("lab_result", _ev_lab), "visits": ("doctor_visit", _ev_visit),
    "reports": ("lab_result", _ev_report),
}
assert set(COMPAT_EVENTS) == set(DOMAINS)


def _compat_insert(db: Any, uid: str, slug: str, row: dict) -> dict:
    """Save a tracker entry as a confirmed extracted_health_events row; returns the saved event."""
    event_type, to_event = COMPAT_EVENTS[slug]
    payload = {"user_id": uid, "event_type": event_type, "confidence": 1.0, "extraction_status": "confirmed",
               "user_confirmed": True, "message_id": None,
               "extracted_data": {**to_event(row), "_prov": {"source": "tracker", "domain": slug, "store": "compat"}, "_row": row}}
    saved = db.table(COMPAT_TABLE).insert(payload).select("*").execute()
    _has_compat.invalidate(uid)
    if not saved.data:
        raise HTTPException(status_code=500, detail="Unable to save entry")
    return saved.data[0]


def _mirror_to_analytics(db: Any, uid: str, slug: str, row: dict, saved_row: dict) -> None:
    """Make a primary-store save visible to the intelligence endpoints.

    Insights, patterns, the daily brief, the living map, body systems and the doctor timeline all read
    extracted_health_events, not the tracker tables. Without this a tracker entry saved normally would never
    influence them (only compat-mode saves did). One confirmed event per save, tagged ``store: "mirror"`` so the
    tracker's own reads (which merge only ``store: "compat"``) never list the entry twice. Best effort: a failure
    here must never fail the user's save.
    """
    try:
        event_type, to_event = COMPAT_EVENTS[slug]
        db.table(COMPAT_TABLE).insert({
            "user_id": uid, "event_type": event_type, "confidence": 1.0, "extraction_status": "confirmed",
            "user_confirmed": True, "message_id": None,
            "extracted_data": {**to_event(row), "_prov": {"source": "tracker", "domain": slug, "store": "mirror",
                                                         "entry_id": str(saved_row.get("id"))}},
        }).execute()
    except Exception as exc:  # noqa: BLE001
        try:
            from logging_util import logger
            logger.warning(component="HEALTH_LOGS", operation="mirror_to_analytics", error=exc, fallback_action="entry_saved_without_analytics_mirror")
        except Exception:  # noqa: BLE001
            pass


def _compat_events(db: Any, uid: str, slug: str | None, *, primary_ok: bool = False) -> list[dict]:
    """Compat-store events for the user (one domain, or all), newest first. Raises on database errors.
    ``primary_ok``: the normal tracker table was readable, so a remembered "this person has no compat entries" can be trusted."""
    if primary_ok and _has_compat.peek(uid) is False:
        return []
    def fetch(filters: dict[str, str], limit: int) -> list[dict]:
        query = db.table(COMPAT_TABLE).select("*").eq("user_id", uid)
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.order("created_at", desc=True).limit(limit).execute().data or []

    server_side = {"extracted_data->_prov->>store": "compat"}
    if slug:
        server_side["extracted_data->_prov->>domain"] = slug
    try:
        rows = fetch(server_side, ROW_LIMIT if slug else COMPAT_SCAN_LIMIT)
    except Exception as exc:
        if is_permission_denied(exc):
            raise
        rows = fetch({}, COMPAT_SCAN_LIMIT)  # json filter unsupported: scan and filter below
    # the server-side filter is an optimisation; this is the authoritative check
    found = [r for r in rows if isinstance(r, dict) and (r.get("extraction_status") or "pending") not in DEAD_STATUSES
             and provenance(r).get("store") == "compat" and (slug is None or provenance(r).get("domain") == slug)]
    if found or slug is None:   # a one-domain read that finds nothing says nothing about the other domains
        _has_compat.put(uid, bool(found))
    return found


def _compat_entry(domain: dict, event: dict, stored: Any = None) -> dict | None:
    """Rebuild the tracker entry for a compat event (None if the stored row is unusable)."""
    data = event.get("extracted_data")
    stored = stored if stored is not None else data.get("_row") if isinstance(data, dict) else None
    if not isinstance(stored, dict) or event.get("id") is None:
        return None
    try:
        return _to_entry(domain, {**stored, "id": event["id"], "created_at": event.get("created_at")})
    except Exception:  # a hand-edited or legacy row must not break the whole listing
        return None


def _in_window(domain: dict, entry: dict, since: datetime) -> bool:
    raw = entry.get("date")
    if not raw:
        return True
    if domain["date"].endswith("_date"):
        return str(raw)[:10] >= since.date().isoformat()
    moment = parse_moment(raw)
    try:
        return moment is None or moment >= since
    except (OverflowError, ValueError):
        return True


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _sort_key(entry: dict) -> datetime:
    try:
        return (parse_moment(entry.get("date")) or _EPOCH).astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return _EPOCH


def _merge(entries: list[dict]) -> list[dict]:
    """Newest first, de-duplicated by id, capped at ROW_LIMIT."""
    seen: set[str] = set()
    merged = []
    for entry in sorted(entries, key=_sort_key, reverse=True):
        if entry["id"] not in seen:
            seen.add(entry["id"])
            merged.append(entry)
    return merged[:ROW_LIMIT]


def _cycle_summary(entries: list[dict]) -> dict:
    starts = sorted({e["date"][:10] for e in entries if e.get("phase") == "period" and e.get("date")})
    parsed = [datetime.fromisoformat(s) for s in starts]
    gaps = [(b - a).days for a, b in zip(parsed, parsed[1:]) if 15 <= (b - a).days <= 90]
    summary: dict[str, Any] = {"period_start_count": len(starts)}
    if starts:
        summary["last_period"] = starts[-1]
    if gaps:
        average = round(sum(gaps) / len(gaps), 1)
        summary["average_cycle_length"] = average
        summary["next_predicted"] = (parsed[-1] + timedelta(days=round(average))).date().isoformat()
    return summary


def list_domain(db: Any, slug: str, domain: dict, uid: str, days: int) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.table(domain["table"]).select("*").eq("user_id", uid)
    for key, value in domain.get("filters", {}).items():
        query = query.eq(key, value)
    if domain["windowed"]:
        query = query.gte(domain["date"], since.date().isoformat() if domain["date"].endswith("_date") else since.isoformat())
    entries: list[dict] = []
    refused: Exception | None = None
    try:
        rows = query.order(domain["date"], desc=True).limit(ROW_LIMIT).execute().data or []
        entries = [_to_entry(domain, r) for r in rows]
    except Exception as exc:
        if not is_permission_denied(exc):
            raise
        refused = exc
    try:
        events = _compat_events(db, uid, slug, primary_ok=refused is None)
    except Exception as exc:
        if not is_permission_denied(exc):
            raise
        if refused is not None:  # neither store is readable: report the table the user asked for
            raise refused
        events = []
    compat = [e for e in (_compat_entry(domain, ev) for ev in events) if e]
    entries = _merge(entries + [e for e in compat if not domain["windowed"] or _in_window(domain, e, since)])
    payload: dict[str, Any] = {"status": "success", "entries": entries}
    if slug == "cycle":
        payload["summary"] = _cycle_summary(entries)
    return payload

def save_domain(db: Any, slug: str, domain: dict, uid: str, body: dict) -> dict:
    row = {k: v for k, v in domain["to_row"](body).items() if v is not None}
    record = {**row, "user_id": uid, "source": SOURCE, "user_confirmed": True}
    if slug == "reports":  # medical_reports has no source column
        record.pop("source")
    try:
        saved = db.table(domain["table"]).insert(record).select("*").execute()
    except Exception as exc:
        if not is_permission_denied(exc):
            raise
        try:
            event = _compat_insert(db, uid, slug, row)
        except Exception as compat_exc:
            if is_permission_denied(compat_exc):  # neither store is writable: report the table the user asked for
                raise exc
            raise
        entry = _compat_entry(domain, event, row)
        if entry is None:
            raise HTTPException(status_code=500, detail="Unable to save entry")
        return {"status": "success", "entry": entry, "store": "compat"}
    if not saved.data:
        raise HTTPException(status_code=500, detail="Unable to save entry")
    _mirror_to_analytics(db, uid, slug, row, saved.data[0])
    return {"status": "success", "entry": _to_entry(domain, saved.data[0]), "store": "primary"}


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def _summary(uid: str) -> dict:
        refused: list[str] = []

        def stamps_of(item: tuple[str, dict]) -> tuple[str, list]:
            slug, domain = item
            query = db.table(domain["table"]).select("created_at").eq("user_id", uid)
            for key, value in domain.get("filters", {}).items():
                query = query.eq(key, value)
            try:
                rows = query.order("created_at", desc=True).limit(500).execute().data or []
            except Exception as exc:
                if not is_permission_denied(exc):
                    raise
                refused.append(slug)
                rows = []  # a refused table is not an error here: compat rows below still count
            return slug, [r.get("created_at") for r in rows]

        # The tracker tables are asked at the same time (it was seventeen round trips one after another).
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="health-summary") as pool:
            stamps: dict[str, list] = dict(pool.map(stamps_of, list(DOMAINS.items())))
        try:
            for event in _compat_events(db, uid, None, primary_ok=not refused):
                domain_slug = provenance(event).get("domain")
                if domain_slug in stamps:
                    stamps[domain_slug].append(event.get("created_at"))
        except Exception as exc:
            if not is_permission_denied(exc):
                raise
        total, with_data, days, latest = 0, 0, set(), None
        for found in stamps.values():
            if found:
                with_data += 1
                total += len(found)
                known = [s for s in found if s]
                days.update(s[:10] for s in known)
                if known:
                    latest = max(known + ([latest] if latest else []))
        return {"status": "success", "categories_with_data": with_data, "total_entries": total,
                "days_tracked": len(days), "last_update": latest}

    def _list(slug: str, domain: dict, uid: str, days: int) -> dict:
        return list_domain(db, slug, domain, uid, days)

    def _save(slug: str, domain: dict, uid: str, body: dict) -> dict:
        return save_domain(db, slug, domain, uid, body)

    @router.get("/health/summary")
    def health_summary(authorization: str | None = Header(default=None)):
        return _summary(str(get_user(authorization).id))

    @router.get("/health/{slug}")
    def list_entries(slug: str, days: int = Query(default=30, ge=1, le=730),
                     authorization: str | None = Header(default=None)):
        domain = DOMAINS.get(slug)
        if not domain:
            raise HTTPException(status_code=404, detail="Unknown tracker")
        return _list(slug, domain, str(get_user(authorization).id), days)

    @router.post("/health/{slug}", status_code=201)
    async def create_entry(slug: str, request: Request, authorization: str | None = Header(default=None)):
        # The body is parsed by hand so every malformed request is a 422 with a string detail
        # (FastAPI's own validation error carries a list the trackers cannot show).
        domain = DOMAINS.get(slug)
        if not domain:
            raise HTTPException(status_code=404, detail="Unknown tracker")
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        return await run_in_threadpool(_save, slug, domain, uid, body)

    @router.get("/intelligence/recent-queries")
    def recent_queries(limit: int = Query(default=4, ge=1, le=20), authorization: str | None = Header(default=None)):
        uid = str(get_user(authorization).id)
        rows = (db.table("chat_messages").select("content").eq("user_id", uid).eq("role", "user")
                .order("created_at", desc=True).limit(limit * 5).execute().data or [])
        seen: list[str] = []
        for row in rows:
            text = (row.get("content") or "").strip()[:140]
            if text and text not in seen:
                seen.append(text)
        return {"status": "success", "queries": seen[:limit]}

    @router.get("/intelligence/suggestions")
    def suggestions(limit: int = Query(default=6, ge=1, le=12), authorization: str | None = Header(default=None)):
        get_user(authorization)
        # ponytail: static prompts; rank by the user's data gaps once context-aware suggestions are built.
        prompts = ["How's my sleep this week?", "What's affecting my energy?", "When's my next period?",
                   "Summarize my health for my doctor", "Am I drinking enough water?", "How's my recovery trending?"]
        return {"status": "success", "suggestions": prompts[:limit]}

    return router
