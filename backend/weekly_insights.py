"""Weekly health insight generation for Bubbles.

Insights are observational summaries of the user's own logged data. They are
not diagnoses, and sparse data is explicitly reported rather than filled in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pattern_engine import analyze, normalize_events


def _week_boundaries(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    start = now - timedelta(days=7)
    return start, now


def build_weekly_insights(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    start, end = _week_boundaries(now)
    rows = normalize_events(events)
    week_rows = [r for r in rows if start <= r["created_at"] <= end]

    analysis = analyze(rows, days=30)
    weekly_patterns = [
        p for p in analysis["patterns"]
        if p["last_seen"] >= start.isoformat()
    ]
    weekly_correlations = analysis["correlations"]

    insights: list[dict[str, Any]] = []

    if not week_rows:
        insights.append({
            "type": "data_gap",
            "priority": "low",
            "title": "Not enough data yet",
            "text": "Bubbles doesn't have enough recent health data to identify meaningful weekly patterns.",
            "evidence_count": 0,
        })
    else:
        for pattern in weekly_patterns[:5]:
            insights.append({
                "type": "recurrence",
                "priority": "medium" if pattern["occurrence_count"] >= 3 else "low",
                "title": f"Repeated {pattern['subject']}",
                "text": (
                    f"{pattern['subject'].capitalize()} was logged "
                    f"{pattern['occurrence_count']} times. This is a recurring "
                    "observation worth watching over time."
                ),
                "evidence_count": pattern["occurrence_count"],
                "source_event_ids": pattern["source_event_ids"][:8],
            })

        for corr in weekly_correlations[:5]:
            insights.append({
                "type": "association",
                "priority": "low",
                "title": "Two signals appeared together",
                "text": corr["interpretation"],
                "evidence_count": corr["pair_count"],
                "source_event_ids": corr["source_event_ids"],
            })

    return {
        "generated_at": end.isoformat(),
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": 7,
        },
        "data_quality": {
            "event_count": len(week_rows),
            "sufficient_for_pattern_detection": len(week_rows) >= 3,
        },
        "insights": insights[:10],
        "trend": analysis["trend"],
        "disclaimer": (
            "These are observations from your logged data, not diagnoses or proof "
            "that one health factor caused another."
        ),
    }


def to_response_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Map build_weekly_insights output onto schemas.WeeklyInsightsData.

    Builder items are {type, priority, title, text, evidence_count, source_event_ids};
    the API contract (and the frontend) expects {title, description, category,
    confidence, supporting_events}. Without this the endpoint failed validation (500)
    for every user.
    """
    items = []
    for item in data.get("insights") or []:
        evidence = int(item.get("evidence_count") or 0)
        items.append({
            "title": item.get("title") or "Observation",
            "description": item.get("text") or "",
            "category": item.get("type") or "observation",
            # ponytail: evidence-count heuristic (0 for gaps, 0.3 + 0.05/observation, capped 0.85);
            # replace with a calibrated score once insights carry their own confidence.
            "confidence": 0.0 if item.get("type") == "data_gap" else round(min(0.85, 0.3 + 0.05 * evidence), 2),
            "supporting_events": [str(e) for e in (item.get("source_event_ids") or [])],
            "actionable": item.get("type") == "data_gap",
            "suggested_action": "Log this signal so Bubbles can compare it with your usual." if item.get("type") == "data_gap" else None,
        })
    return {**data, "insights": items}
