"""Batch 26: body-system intelligence over existing organ tracker signals."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from organ_tracker import assess_all
from event_filters import clean_data, counts_as_observation


EYE_WINDOW_DAYS = 14
MIN_SCREEN_DAYS = 3        # an average over fewer logged days says too little
#: symptom names (health_semantics display names) that count towards each system's "symptom days". Eyes also read their own tracker (eye_snapshot).
SYSTEM_SYMPTOM_NAMES: dict[str, frozenset[str]] = {
    "ears": frozenset({"ear pain", "ringing in the ears", "hearing loss", "sudden hearing loss"}),
    "mouth": frozenset({"mouth ulcers", "toothache", "bleeding gums"}),
    "bladder": frozenset({"burning when urinating", "frequent urination"}),
    "skin": frozenset({"rash"}),
    "breasts": frozenset({"breast pain", "a breast lump"}),
}
#: names a chat or a symptom log gives to eye complaints (health_semantics display names + the tracker's own vocabulary)
EYE_SYMPTOM_NAMES = frozenset({"eye strain", "dry eyes", "red eyes", "eye pain", "itchy eyes", "blurred vision"})


def _event_day(event: dict[str, Any], data: dict[str, Any]) -> str:
    return str(data.get("date") or event.get("created_at") or "")[:10]


def eye_snapshot(events: list[dict[str, Any]], today: datetime | None = None) -> dict[str, Any]:
    """Facts about the eyes from the person's own logs: average screen time and the number of days with eye symptoms in the last
    two weeks, and the date of the last eye exam they recorded. Only what was logged: no entries means no keys, never zeros."""
    since = ((today or datetime.now(timezone.utc)).date() - timedelta(days=EYE_WINDOW_DAYS)).isoformat()
    screen: dict[str, float] = {}
    symptom_days: set[str] = set()
    last_exam = ""
    for event in events or []:
        if not isinstance(event, dict) or not counts_as_observation(event):
            continue
        data = clean_data(event.get("extracted_data") if isinstance(event.get("extracted_data"), dict) else {})
        kind = str(event.get("event_type") or "")
        day = _event_day(event, data)
        if kind == "eye_check":
            exam = str(data.get("last_exam") or "")[:10]
            if exam > last_exam:
                last_exam = exam
            if day < since:
                continue
            hours = data.get("screen_hours")
            if isinstance(hours, (int, float)) and not isinstance(hours, bool):
                screen[day] = max(screen.get(day, 0.0), float(hours))   # one value per day: the longest the person logged
            comfort = data.get("eye_comfort")
            if data.get("eye_symptoms") or (isinstance(comfort, (int, float)) and not isinstance(comfort, bool) and comfort <= 2):
                symptom_days.add(day)
        elif kind in {"symptom", "menstrual_symptom"} and day >= since:
            if str(data.get("name") or data.get("symptom") or "").strip().lower() in EYE_SYMPTOM_NAMES:
                symptom_days.add(day)
    out: dict[str, Any] = {}
    if len(screen) >= MIN_SCREEN_DAYS:
        out["screen_hours_avg"] = round(sum(screen.values()) / len(screen), 1)
    if symptom_days:
        out["eye_symptom_days"] = len(symptom_days)
    if last_exam:
        out["last_eye_exam"] = last_exam
    return out


def symptom_day_snapshot(events: list[dict[str, Any]], today: datetime | None = None) -> dict[str, Any]:
    """`<system>_symptom_days`: how many different days in the last two weeks the person logged or told Bubbles about a symptom of that
    system. Only live, positive, first-person events count (denials, other people and rejected rows never do); no events means no key."""
    since = ((today or datetime.now(timezone.utc)).date() - timedelta(days=EYE_WINDOW_DAYS)).isoformat()
    days: dict[str, set[str]] = {system: set() for system in SYSTEM_SYMPTOM_NAMES}
    for event in events or []:
        if not isinstance(event, dict) or not counts_as_observation(event):
            continue
        if str(event.get("event_type") or "") not in {"symptom", "menstrual_symptom"}:
            continue
        data = clean_data(event.get("extracted_data") if isinstance(event.get("extracted_data"), dict) else {})
        day = _event_day(event, data)
        if day < since:
            continue
        name = str(data.get("name") or data.get("symptom") or "").strip().lower()
        for system, names in SYSTEM_SYMPTOM_NAMES.items():
            if name in names:
                days[system].add(day)
    return {f"{system}_symptom_days": len(found) for system, found in days.items() if found}


def build_body_system_intelligence(events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    source_ids: dict[str, list[str]] = {}
    # oldest first so the newest value wins the snapshot (readers deliver newest-first)
    live = sorted((e for e in events or [] if isinstance(e, dict) and counts_as_observation(e)),
                  key=lambda e: str(e.get("created_at") or ""))
    for event in live:
        data = event.get("extracted_data") or {}
        if isinstance(data, dict):
            for key, value in clean_data(data).items():
                if value is not None:
                    snapshot[key] = value
                    source_ids.setdefault(key, []).append(str(event.get("id")))
    snapshot.update(symptom_day_snapshot(events))
    snapshot.update(eye_snapshot(events))   # derived from the eye logs, so a single latest value never stands in for a pattern
    snapshot["source_ids"] = source_ids
    assessments = assess_all(snapshot)
    rows = []
    for item in assessments:
        row = item.__dict__.copy() if hasattr(item, "__dict__") else dict(item)
        row["signals"] = [s.__dict__ if hasattr(s, "__dict__") else s for s in row.get("signals", [])]
        rows.append(row)
    observed = sum(1 for r in rows if r.get("data_completeness", 0) > 0)
    return {
        "systems": rows,
        "systems_with_data": observed,
        "total_systems": len(rows),
        "interpretation": "Body-system signals organize available evidence; they do not diagnose disease or establish that an organ is healthy or damaged.",
    }
