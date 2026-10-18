"""Bubbles longitudinal pattern and correlation engine.

This module is intentionally deterministic and evidence-aware. It identifies
repeated observations and temporal co-occurrence; it does NOT infer medical
causation or diagnose conditions.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Iterable

from event_filters import counts_as_observation, event_moment


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _subject(event: dict[str, Any]) -> str:
    # raw DB rows carry extracted_data, compact context rows carry data
    data = event.get("extracted_data") or event.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    value = (
        data.get("symptom")
        or data.get("name")
        or data.get("category")
        or data.get("activity")
        or data.get("mood")
        or data.get("type")
    )
    if value is None:
        value = event.get("event_type", "health event")
    return str(value).strip().lower()


def _is_normalized(event: dict[str, Any]) -> bool:
    """Rows produced by normalize_events itself (second pass over our own output)."""
    return "subject" in event and "data" in event and isinstance(event.get("created_at"), datetime)


def normalize_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return clean, chronologically ordered observation records.

    Only live positive observations survive: rejected/superseded/retracted rows,
    explicit denials, hedged/other-person rows and symptom-screen rows are dropped.
    """
    normalized: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if _is_normalized(event):  # already filtered; re-normalizing would lose extracted_data
            normalized.append(event)
            continue
        # Handle both raw DB format (event_type + extracted_data) and
        # compact format from _compact_event (type + data)
        raw_data = event.get("extracted_data") or event.get("data") or {}
        if not isinstance(raw_data, dict):
            raw_data = {}
        event_type = str(event.get("event_type") or event.get("type") or "unknown").lower()
        if not counts_as_observation({
            "event_type": event_type,
            "extracted_data": raw_data,
            "extraction_status": event.get("extraction_status"),
        }):
            continue
        dt = event_moment({"extracted_data": raw_data, "created_at": event.get("created_at")})             or _parse_dt(event.get("created_at") or event.get("timestamp"))
        if dt is None:
            continue
        normalized.append({
            "id": event.get("id"),
            "event_type": event_type,
            "subject": _subject(event),
            "data": raw_data,
            "confidence": float(event.get("confidence") or 0),
            "created_at": dt,
        })
    return sorted(normalized, key=lambda e: e["created_at"])


_SLUG = re.compile(r"[^a-z0-9_-]+")
MAX_OCCURRENCES = 14   # newest dated occurrences returned for one pattern
MAX_PAIRS = 12         # newest dated co-occurring pairs returned for one correlation


def slug(value: Any) -> str:
    """URL-safe fragment for a subject or event type ("Low back pain" -> "low-back-pain")."""
    return _SLUG.sub("-", str(value).strip().lower()).strip("-")[:40] or "x"


def recurrence_id(event_type: Any, subject: Any) -> str:
    return f"rec:{slug(event_type)}:{slug(subject)}"


def correlation_id(type_a: Any, subject_a: Any, type_b: Any, subject_b: Any) -> str:
    return f"co:{slug(type_a)}:{slug(subject_a)}|{slug(type_b)}:{slug(subject_b)}"


def recurrence_confidence(count: int, span_days: float, average: float) -> str:
    """The one place a repeated item gets its confidence word (patterns page, Today and the detail sheet read this)."""
    if average < 0.5:
        return "low"
    if count >= 8 and span_days >= 14:
        return "high"
    return "medium" if count >= 5 else "low"


def correlation_confidence(pair_count: int) -> str:
    return "high" if pair_count >= 6 else "medium" if pair_count >= 4 else "low"


def _day(row: dict[str, Any]) -> str:
    return row["created_at"].date().isoformat()


