"""Builder output must validate against the response models the endpoints declare.

/insights/weekly, /companion/daily and /intelligence/overview used to return 500 for
every user because the builders and schemas had drifted apart, and health-state
deviations were silently dropped by pydantic.
"""
from datetime import datetime, timedelta, timezone

import schemas as S
from companion_engine import build_daily_companion
from health_state_engine import build_health_state
from learning_engine import build_learning_snapshot
from nutrition_intelligence import analyze_flat as analyze_nutrition_flat
from state_normalizer import normalize_health_state
from weekly_insights import build_weekly_insights, to_response_shape


def _events():
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(14):
        ts = (now - timedelta(days=i)).isoformat()
        rows += [
            {"id": f"s{i}", "event_type": "sleep", "extracted_data": {"hours": 5 if i < 7 else 8}, "confidence": 0.9, "created_at": ts},
            {"id": f"h{i}", "event_type": "hydration", "extracted_data": {"amount_ml": 1500}, "confidence": 0.9, "created_at": ts},
            {"id": f"n{i}", "event_type": "nutrition", "extracted_data": {"name": "dal", "calories": 400}, "confidence": 0.9, "created_at": ts},
        ]
    return rows


def _state(events):
    return normalize_health_state(build_health_state(events, days=7))


def test_weekly_insights_contract_with_and_without_data():
    for events in (_events(), []):
        data = S.WeeklyInsightsData(**to_response_shape(build_weekly_insights(events)))
        for item in data.insights:
            assert 0.0 <= item.confidence <= 1.0 and item.description
    gaps = S.WeeklyInsightsData(**to_response_shape(build_weekly_insights([])))
    assert any(i.category == "data_gap" for i in gaps.insights)


def test_nutrition_and_overview_contract():
    for events in (_events(), []):
        S.NutritionSummaryData(**analyze_nutrition_flat(events))


def test_companion_contract_and_gap_checkins_fire():
    for events in (_events(), []):
        state = _state(events)
        S.CompanionData(**build_daily_companion(state, build_learning_snapshot(events, days=21)))
    empty = build_daily_companion(_state([]), {})
    areas = {f["area"] for f in empty["focus"]}
    assert {"sleep", "hydration", "mood"} <= areas, "normalized data_gaps dict must still trigger check-ins"


def test_state_deviations_are_kept_not_dropped():
    state = S.HealthStateData(**_state(_events()))
    assert state.deviations.sleep_hours is not None
    assert state.deviations.sleep_hours.delta < 0
