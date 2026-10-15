"""Bubbles personal-context assembly.

The engine is deliberately best-effort: missing optional tables or data must
never make chat unavailable. It returns a compact, auditable context object
for the response layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from event_filters import clean_data, counts_as_observation, event_moment, pertinent_negatives
from ttl_cache import TTLCache


def _get_supabase():
    from supabase_client import supabase
    return supabase


def _select_rows(table: str, columns: str, user_id: str, limit: int = 20, order_by: str | None = "created_at") -> list[dict[str, Any]]:
    """One owner-scoped read. Raises on a database problem (callers decide what a failure means)."""
    query = _get_supabase().table(table).select(columns).eq("user_id", user_id)
    if order_by:  # user_preferences has no created_at/id column in the live schema
        query = query.order(order_by, desc=True)
    return list(query.limit(limit).execute().data or [])


def _safe_table_select(table: str, columns: str, user_id: str, limit: int = 20, order_by: str | None = "created_at") -> list[dict[str, Any]]:
    try:
        return _select_rows(table, columns, user_id, limit, order_by)
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


# Profile and preferences change rarely, and the chat reads them on every message: remembered per person for a minute. The writers
# (main.sync_profile_from_auth, onboarding completion) call forget_profile(), so a change shows on the very next message.
# Holds the person's own profile row, per person, in process memory only (ttl_cache rules).
_profile_cache = TTLCache("profile_context", ttl_s=60, max_entries=5000)


def forget_profile(user_id: str) -> None:
    _profile_cache.invalidate(str(user_id))


def _fetch_profile(user_id: str) -> dict[str, Any]:
    rows = (
        _get_supabase().table("profiles")
        .select("id, display_name, date_of_birth, gender, timezone")
        .eq("id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    return dict(rows[0]) if rows else {}


def _fetch_preferences(user_id: str) -> dict[str, Any]:
    rows = _select_rows("user_preferences", "*", user_id, limit=1, order_by=None)
    return dict(rows[0]) if rows else {}


def build_user_context(user_id: str, query: str) -> dict[str, Any]:
    """The person's own context for a reply. The four reads (events, memory items, profile, preferences) are independent, so they
    run side by side: one round trip of waiting instead of five. One event read serves both memory retrieval and the recent-events
    list (they used to read the same table twice)."""
    import memory_retrieval
    from chat_concurrency import settled, submit_io

    user_id = str(user_id)
    cached = _profile_cache.peek(user_id)
    jobs = {
        "events": submit_io(settled, memory_retrieval.fetch_event_rows, user_id),
        "memory": submit_io(settled, memory_retrieval.fetch_memory_rows, user_id),
    }
    if cached is None:
        jobs["profile"] = submit_io(settled, _fetch_profile, user_id)
        jobs["prefs"] = submit_io(settled, _fetch_preferences, user_id)
    done = {name: job.result() for name, job in jobs.items()}

    event_rows, event_error = done["events"]
    memory_rows, memory_error = done["memory"]
    memories = memory_retrieval.get_relevant_memories(
        user_id=user_id, query=query,
        event_rows=event_error if event_error is not None else event_rows,
        memory_rows=memory_error if memory_error is not None else memory_rows,
    )

    # over-fetch: dead / non-positive rows are dropped below and must not crowd out live ones
    rows = list(event_rows or [])[:40]
    recent_events = [row for row in rows if counts_as_observation(row)][:20]
    denials = _denials(rows)

    if cached is not None:
        profile, preferences = cached
    else:
        profile, profile_error = done["profile"]
        preferences, prefs_error = done["prefs"]
        if profile_error is not None:
            from logging_util import logger
            logger.warning(
                component="CONTEXT_ENGINE",
                message=f"profile_fetch failed: {profile_error}",
                user_id=user_id,
                context={"table": "profiles", "fallback_action": "returning_empty_profile"},
            )
        if prefs_error is not None:
            from logging_util import logger
            logger.warning(
                component="CONTEXT_ENGINE",
                message=f"table_select failed: {prefs_error}",
                user_id=user_id,
                context={"table": "user_preferences", "limit": 1, "fallback_action": "returning_empty_list"},
            )
        profile, preferences = profile or {}, preferences or {}
        if profile_error is None and prefs_error is None:   # a failed read is never remembered
            _profile_cache.put(user_id, (profile, preferences))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "preferences": preferences,
        "recent_events": [_compact_event(event) for event in recent_events],
        "pertinent_negatives": denials,
        "relevant_memories": memories,
        "memory_context": memory_retrieval.format_memory_context(memories),
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
