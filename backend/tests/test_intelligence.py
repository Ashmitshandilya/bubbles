from nutrition_intelligence import analyze as analyze_nutrition
from cycle_intelligence import analyze as analyze_cycle


def test_nutrition_ignores_missing_values_and_summarizes_logged_values():
    result = analyze_nutrition([
        {"event_type": "meal", "created_at": "2026-09-01T10:00:00Z", "extracted_data": {"calories": 500, "protein_g": 20}},
        {"event_type": "meal", "created_at": "2026-09-01T14:00:00Z", "extracted_data": {"food": "fruit"}},
        {"event_type": "hydration", "created_at": "2026-09-01T15:00:00Z", "extracted_data": {"water_ml": 750}},
    ])
    assert result["summary"]["total_calories_logged"] == 500
    assert result["summary"]["total_protein_g_logged"] == 20
    assert result["summary"]["total_water_ml_logged"] == 750
    assert result["summary"]["logged_meals_without_calories"] == 1


def test_cycle_uses_period_starts_without_diagnosing():
    result = analyze_cycle([
        {"event_type": "menstrual_cycle", "created_at": "2026-07-01", "extracted_data": {"period_start": "2026-07-01", "is_start": True}},
        {"event_type": "menstrual_cycle", "created_at": "2026-07-30", "extracted_data": {"period_start": "2026-07-30", "is_start": True}},
    ])
    assert result["cycle"]["period_start_count"] == 2
    assert result["cycle"]["start_to_start_intervals"] == [29]
    assert "not diagnosed" in result["interpretation"]
