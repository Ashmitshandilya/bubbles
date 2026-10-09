from datetime import datetime, timezone
from typing import Any

from supabase_client import supabase
from event_filters import DEAD_STATUSES, clean_data, is_live_positive, provenance


# --------------------------------------------------
# MEMORY TYPES
# --------------------------------------------------

L2_TYPES = {
    "medical_condition",
    "allergy",
    "family_medical_history",
    "vaccination",
    "medical_procedure",
}

L3_TYPES = {
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
}


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def get_event_subject(
    event_type: str,
    data: dict[str, Any],
) -> str:

    subject = (
        data.get("symptom")
        or data.get("name")
        or data.get("category")
        or data.get("details")
        or event_type.replace("_", " ")
    )

    return str(subject).strip()


def is_promotable(event_type: str, data: dict[str, Any], extraction_status: str | None = None) -> bool:
    """Only a live, present, first-person observation may become memory.

    family_medical_history is about a relative by definition, so the subject check is waived for it.
    """
    row = {"event_type": event_type, "extracted_data": data, "extraction_status": extraction_status}
    if event_type != "family_medical_history":
        return is_live_positive(row)
    prov = provenance(row)
    return (
        (extraction_status or "pending") not in DEAD_STATUSES
        and data.get("present") is not False
        and prov.get("assertion", "present") == "present"
    )


def l2_content(event_type: str, data: dict[str, Any]) -> str:
    subject = get_event_subject(event_type, data)
    if event_type == "family_medical_history":
        relative = data.get("relative") or data.get("relation") or data.get("family_member") or data.get("member")
        return f"Family history: {str(relative).strip()}: {subject}." if relative else f"Family history: {subject}."
    return f"User has reported {subject}."


def create_pattern_key(
    event_type: str,
    data: dict[str, Any],
) -> str:

    subject = get_event_subject(event_type, data)

    return f"{event_type}:{subject.lower()}"


# --------------------------------------------------
# L2 PROMOTION
# --------------------------------------------------

def promote_to_l2(
    user_id: str,
    event_id: str,
    event_type: str,
    data: dict[str, Any],
    confidence: float,
):

    result = (
        supabase
        .table("memory_items")
        .insert({
            "user_id": user_id,
            "memory_type": "L2",
            "content": l2_content(event_type, data),
            "structured_data": {
                **clean_data(data),
                # canonical keys last: event data must never overwrite them
                "event_type": event_type,
                "pattern_key": create_pattern_key(
                    event_type,
                    data,
                ),
                "source_event_ids": [event_id],
                "confirmed": True,
            },
            "source_type": "extracted_health_event",
            "source_id": event_id,
            "confidence": confidence,
            "is_active": True,
        })
        .execute()
    )

    if result.data:
        return {
            "promoted": True,
            "level": "L2",
            "memory_id": result.data[0]["id"],
        }

    return {
        "promoted": False,
        "level": "L2",
        "reason": "insert_failed",
    }


# --------------------------------------------------
# FIND EXISTING L3 PATTERN
# --------------------------------------------------

