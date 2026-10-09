from organ_tracker import assess_organ, explain_interaction


def test_missing_data_reduces_confidence_not_health_risk():
    result = assess_organ("heart", {})
    assert result.data_completeness == 0
    assert result.confidence < 0.5
    assert any("absence of a signal" in x for x in result.limitations)


def test_smoking_hits_multiple_systems():
    snapshot = {"smoking_status": "current"}
    lungs = assess_organ("lungs", snapshot)
    heart = assess_organ("heart", snapshot)
    brain = assess_organ("brain", snapshot)
    assert lungs.score < 100
    assert heart.score < 100
    assert brain.score < 100


def test_combined_context_is_not_structural_damage_claim():
    snapshot = {
        "smoking_status": "current",
        "sleep_hours_avg": 5.5,
    }
    interactions = explain_interaction(snapshot)
    assert interactions
    assert "proof of organ damage" in interactions[0]["message"]


def test_direct_data_increases_completeness():
    snapshot = {
        "blood_pressure": "120/80",
        "lipids": {"non_hdl": 100},
        "source_ids": {"direct_clinical_data": ["event-1"]},
    }
    result = assess_organ("heart", snapshot)
    assert result.data_completeness > 0
    assert result.confidence > 0.25


def test_no_data_is_unknown_and_has_no_score():
    result = assess_organ("heart", {})
    assert result.score is None
    assert result.status == "unknown"
    assert result.confidence == 0.0


def test_score_is_risk_indicator_not_health_percentage():
    result = assess_organ("lungs", {"smoking_status": "current"})
    assert result.score == 30.0
    assert "percentage of organ health" in result.limitations[0]


def test_unknown_string_does_not_create_risk_signal():
    result = assess_organ("heart", {"high_salt_pattern": "unknown"})
    assert result.score is None
    assert result.status == "unknown"


def test_source_id_string_is_not_split_into_characters():
    result = assess_organ(
        "lungs",
        {
            "smoking_status": "current",
            "source_ids": {"smoking": "event-123"},
        },
    )
    assert result.signals[0].source_ids == ["event-123"]
