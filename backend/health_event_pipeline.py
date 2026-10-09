"""Trusted boundary for AI-extracted personal health events.

AI-generated health events are untrusted until they pass this validation
boundary. Validated events are persisted as pending/unconfirmed records.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_EVENT_TYPES = {
    "symptom",
    "menstrual_symptom",
    "food",
    "hydration",
    "sleep",
    "activity",
    "exercise",
    "weight",
    "vital_sign",
    "medication",
    "supplement",
    "mood",
    "stress",
    "lifestyle",
    "lab_result",
    "doctor_visit",
    "pregnancy_test",
    "wellness_checkin",
    "medical_condition",
    "allergy",
    "family_medical_history",
    "vaccination",
    "medical_procedure",
}


class ValidatedHealthEvent(BaseModel):
    """Validated representation of one AI-extracted health event."""

    model_config = ConfigDict(extra="ignore")

    event_type: str
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_EVENT_TYPES:
            raise ValueError("unsupported health event type")

        return value


def prepare_db_row(
    *,
    user_id: str,
    message_id: str | None,
    event: Any,
) -> dict[str, Any]:
    """Convert an AI event into a safe DB insertion row."""

    # Plain dict events (built by the deterministic parser / reconciliation) carry their own extracted_data.
    # Before this branch a dict event silently stored extracted_data={} .
    if isinstance(event, dict):
        extracted_data = dict(event.get("extracted_data") or {})
    # Handle both HealthEvent (from bubbles_ai) and ValidatedHealthEvent
    elif hasattr(event, 'extracted_data') and hasattr(event.extracted_data, 'model_dump'):
        # It's a HealthEvent from bubbles_ai with ExtractedHealthData model
        extracted_data = event.extracted_data.model_dump()
    elif hasattr(event, 'extracted_data') and isinstance(event.extracted_data, dict):
        # It's already a dict
        extracted_data = event.extracted_data
    else:
        # Try to validate as ValidatedHealthEvent
        extracted_data = {}

    validated = ValidatedHealthEvent(
        event_type=event.event_type if hasattr(event, 'event_type') else event.get("event_type", "unknown"),
        extracted_data=extracted_data,
        confidence=event.confidence if hasattr(event, 'confidence') else event.get("confidence", 0.0),
    )

    return {
        "user_id": user_id,
        "message_id": message_id,
        "event_type": validated.event_type,
        "extracted_data": validated.extracted_data,
        "confidence": validated.confidence,
        "extraction_status": "pending",
        "user_confirmed": False,
    }