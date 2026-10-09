from datetime import datetime, timedelta, timezone

from pattern_engine import analyze, recurring_patterns, temporal_correlations
from weekly_insights import build_weekly_insights


def event(event_type, subject, dt, confidence=0.95, event_id=None):
    return {
        "id": event_id or subject + dt.isoformat(),
        "event_type": event_type,
        "extracted_data": {"symptom": subject},
        "confidence": confidence,
        "created_at": dt.isoformat(),
    }


def test_recurring_pattern_requires_three_events():
    now = datetime.now(timezone.utc)
    rows = [event("symptom", "headache", now - timedelta(days=d)) for d in (8, 4, 1)]
    patterns = recurring_patterns(rows)
    assert patterns[0]["subject"] == "headache"
    assert patterns[0]["occurrence_count"] == 3


def test_temporal_correlation_requires_repeated_pairs():
    now = datetime.now(timezone.utc)
    rows = []
    for i, d in enumerate((10, 6, 2)):
        rows.append(event("sleep", "poor sleep", now - timedelta(days=d), event_id=f"s{i}"))
        rows.append(event("symptom", "headache", now - timedelta(days=d + 1), event_id=f"h{i}"))
    correlations = temporal_correlations(rows, window_days=2, min_pairs=3)
    assert correlations
    assert correlations[0]["pair_count"] >= 3
    assert "not proof of causation" in correlations[0]["interpretation"]


def test_analyze_combines_patterns_and_correlations():
    now = datetime.now(timezone.utc)
    rows = []
    for i, d in enumerate((9, 6, 3, 1)):
        rows.append(event("symptom", "cramps", now - timedelta(days=d), event_id=f"c{i}"))
    result = analyze(rows, days=30)
    assert result["event_count"] == 4
    assert result["patterns"]


def test_weekly_insights_reports_data_gap():
    now = datetime.now(timezone.utc)
    result = build_weekly_insights([], now=now)
    assert result["insights"][0]["type"] == "data_gap"


def test_weekly_insights_has_disclaimer():
    now = datetime.now(timezone.utc)
    rows = [event("symptom", "headache", now - timedelta(days=d), event_id=str(d)) for d in (6, 4, 2)]
    result = build_weekly_insights(rows, now=now)
    assert result["insights"]
    assert "not diagnoses" in result["disclaimer"]