def find_l3_pattern(
    user_id: str,
    pattern_key: str,
):

    result = (
        supabase
        .table("memory_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("memory_type", "L3")
        .eq("is_active", True)
        .execute()
    )

    for memory in result.data or []:

        structured = memory.get("structured_data") or {}

        if structured.get("pattern_key") == pattern_key:
            return memory

    return None


# --------------------------------------------------
# GET ALL MATCHING L1 EVENTS
# --------------------------------------------------

def get_matching_l1_events(
    user_id: str,
    event_type: str,
    pattern_key: str,
):

    result = (
        supabase
        .table("extracted_health_events")
        .select(
            "id, event_type, extracted_data, "
            "confidence, created_at, message_id, "
            "extraction_status, user_confirmed"
        )
        .eq("user_id", user_id)
        .eq("event_type", event_type)
        .order("created_at", desc=False)
        .execute()
    )

    matching_events = []
    seen_messages: set[str] = set()

    for event in result.data or []:

        # rejected / negated / hedged / other-person / unconfirmed rows never count toward a pattern
        if not is_live_positive(event) or not event.get("user_confirmed"):
            continue

        data = event.get("extracted_data") or {}

        if create_pattern_key(
            event_type,
            data,
        ) == pattern_key:

            # one message that produced several rows (or was retried) is one occurrence
            message_key = str(event.get("message_id") or f"event:{event.get('id')}")
            if message_key in seen_messages:
                continue
            seen_messages.add(message_key)
            matching_events.append(event)

    return matching_events


# --------------------------------------------------
# CREATE L3 PATTERN
# --------------------------------------------------

def create_l3_pattern(
    user_id: str,
    event_type: str,
    data: dict[str, Any],
    events: list[dict[str, Any]],
    confidence: float,
):

    subject = get_event_subject(event_type, data)

    source_event_ids = [
        event["id"]
        for event in events
    ]

    pattern_key = create_pattern_key(
        event_type,
        data,
    )

    content = (
        f"{subject.capitalize()} has appeared repeatedly "
        f"in the user's health data "
        f"({len(source_event_ids)} recorded events)."
    )

    result = (
        supabase
        .table("memory_items")
        .insert({
            "user_id": user_id,
            "memory_type": "L3",
            "content": content,
            "structured_data": {
                "event_type": event_type,
                "pattern_key": pattern_key,
                "source_event_ids": source_event_ids,
                "occurrence_count": len(source_event_ids),
                "first_seen": events[0]["created_at"],
                "last_seen": events[-1]["created_at"],
                "status": "active",
            },
            "source_type": "extracted_health_event",
            "source_id": events[-1]["id"],
            "confidence": confidence,
            "is_active": True,
        })
        .execute()
    )

    if result.data:

        return {
            "promoted": True,
            "level": "L3",
            "memory_id": result.data[0]["id"],
            "occurrences": len(source_event_ids),
        }

    return {
        "promoted": False,
        "level": "L3",
        "reason": "insert_failed",
    }


# --------------------------------------------------
# UPDATE EXISTING L3 PATTERN
# --------------------------------------------------

def update_l3_pattern(
    memory: dict,
    events: list[dict[str, Any]],
    confidence: float,
):

    structured = memory.get("structured_data") or {}

    source_event_ids = [
        event["id"]
        for event in events
    ]

    subject = structured.get(
        "pattern_key",
        "health pattern",
    )

    if ":" in subject:
        subject = subject.split(":", 1)[1]

    updated_structured = {
        **structured,
        "source_event_ids": source_event_ids,
        "occurrence_count": len(source_event_ids),
        "first_seen": events[0]["created_at"],
        "last_seen": events[-1]["created_at"],
        "status": "active",
    }

    content = (
        f"{subject.capitalize()} has appeared repeatedly "
        f"in the user's health data "
        f"({len(source_event_ids)} recorded events)."
    )

    result = (
        supabase
        .table("memory_items")
        .update({
            "content": content,
            "structured_data": updated_structured,
            "confidence": max(
                float(memory.get("confidence") or 0),
                confidence,
            ),
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        })
        .eq("id", memory["id"])
        .eq("user_id", memory["user_id"])
        .execute()
    )

    if result.data:

        return {
            "promoted": True,
            "level": "L3",
            "memory_id": memory["id"],
            "occurrences": len(source_event_ids),
        }

    return {
        "promoted": False,
        "level": "L3",
        "reason": "update_failed",
    }


# --------------------------------------------------
# MAIN PROMOTION ENGINE
# --------------------------------------------------

def promote_health_event(
    user_id: str,
    event_id: str,
    event_type: str,
    extracted_data: dict[str, Any],
    confidence: float,
    user_confirmed: bool = False,
    extraction_status: str | None = None,
):

    data = extracted_data or {}

    if not is_promotable(event_type, data, extraction_status):
        return {
            "promoted": False,
            "level": None,
            "reason": "not_a_live_present_observation",
        }

    # --------------------------------------------------
    # L2
    # --------------------------------------------------

    if event_type in L2_TYPES:

        if not user_confirmed:

            return {
                "promoted": False,
                "level": None,
                "reason": "confirmation_required",
            }

        # Prevent duplicate L2 memory
        existing = (
            supabase
            .table("memory_items")
            .select("id")
            .eq("user_id", user_id)
            .eq("memory_type", "L2")
            .eq("source_id", event_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if existing.data:

            return {
                "promoted": False,
                "level": "L2",
                "reason": "already_promoted",
                "memory_id": existing.data[0]["id"],
            }

        return promote_to_l2(
            user_id=user_id,
            event_id=event_id,
            event_type=event_type,
            data=data,
            confidence=confidence,
        )

    # --------------------------------------------------
    # L3
    # --------------------------------------------------

    if event_type in L3_TYPES:

        if not user_confirmed:

            return {
                "promoted": False,
                "level": None,
                "reason": "confirmation_required",
            }

        if confidence < 0.85:

            return {
                "promoted": False,
                "level": None,
                "reason": "low_confidence",
            }

        pattern_key = create_pattern_key(
            event_type,
            data,
        )

        # ----------------------------------------------
        # Find ALL historical L1 events
        # ----------------------------------------------

        matching_events = get_matching_l1_events(
            user_id=user_id,
            event_type=event_type,
            pattern_key=pattern_key,
        )

        occurrence_count = len(matching_events)

        # ----------------------------------------------
        # First / second occurrence
        # ----------------------------------------------

        if occurrence_count < 3:

            return {
                "promoted": False,
                "level": None,
                "reason": "not_enough_occurrences",
                "occurrences": occurrence_count,
                "required": 3,
            }

        # ----------------------------------------------
        # Check existing L3
        # ----------------------------------------------

        existing_pattern = find_l3_pattern(
            user_id=user_id,
            pattern_key=pattern_key,
        )

        # ----------------------------------------------
        # Create L3
        # ----------------------------------------------

        if not existing_pattern:

            return create_l3_pattern(
                user_id=user_id,
                event_type=event_type,
                data=data,
                events=matching_events,
                confidence=confidence,
            )

        # ----------------------------------------------
        # Update existing L3
        # ----------------------------------------------

        return update_l3_pattern(
            memory=existing_pattern,
            events=matching_events,
            confidence=confidence,
        )

    # --------------------------------------------------
    # Not promotable
    # --------------------------------------------------

    return {
        "promoted": False,
        "level": None,
        "reason": "event_type_not_promotable",
    }