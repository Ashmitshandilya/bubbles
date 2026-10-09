from living_signal_engine import build_living_signal_map
from health_state_engine import build_health_state
from longitudinal_health_analysis import analyze as analyze_longitudinal


def test_living_map_surfaces_gaps_and_baseline_changes():
    result = build_living_signal_map({
        "status": "observed",
        "event_count": 12,
        "data_gaps": ["sleep", "hydration"],
        "deviations": {"resting_hr": {"delta": 5}},
    }, correlations=[{"pair": "sleep + mood", "confidence": "exploratory"}])
    assert result["observed_signal_count"] == 12
    assert result["baseline_change_count"] == 1
    assert result["data_gap_count"] == 2
    assert any(x["kind"] == "repeated_cooccurrence" for x in result["signals"])
    assert "does not establish causation" in result["interpretation_policy"]


def test_living_map_empty_state():
    """Empty event list returns valid empty-state map, not 500."""
    state = build_health_state([], days=14)
    analysis = analyze_longitudinal([], days=14)
    correlations = analysis.get("correlations", []) if isinstance(analysis, dict) else []
    result = build_living_signal_map(state, correlations=correlations)
    assert result["observed_signal_count"] == 0
    assert result["status"] == "limited"
    assert result["coverage"] == "sparse"
    assert "data_gaps" in result
    assert "signals" in result


def test_living_map_malformed_events_handled_gracefully():
    """String/null in events list handled gracefully without crashing."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    malformed = [
        "not a dict",
        None,
        {
            "id": 1,
            "event_type": "sleep",
            "extracted_data": {"hours": 8},
            "confidence": 0.9,
            "created_at": (now - timedelta(days=2)).isoformat(),
        },
    ]
    state = build_health_state(malformed, days=14)
    analysis = analyze_longitudinal(malformed, days=14)
    correlations = analysis.get("correlations", []) if isinstance(analysis, dict) else []
    result = build_living_signal_map(state, correlations=correlations)
    assert result["observed_signal_count"] == 1
    assert result["status"] in ("limited", "active")


def test_living_map_canonical_events_produce_correct_signals():
    """Supabase-style event dicts produce correct signal structure."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    events = [
        {
            "id": f"evt-{i}",
            "event_type": "sleep",
            "extracted_data": {"hours": 7 + i * 0.5},
            "confidence": 0.9,
            "created_at": (now - timedelta(days=i)).isoformat(),
        }
        for i in range(5)
    ]
    state = build_health_state(events, days=14)
    analysis = analyze_longitudinal(events, days=14)
    correlations = analysis.get("correlations", []) if isinstance(analysis, dict) else []
    result = build_living_signal_map(state, correlations=correlations)
    assert result["observed_signal_count"] == 5
    assert result["status"] == "active"
    assert "signals" in result
    assert "data_gaps" in result
    assert isinstance(result["coverage"], str)
