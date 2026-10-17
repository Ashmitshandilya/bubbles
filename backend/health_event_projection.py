"""Project user-confirmed extracted events into Bubbles canonical health tables.

The extracted-event table is staging. A confirmed event is first written to the
canonical health_events ledger, then projected only when the payload contains
enough validated information for a matching domain table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from event_filters import clean_data, provenance


def _text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _number(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _date(data: dict[str, Any]) -> str | None:
    value = _text(data, "date")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _occurred_at(data: dict[str, Any]) -> str:
    date = _text(data, "date")
    time = _text(data, "time")
    if date:
        candidate = f"{date}T{time}" if time else f"{date}T00:00:00+00:00"
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def _vital_row(user_id: str, data: dict[str, Any], occurred: str) -> dict[str, Any] | None:
    metric = (_text(data, "name", "metric", "category", "symptom") or "").lower()
    value = _number(data, "amount", "value", "quantity")
    if value is None:
        return None
    row: dict[str, Any] = {"user_id": user_id, "measured_at": occurred, "notes": _text(data, "notes", "details"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    if "heart" in metric or "pulse" in metric:
        row["heart_rate_bpm"] = round(value)
    elif "systolic" in metric:
        row["systolic_bp"] = round(value)
    elif "diastolic" in metric:
        row["diastolic_bp"] = round(value)
    elif "temperature" in metric or metric in {"temp", "fever"}:
        row["temperature_c"] = value
    elif "spo2" in metric or "oxygen" in metric:
        row["spo2_percent"] = value
    elif "respiratory" in metric or "breathing rate" in metric:
        row["respiratory_rate"] = round(value)
    else:
        return None
    return row




# Live Supabase contract snapshot used as a defensive boundary.  These are the
# columns Bubbles is allowed to write in each canonical domain table.  Generated
# or future fields must be added deliberately rather than leaking arbitrary AI
# keys into SQL inserts.
PROJECTION_CONTRACTS: dict[str, dict[str, set[str]]] = {
    "symptoms": {"allowed": {"user_id", "symptom_name", "severity", "started_at", "ended_at", "notes", "body_location", "source", "user_confirmed"}, "required": {"user_id", "symptom_name"}},
    "hydration_logs": {"allowed": {"user_id", "logged_at", "amount_ml", "drink_type", "notes", "source", "user_confirmed"}, "required": {"user_id", "logged_at", "amount_ml"}},
    "sleep_logs": {"allowed": {"user_id", "sleep_date", "bedtime", "wake_time", "duration_minutes", "sleep_quality", "notes", "source", "user_confirmed"}, "required": {"user_id", "sleep_date"}},
    "activity_logs": {"allowed": {"user_id", "activity_date", "activity_type", "duration_minutes", "distance_km", "calories_burned", "steps", "intensity", "notes", "source", "user_confirmed"}, "required": {"user_id", "activity_date", "activity_type"}},
    "exercise_logs": {"allowed": {"user_id", "performed_at", "exercise_name", "duration_minutes", "sets", "reps", "weight_kg", "calories_burned", "intensity", "notes", "source", "user_confirmed"}, "required": {"user_id", "performed_at", "exercise_name"}},
    "weight_logs": {"allowed": {"user_id", "logged_at", "weight_kg", "body_fat_percent", "notes", "source", "user_confirmed"}, "required": {"user_id", "logged_at", "weight_kg"}},
    "vital_signs": {"allowed": {"user_id", "measured_at", "heart_rate_bpm", "systolic_bp", "diastolic_bp", "temperature_c", "spo2_percent", "respiratory_rate", "notes", "source", "user_confirmed"}, "required": {"user_id", "measured_at"}},
    "medications": {"allowed": {"user_id", "medication_name", "dosage", "frequency", "start_date", "end_date", "reason", "notes", "source", "user_confirmed"}, "required": {"user_id", "medication_name"}},
    "mood_logs": {"allowed": {"user_id", "logged_at", "mood", "intensity", "notes", "source", "user_confirmed"}, "required": {"user_id", "logged_at", "mood"}},
    "lab_results": {"allowed": {"user_id", "medical_report_id", "test_name", "value", "unit", "reference_min", "reference_max", "abnormal_flag", "tested_at", "notes", "source", "user_confirmed"}, "required": {"user_id", "test_name"}},
    "doctor_visits": {"allowed": {"user_id", "visit_date", "doctor_name", "specialty", "reason", "diagnosis", "notes", "recommendations", "medical_report_id", "source", "user_confirmed"}, "required": {"user_id", "visit_date"}},
    "medical_conditions": {"allowed": {"user_id", "condition_name", "status", "diagnosed_date", "notes", "source", "user_confirmed"}, "required": {"user_id", "condition_name"}},
    "allergies": {"allowed": {"user_id", "allergen", "reaction", "severity", "notes", "source", "user_confirmed"}, "required": {"user_id", "allergen"}},
}

_INTEGER_COLUMNS = {
    "severity", "duration_minutes", "sleep_quality", "heart_rate_bpm",
    "systolic_bp", "diastolic_bp", "respiratory_rate", "intensity",
    "amount_ml",
}

# columns in _INTEGER_COLUMNS that are TEXT in these tables (activity/exercise intensity, allergy severity)
_TEXT_COLUMNS = {
    "activity_logs": {"intensity"},
    "exercise_logs": {"intensity"},
    "allergies": {"severity"},
}

def validate_projection_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    contract = PROJECTION_CONTRACTS.get(table)
    if not contract:
        raise ValueError(f"No canonical projection contract for table {table!r}")
    unknown = set(row) - contract["allowed"]
    if unknown:
        raise ValueError(f"Projection contains unsupported columns for {table}: {sorted(unknown)}")
    missing = {key for key in contract["required"] if row.get(key) in (None, "")}
    if missing:
        raise ValueError(f"Projection missing required columns for {table}: {sorted(missing)}")
    for key in (_INTEGER_COLUMNS & row.keys()) - _TEXT_COLUMNS.get(table, set()):
        if row[key] is None:
            continue
        try:
            value = int(round(float(row[key])))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{table}.{key} must be an integer-compatible value") from exc
        row[key] = value
    if table in {"symptoms", "sleep_logs", "mood_logs"} and row.get("severity") is not None:
        if not 1 <= int(row["severity"]) <= 10:
            raise ValueError(f"{table}.severity must be between 1 and 10")
    if table == "sleep_logs" and row.get("sleep_quality") is not None:
        if not 1 <= int(row["sleep_quality"]) <= 10:
            raise ValueError("sleep_logs.sleep_quality must be between 1 and 10")
    if table == "mood_logs" and row.get("intensity") is not None:
        if not 1 <= int(row["intensity"]) <= 10:
            raise ValueError("mood_logs.intensity must be between 1 and 10")
    if table == "hydration_logs" and row.get("amount_ml") is not None and int(row["amount_ml"]) < 0:
        raise ValueError("hydration_logs.amount_ml cannot be negative")
    if table == "weight_logs" and row.get("weight_kg") is not None and float(row["weight_kg"]) <= 0:
        raise ValueError("weight_logs.weight_kg must be positive")
    return row

def _plan(*, user_id: str, event_id: str, event_type: str, extracted_data: dict[str, Any], confidence: float, message_id: str | None) -> tuple[dict[str, Any], str | None, dict[str, Any] | None, bool]:
    """What confirming one event writes: (ledger row, domain table, validated domain row, positive). Pure; raises ValueError on a bad row."""
    raw = dict(extracted_data or {})  # the ledger keeps everything, including _prov
    data = clean_data(raw)  # domain rows are built from clinical values only, never `_prov` metadata

    prov = provenance({"extracted_data": raw})
    positive = (
        raw.get("present") is not False
        and prov.get("assertion", "present") == "present"
        and prov.get("subject", "self") == "self"
    )
    occurred = _occurred_at(data)

    row: dict[str, Any] | None = None
    table: str | None = None
    if not positive:
        pass  # a denial / hedge / other-person statement is a ledger entry only, never a domain row
    elif event_type in {"symptom", "menstrual_symptom"}:
        name = _text(data, "symptom", "name", "category")
        if name:
            table = "symptoms"
            row = {"user_id": user_id, "symptom_name": name, "severity": _number(data, "severity"), "started_at": occurred, "notes": _text(data, "details", "notes"), "body_location": _text(data, "body_location", "location"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "hydration":
        amount = _number(data, "amount", "amount_ml", "quantity")
        if amount is not None:
            table = "hydration_logs"; row = {"user_id": user_id, "logged_at": occurred, "amount_ml": round(amount), "drink_type": _text(data, "category", "drink_type", "name"), "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "sleep":
        duration = _number(data, "duration_minutes")
        unit = (_text(data, "unit") or "").lower()
        if duration is None and unit.startswith("hour"):
            duration = (_number(data, "amount", "quantity") or 0) * 60
        if duration is not None:
            table = "sleep_logs"; row = {"user_id": user_id, "sleep_date": _date(data) or occurred[:10], "duration_minutes": duration, "sleep_quality": _number(data, "severity"), "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "activity":
        duration = _number(data, "duration_minutes", "duration")
        if duration is not None:
            table = "activity_logs"; row = {"user_id": user_id, "activity_date": occurred, "activity_type": _text(data, "name", "category") or "activity", "duration_minutes": duration, "intensity": _text(data, "severity", "intensity"), "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "exercise":
        duration = _number(data, "duration_minutes", "duration")
        if duration is not None:
            table = "exercise_logs"; row = {"user_id": user_id, "performed_at": occurred, "exercise_name": _text(data, "name", "category") or "exercise", "duration_minutes": duration, "intensity": _text(data, "severity", "intensity"), "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "weight":
        value = _number(data, "amount", "value", "quantity")
        if value is not None:
            table = "weight_logs"; row = {"user_id": user_id, "logged_at": occurred, "weight_kg": value, "notes": _text(data, "notes", "details"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "vital_sign":
        table = "vital_signs"; row = _vital_row(user_id, data, occurred)
    elif event_type == "medication":
        name = _text(data, "name", "category")
        if name:
            table = "medications"; row = {"user_id": user_id, "medication_name": name, "dosage": _text(data, "amount", "dose"), "frequency": _text(data, "details", "frequency"), "start_date": _date(data), "reason": _text(data, "reason"), "notes": _text(data, "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type in {"mood", "stress"}:
        table = "mood_logs"; row = {"user_id": user_id, "logged_at": occurred, "mood": _text(data, "name", "category", "symptom") or event_type, "intensity": _number(data, "severity"), "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "lab_result":
        name = _text(data, "name", "category", "symptom")
        value = _number(data, "value", "amount", "quantity")
        if name:
            table = "lab_results"; row = {"user_id": user_id, "test_name": name, "value": value, "unit": _text(data, "unit"), "abnormal_flag": _text(data, "abnormal_flag"), "tested_at": occurred, "notes": _text(data, "details", "notes"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "doctor_visit":
        table = "doctor_visits"; row = {"user_id": user_id, "visit_date": occurred, "doctor_name": _text(data, "name", "doctor_name"), "specialty": _text(data, "category", "specialty"), "reason": _text(data, "symptom", "reason", "details"), "notes": _text(data, "notes", "details"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "medical_condition":
        name = _text(data, "name", "category", "symptom")
        if name:
            table = "medical_conditions"; row = {"user_id": user_id, "condition_name": name, "status": _text(data, "status", "severity", "details"), "diagnosed_date": _date(data), "notes": _text(data, "notes", "details"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}
    elif event_type == "allergy":
        name = _text(data, "name", "category", "symptom")
        if name:
            table = "allergies"; row = {"user_id": user_id, "allergen": name, "reaction": _text(data, "reaction", "details", "notes"), "severity": _text(data, "severity"), "source": "bubbles_confirmed_extraction", "user_confirmed": True}

    if row and table:
        # validate BEFORE the ledger insert: a bad row must not leave a ledger-only half projection behind
        row = validate_projection_row(table, row)

    title = _text(data, "name", "symptom", "category") or event_type.replace("_", " ").title()
    ledger_payload = {
        "user_id": user_id,
        "event_type": event_type,
        "event_date": occurred,
        "title": title if positive or raw.get("present") is not False else f"No {title}",
        "description": _text(data, "details", "notes", "symptom"),
        "data": raw,
        "source": "bubbles_confirmed_extraction",
        "confidence": confidence,
        "user_confirmed": True,
        "source_extracted_event_id": event_id,
        "source_message_id": message_id,
    }
    return ledger_payload, table, row, positive


def project_confirmed_event(*, db: Any, user_id: str, event_id: str, event_type: str, extracted_data: dict[str, Any], confidence: float, message_id: str | None = None) -> dict[str, Any]:
    existing = db.table("health_events").select("id").eq("user_id", user_id).eq("source_extracted_event_id", event_id).limit(1).execute()
    if existing.data:
        return {"status": "already_projected", "health_event_id": existing.data[0].get("id")}
    ledger_payload, table, row, positive = _plan(user_id=user_id, event_id=event_id, event_type=event_type, extracted_data=extracted_data, confidence=confidence, message_id=message_id)
    # postgrest insert builders have no .single(); read the first returned row.
    ledger = db.table("health_events").insert(ledger_payload).select("id").execute()
    health_event_id = ledger.data[0].get("id") if ledger.data else None

    if not positive:
        return {"status": "ledger_only_non_positive", "health_event_id": health_event_id, "domain_table": None}
    if row and table:
        db.table(table).insert(row).execute()
    return {"status": "projected", "health_event_id": health_event_id, "domain_table": table if row else None}


def project_confirmed_events(*, db: Any, user_id: str, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Batch variant of project_confirmed_event for the batch confirmation route: ONE read of the ledger rows that already exist, ONE list insert
    into the ledger and one list insert per domain table, instead of about five calls per event. Returns ``{event_id: result}``; a bad event gets
    ``{"status": "error", ...}`` and never stops the others. If a list insert fails, those events are retried one by one (so one bad row cannot
    block the rest); a database permission error is raised to the caller (it means "compat mode")."""
    from db_access import is_permission_denied

    ids = [str(e["id"]) for e in events if e.get("id")]
    done = {str(r.get("source_extracted_event_id")): r.get("id") for r in
            (db.table("health_events").select("id,source_extracted_event_id").eq("user_id", user_id).in_("source_extracted_event_id", ids).execute().data or [])}
    results: dict[str, dict[str, Any]] = {i: {"status": "already_projected", "health_event_id": done[i]} for i in ids if i in done}
    planned: list[tuple[str, dict[str, Any], str | None, dict[str, Any] | None, bool]] = []
    for e in events:
        eid = str(e.get("id") or "")
        if not eid or eid in results:
            continue
        try:
            ledger, table, row, positive = _plan(user_id=user_id, event_id=eid, event_type=str(e["event_type"]), extracted_data=e.get("extracted_data") or {},
                                                 confidence=float(e.get("confidence") or 0), message_id=e.get("message_id"))
            planned.append((eid, ledger, table, row, positive))
        except (ValueError, KeyError, TypeError) as error:
            results[eid] = {"status": "error", "reason": type(error).__name__}

    def one_by_one(items) -> None:
        for eid, _l, _t, _r, _p in items:
            event = next(e for e in events if str(e.get("id")) == eid)
            try:
                results[eid] = project_confirmed_event(db=db, user_id=user_id, event_id=eid, event_type=str(event["event_type"]), extracted_data=event.get("extracted_data") or {},
                                                       confidence=float(event.get("confidence") or 0), message_id=event.get("message_id"))
            except Exception as error:  # noqa: BLE001
                if is_permission_denied(error):
                    raise
                results[eid] = {"status": "error", "reason": type(error).__name__}

    if not planned:
        return results
    try:
        saved = db.table("health_events").insert([p[1] for p in planned]).select("id,source_extracted_event_id").execute().data or []
        ledger_ids = {str(r.get("source_extracted_event_id")): r.get("id") for r in saved}
        if len(saved) != len(planned):
            raise RuntimeError("ledger batch insert returned an unexpected row count")
    except Exception as error:  # noqa: BLE001
        if is_permission_denied(error):
            raise
        one_by_one(planned)
        return results
    by_table: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for eid, _ledger, table, row, positive in planned:
        results[eid] = ({"status": "ledger_only_non_positive", "health_event_id": ledger_ids.get(eid), "domain_table": None} if not positive else
                        {"status": "projected", "health_event_id": ledger_ids.get(eid), "domain_table": table if row else None})
        if positive and row and table:
            by_table.setdefault(table, []).append((eid, row))
    for table, items in by_table.items():
        try:
            db.table(table).insert([row for _eid, row in items]).execute()
        except Exception as error:  # noqa: BLE001
            if is_permission_denied(error):
                raise
            for eid, row in items:
                try:
                    db.table(table).insert(row).execute()
                except Exception as row_error:  # noqa: BLE001
                    if is_permission_denied(row_error):
                        raise
                    results[eid] = {"status": "error", "reason": type(row_error).__name__, "health_event_id": ledger_ids.get(eid)}
    return results
