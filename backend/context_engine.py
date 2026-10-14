"""Bubbles personal-context assembly.

The engine is deliberately best-effort: missing optional tables or data must
never make chat unavailable. It returns a compact, auditable context object
for the response layer.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from event_filters import clean_data, counts_as_observation, event_moment, pertinent_negatives


def _get_supabase():
    from supabase_client import supabase
    return supabase


def _safe_table_select(table: str, columns: str, user_id: str, limit: int = 20, order_by: str | None = "created_at") -> list[dict[str, Any]]:
    try:
        query = _get_supabase().table(table).select(columns).eq("user_id", user_id)
        if order_by:  # user_preferences has no created_at/id column in the live schema
            query = query.order(order_by, desc=True)
        result = query.limit(limit).execute()
        return list(result.data or [])
    except Exception as error:
        from logging_util import logger
        logger.warning(
            component="CONTEXT_ENGINE",
            message=f"table_select failed: {error}",
            user_id=user_id,
            context={"table": table, "columns": columns, "limit": limit, "fallback_action": "returning_empty_list"},
        )
        return []


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "type": event.get("event_type"),
        "data": event.get("extracted_data") or {},
        "confidence": event.get("confidence"),
        "created_at": event.get("created_at"),
        "extraction_status": event.get("extraction_status"),
        "user_confirmed": bool(event.get("user_confirmed")),
    }


def _denials(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Explicit denials ("no chest pain") recorded on screen rows, newest first."""
    out = []
    for row in rows:
        concepts = pertinent_negatives(row)
        if concepts:
            moment = event_moment(row)
            out.append({"concepts": concepts, "date": moment.date().isoformat() if moment else None})
    return out[:limit]


def _profile_rows(user_id: str) -> list[dict[str, Any]]:
    try:
        result = (
            _get_supabase().table("profiles")
            .select("id, display_name, date_of_birth, gender, timezone")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return list(result.data or [])
    except Exception as error:
        from logging_util import logger
        logger.warning(
            component="CONTEXT_ENGINE",
            message=f"profile_fetch failed: {error}",
            user_id=user_id,
            context={"table": "profiles", "fallback_action": "returning_empty_profile"},
        )
        return []


# ponytail: one small shared pool for per-request fan-out; size it up if many chats run at once.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bubbles-ctx")


def build_user_context(user_id: str, query: str) -> dict[str, Any]:
    from memory_retrieval import EVENT_COLUMNS, get_relevant_memories, format_memory_context

    # The reads are independent, so they run together (each one is a network round trip). The events are read once and
    # shared: memory retrieval used to read the same table again.
    events_job = _POOL.submit(_safe_table_select, "extracted_health_events", EVENT_COLUMNS, user_id, 100)
    profile_job = _POOL.submit(_profile_rows, user_id)
    preferences_job = _POOL.submit(_safe_table_select, "user_preferences", "*", user_id, 1, None)

    rows = events_job.result()
    memories = get_relevant_memories(user_id=user_id, query=query, event_rows=rows)
    # over-fetch: dead / non-positive rows are dropped below and must not crowd out live ones
    rows = rows[:40]
    recent_events = [row for row in rows if counts_as_observation(row)][:20]
    denials = _denials(rows)
    profile = profile_job.result()
    preferences = preferences_job.result()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile[0] if profile else {},
        "preferences": preferences[0] if preferences else {},
        "recent_events": [_compact_event(event) for event in recent_events],
        "pertinent_negatives": denials,
        "relevant_memories": memories,
        "memory_context": format_memory_context(memories),
    }


def format_user_context(context: dict[str, Any]) -> str:
    sections: list[str] = []
    profile = context.get("profile") or {}
    preferences = context.get("preferences") or {}

    if profile:
        safe_profile = {
            key: value for key, value in profile.items()
            if key in {"display_name", "date_of_birth", "gender", "timezone"} and value not in (None, "")
        }
        if safe_profile:
            sections.append("PROFILE:\n" + "\n".join(f"- {k}: {v}" for k, v in safe_profile.items()))

    if preferences:
        safe_preferences = {k: v for k, v in preferences.items() if k not in {"id", "user_id"} and v not in (None, "")}
        if safe_preferences:
            sections.append("PREFERENCES:\n" + "\n".join(f"- {k}: {v}" for k, v in safe_preferences.items()))

    memory_context = context.get("memory_context", "").strip()
    if memory_context:
        sections.append(memory_context)

    recent = context.get("recent_events") or []
    if recent:
        lines = []
        for event in recent[:12]:
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            details = ", ".join(f"{k}={v}" for k, v in clean_data(data).items() if v is not None)
            confirmed = event.get("user_confirmed") or event.get("extraction_status") == "confirmed"
            lines.append(
                f"- {event.get('type')}: {details} "
                f"(confidence={event.get('confidence')}, at={event.get('created_at')})"
                + ("" if confirmed else " (unconfirmed)")
            )
        sections.append("RECENT HEALTH EVENTS:\n" + "\n".join(lines))

    denied = context.get("pertinent_negatives") or []
    if denied:
        sections.append("EXPLICIT DENIALS (the user said these are NOT happening):\n" + "\n".join(
            f"- Denied by user: {', '.join(item.get('concepts') or [])}" + (f" ({item['date']})" if item.get("date") else "")
            for item in denied
        ))

    return "\n\n".join(sections)
