from typing import Any
from datetime import datetime, timezone

from supabase_client import supabase
from event_filters import clean_data, counts_as_observation, pertinent_negatives


EVENT_COLUMNS = "id, event_type, extracted_data, confidence, created_at, extraction_status, user_confirmed"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_confirmed(event: dict) -> bool:
    return bool(event.get("user_confirmed")) or event.get("extraction_status") == "confirmed"


def _event_matches_query(event: dict, query: str) -> bool:
    query_words = {
        word.lower()
        for word in query.split()
        if len(word) >= 3
    }

    if not query_words:
        return True

    data = event.get("extracted_data") or {}

    searchable = " ".join(
        [
            _text(event.get("event_type")),
            _text(data.get("name")),
            _text(data.get("symptom")),
            _text(data.get("details")),
            _text(data.get("category")),
            _text(data.get("notes")),
            _text(data.get("severity")),
            " ".join(pertinent_negatives(event)),
        ]
    ).lower()

    return any(word in searchable for word in query_words)


def get_relevant_memories(
    user_id: str,
    query: str,
    limit_l1: int = 12,
    limit_l2_l3: int = 12,
    event_rows: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """
    Retrieve relevant personal health context.

    L1 = raw health events
    L2 = persistent health facts
    L3 = derived patterns
    """

    l1: list[dict] = []
    l2: list[dict] = []
    l3: list[dict] = []

    # --------------------------------------------------
    # L1 — RAW HEALTH EVENTS
    # --------------------------------------------------

    try:
        if event_rows is None:   # build_user_context passes the rows it already read (same columns, newest 100)
            event_rows = (
                supabase
                .table("extracted_health_events")
                .select(EVENT_COLUMNS)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            ).data or []

        for event in event_rows:
            # live positives, plus screen rows that carry explicit denials; rejected rows never reach the prompt
            if not (counts_as_observation(event) or pertinent_negatives(event)):
                continue
            if _event_matches_query(event, query):
                l1.append(event)

            if len(l1) >= limit_l1:
                break

    except Exception as error:
        from logging_util import logger
        logger.error(
            component="MEMORY",
            operation="l1_retrieval",
            error=error,
            user_id=user_id,
            context={"query_length": len(query or "")},
            fallback_action="returning_empty_l1",
        )

    # --------------------------------------------------
    # L2 + L3 — PERSISTENT / DERIVED MEMORY
    # --------------------------------------------------

    try:
        result = (
            supabase
            .table("memory_items")
            .select(
                "id, memory_type, content, structured_data, "
                "confidence, created_at, updated_at, review_after, verification_status"
            )
            .eq("user_id", user_id)
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        )

        for memory in result.data or []:
            memory_type = memory.get("memory_type")
            review_after = memory.get("review_after")
            if review_after:
                try:
                    if datetime.fromisoformat(str(review_after).replace("Z", "+00:00")) < datetime.now(timezone.utc):
                        continue
                except ValueError:
                    # Malformed freshness metadata must not silently become trusted memory.
                    continue
            if memory.get("verification_status") in {"rejected", "superseded"}:
                continue

            searchable = " ".join(
                [
                    _text(memory.get("content")),
                    _text(memory.get("structured_data")),
                ]
            ).lower()

            query_words = {
                word.lower()
                for word in query.split()
                if len(word) >= 3
            }

            relevant = (
                not query_words
                or any(word in searchable for word in query_words)
            )

            if not relevant:
                continue

            if memory_type == "L2":
                l2.append(memory)

            elif memory_type == "L3":
                l3.append(memory)

            if len(l2) + len(l3) >= limit_l2_l3:
                break

    except Exception as error:
        from logging_util import logger
        logger.error(
            component="MEMORY",
            operation="l2_l3_retrieval",
            error=error,
            user_id=user_id,
            context={"query_length": len(query or "")},
            fallback_action="returning_empty_l2_l3",
        )

    return {
        "L1": l1,
        "L2": l2,
        "L3": l3,
    }


def format_memory_context(
    memories: dict[str, list[dict]]
) -> str:
    """
    Convert retrieved memories into a compact AI context.
    """

    sections: list[str] = []

    # --------------------------------------------------
    # L2
    # --------------------------------------------------

    if memories["L2"]:
        lines = ["PERSISTENT USER HEALTH FACTS:"]

        for memory in memories["L2"]:
            lines.append(
                f"- {memory.get('content', '')}"
            )

        sections.append("\n".join(lines))

    # --------------------------------------------------
    # L3
    # --------------------------------------------------

    if memories["L3"]:
        lines = ["KNOWN PERSONAL HEALTH PATTERNS:"]

        for memory in memories["L3"]:
            lines.append(
                f"- {memory.get('content', '')}"
            )

        sections.append("\n".join(lines))

    # --------------------------------------------------
    # L1
    # --------------------------------------------------

    if memories["L1"]:
        lines = ["RECENT RELEVANT HEALTH EVENTS:"]

        for event in memories["L1"]:
            denied = pertinent_negatives(event)
            if denied:
                lines.append(f"- [{event.get('created_at')}] Denied by user: {', '.join(denied)}")
                continue
            if not counts_as_observation(event):  # rejected / hedged / other-person rows are never rendered
                continue

            data = clean_data(event.get("extracted_data") if isinstance(event.get("extracted_data"), dict) else {})

            details = ", ".join(
                f"{key}={value}"
                for key, value in data.items()
                if value is not None
            )

            label = "" if _is_confirmed(event) else " (unconfirmed)"
            lines.append(
                f"- [{event.get('created_at')}] "
                f"{event.get('event_type')}: {details}{label}"
            )

        if len(lines) > 1:
            sections.append("\n".join(lines))

    if not sections:
        return "No relevant personal health memory was found."

    return "\n\n".join(sections)