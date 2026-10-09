import pytest

from health_event_pipeline import (
    ValidatedHealthEvent,
    prepare_db_row,
)


def test_valid_event_is_prepared_as_pending_unconfirmed():
    row = prepare_db_row(
        user_id="user-1",
        message_id="message-1",
        event={
            "event_type": "symptom",
            "extracted_data": {
                "name": "headache",
                "severity": "mild",
            },
            "confidence": 0.9,
        },
    )

    assert row["user_id"] == "user-1"
    assert row["message_id"] == "message-1"
    assert row["event_type"] == "symptom"
    assert row["extraction_status"] == "pending"
    assert row["user_confirmed"] is False


def test_event_type_is_normalized():
    event = ValidatedHealthEvent(
        event_type="  SYMPTOM ",
        extracted_data={},
        confidence=0.8,
    )

    assert event.event_type == "symptom"


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValueError):
        ValidatedHealthEvent(
            event_type="ai_diagnosis",
            extracted_data={},
            confidence=1.0,
        )


def test_confidence_above_one_is_rejected():
    with pytest.raises(ValueError):
        ValidatedHealthEvent(
            event_type="symptom",
            extracted_data={},
            confidence=1.1,
        )


def test_negative_confidence_is_rejected():
    with pytest.raises(ValueError):
        ValidatedHealthEvent(
            event_type="symptom",
            extracted_data={},
            confidence=-0.1,
        )


def test_extra_ai_fields_are_not_persisted():
    row = prepare_db_row(
        user_id="user-1",
        message_id="message-1",
        event={
            "event_type": "symptom",
            "extracted_data": {"name": "nausea"},
            "confidence": 0.7,
            "diagnosis": "something",
            "severity_score": 99,
        },
    )

    assert "diagnosis" not in row
    assert "severity_score" not in row