def _number(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
            if isfinite(number):
                return number
        except (TypeError, ValueError):
            continue
    return None


#: Metrics people log every day. Co-occurrence or "recurrence" of these is guaranteed by logging habits, so counting
#: them produces confident-looking noise ("sleep and water were recorded together 54 times"). Episodic events
#: (symptoms, mood, medication changes) are what patterns are about.
ROUTINE_TYPES = frozenset({"sleep", "hydration", "weight", "vital_sign", "activity", "exercise", "food", "supplement", "lifestyle"})


_MEASUREMENT_KEYS = ("duration_minutes", "hours", "duration_hours", "amount_ml", "water_ml", "steps", "weight_kg", "value", "amount", "minutes", "count")


def _is_routine_measurement(row: dict[str, Any]) -> bool:
    """A daily metric reading ("slept 7h", "1.8 L water", "6,420 steps"), as opposed to a qualitative note
    such as a sleep event described as "poor sleep", which is a legitimate pattern candidate."""
    if row.get("event_type") not in ROUTINE_TYPES:
        return False
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    return any(data.get(key) is not None for key in _MEASUREMENT_KEYS)


def _episodic(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if not _is_routine_measurement(r)]


def recurring_patterns(events: Iterable[dict[str, Any]], *, min_occurrences: int = 3) -> list[dict[str, Any]]:
    """Find repeated event subjects with minimum occurrence/confidence guards."""
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in _episodic(normalize_events(events)):
        grouped[(event["event_type"], event["subject"])].append(event)

    patterns: list[dict[str, Any]] = []
    for (event_type, subject), rows in grouped.items():
        if len(rows) < min_occurrences:
            continue
        confidence = sum(r["confidence"] for r in rows) / len(rows)
        span_days = max((rows[-1]["created_at"] - rows[0]["created_at"]).total_seconds() / 86400, 0)
        patterns.append({
            "kind": "recurrence",
            "event_type": event_type,
            "subject": subject,
            "occurrence_count": len(rows),
            "average_confidence": round(confidence, 3),
            "first_seen": rows[0]["created_at"].isoformat(),
            "last_seen": rows[-1]["created_at"].isoformat(),
            "span_days": round(span_days, 1),
            "id": recurrence_id(event_type, subject),
            "confidence_label": recurrence_confidence(len(rows), span_days, confidence),
            "occurrences": [{"id": r["id"] or None, "date": _day(r)} for r in reversed(rows[-MAX_OCCURRENCES:])],
            "source_event_ids": [r["id"] for r in rows if r["id"]],
            "observation": f"{subject} was recorded {len(rows)} times.",
        })

    return sorted(patterns, key=lambda p: (-p["occurrence_count"], p["subject"]))


def temporal_correlations(
    events: Iterable[dict[str, Any]],
    *,
    window_days: int = 2,
    min_pairs: int = 3,
) -> list[dict[str, Any]]:
    """Detect repeated temporal co-occurrence between distinct event subjects.

    A correlation here means 'occurred near each other repeatedly'. It is not
    evidence that one event caused another.
    """
    rows = _episodic(normalize_events(events))
    candidates: defaultdict[tuple[str, str, str, str], list[tuple[Any, Any, str, str]]] = defaultdict(list)

    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            if (right["created_at"] - left["created_at"]).total_seconds() > window_days * 86400:
                break
            if left["event_type"] == right["event_type"] and left["subject"] == right["subject"]:
                continue
            key_left = (left["event_type"], left["subject"])
            key_right = (right["event_type"], right["subject"])
            ordered = sorted([key_left, key_right])
            key = (ordered[0][0], ordered[0][1], ordered[1][0], ordered[1][1])
            pair = (left, right) if (left["event_type"], left["subject"]) == ordered[0] else (right, left)
            candidates[key].append((pair[0]["id"], pair[1]["id"], _day(pair[0]), _day(pair[1])))

    results: list[dict[str, Any]] = []
    for (type_a, subject_a, type_b, subject_b), pairs in candidates.items():
        if len(pairs) < min_pairs:
            continue
        results.append({
            "kind": "temporal_correlation",
            "a": {"event_type": type_a, "subject": subject_a},
            "b": {"event_type": type_b, "subject": subject_b},
            "pair_count": len(pairs),
            "window_days": window_days,
            "strength": round(min(1.0, len(pairs) / 6), 3),
            "id": correlation_id(type_a, subject_a, type_b, subject_b),
            "confidence_label": correlation_confidence(len(pairs)),
            "pairs": [{"a": {"id": a_id or None, "date": a_day}, "b": {"id": b_id or None, "date": b_day}}
                      for a_id, b_id, a_day, b_day in reversed(pairs[-MAX_PAIRS:])],
            "interpretation": (
                f"{subject_a} and {subject_b} were recorded within "
                f"{window_days} days of each other {len(pairs)} times. "
                "This is a temporal association, not proof of causation."
            ),
            "source_event_ids": [x for pair in pairs for x in pair[:2] if x][:12],
        })

    return sorted(results, key=lambda x: (-x["pair_count"], x["a"]["subject"], x["b"]["subject"]))


def trend_summary(events: Iterable[dict[str, Any]], days: int = 7) -> dict[str, Any]:
    rows = normalize_events(events)
    if not rows:
        return {"period_days": days, "event_count": 0, "by_type": {}, "signals": []}

    cutoff = rows[-1]["created_at"] - timedelta(days=days)
    recent = [r for r in rows if r["created_at"] >= cutoff]
    by_type: defaultdict[str, int] = defaultdict(int)
    for row in recent:
        by_type[row["event_type"]] += 1

    return {
        "period_days": days,
        "event_count": len(recent),
        "by_type": dict(sorted(by_type.items())),
        "signals": [
            {"event_type": k, "count": v}
            for k, v in sorted(by_type.items(), key=lambda item: -item[1])[:8]
        ],
    }


def analyze(events: Iterable[dict[str, Any]], *, days: int = 30) -> dict[str, Any]:
    rows = normalize_events(events)
    if rows:
        cutoff = rows[-1]["created_at"] - timedelta(days=days)
        rows = [r for r in rows if r["created_at"] >= cutoff]
    return {
        "period_days": days,
        "event_count": len(rows),
        "patterns": recurring_patterns(rows),
        "correlations": temporal_correlations(rows),
        "trend": trend_summary(rows, min(days, 7)),
    }
