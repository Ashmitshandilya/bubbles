"""Saves what a person stated plainly, straight away, and leaves the rest waiting for their OK (policy: event_policy.py).

Runs after the events of a message are staged (pending) and only for a person who agreed to save details noticed in chat (staging itself needs that yes).
"auto" events are confirmed through the same code as a tap on Save (health_event_confirm.decide), so they land in the same logs and memory the same way;
the copy into the health record runs after the reply. A sleep, weight or mood already saved for the same day is not written twice: that one is asked about.
Never raises: whatever fails simply stays pending, which is exactly what happened before this existed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import event_policy
import paragraph_extras
from ttl_cache import TTLCache

ONE_PER_DAY = ("sleep", "weight", "mood")


def _day(event: dict[str, Any]) -> str:
    return str((event.get("extracted_data") or {}).get("date") or "")[:10]


def _already_saved(db: Any, uid: str, auto: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """(type, day) of sleep, weight and mood already saved in the last few days, so the same day is not written twice."""
    wanted = {e["event_type"] for e in auto if e["event_type"] in ONE_PER_DAY}
    if not wanted:
        return set()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        rows = (db.table("extracted_health_events").select("event_type,extracted_data,extraction_status").eq("user_id", uid).in_("event_type", sorted(wanted))
                .eq("extraction_status", "confirmed").gte("created_at", cutoff).limit(60).execute().data or [])
    except Exception:  # noqa: BLE001 - cannot tell: ask instead of saving blind
        return {(t, _day(e)) for e in auto if (t := e["event_type"]) in wanted}
    return {(r["event_type"], str((r.get("extracted_data") or {}).get("date") or "")[:10]) for r in rows}


def autosave(db: Any, uid: str, persisted: list[dict[str, Any]], defer: Callable[..., Any]) -> dict[str, list[dict[str, Any]]]:
    """Confirm the plainly stated events among ``persisted`` (changing their ``status`` to "confirmed" and marking ``auto_saved``). Returns
    ``{"saved": [...], "ask": [...]}``: what was saved, and what is still waiting for the person's OK."""
    try:
        staged = [e for e in persisted if e.get("id") and e.get("status") in (None, "pending")]
        auto, ask = event_policy.split(staged)
        if not auto:
            return {"saved": [], "ask": ask}
        taken = _already_saved(db, uid, auto)
        fresh = []
        for e in auto:
            if (e["event_type"], _day(e)) in taken:
                ask.append(e)   # that day already has one saved: the person decides whether this replaces it
            else:
                fresh.append(e)
        if not fresh:
            return {"saved": [], "ask": ask}
        from health_event_confirm import Decision, decide, project_and_remember
        answers, to_project, _updated = decide(db, uid, [Decision(id=str(e["id"]), confirmed=True) for e in fresh])
        saved = []
        for event, answer in zip(fresh, answers):
            if answer.get("status") == "confirmed":
                event["status"], event["auto_saved"] = "confirmed", True
                saved.append(event)
            else:
                ask.append(event)
        if to_project:
            defer(project_and_remember, db, uid, to_project)
        return {"saved": saved, "ask": ask}
    except Exception:  # noqa: BLE001
        from logging_util import logger
        logger.warning(component="CHAT", operation="autosave", error=None, user_id=uid, fallback_action="left_pending")
        return {"saved": [], "ask": [e for e in persisted if e.get("id") and e.get("status") in (None, "pending")]}


_nudged = TTLCache("saving_nudge", ttl_s=6 * 3600, max_entries=5000)   # one gentle note per person per six hours, never a nag


def off_note(db: Any, uid: str) -> str:
    """When the person typed things Bubbles could log but saving from chat is off: say so once in a while, kindly. Never raises."""
    try:
        from consent import is_granted
        if is_granted(db, uid, "health_memory_from_chat") or _nudged.peek(uid):
            return ""
        _nudged.put(uid, True)
        return ("I understood these, but saving details from chat is off, so I haven't logged them. If you'd like me to log things like this for you, turn on "
                "\"Save details Bubbles notices in chat\" in Your choices. Nothing is saved without that.")
    except Exception:  # noqa: BLE001
        return ""


def mark_tension_day(db: Any, uid: str, text: str) -> bool:
    """A fight with a partner, said in plain words, marks today as a tension day for the person's own patterns (the same date-only marker Orbit's "After a
    fight" writes; no words are kept). Never raises."""
    try:
        if not paragraph_extras.conflict_with_partner(text):
            return False
        from consent import is_granted
        if not is_granted(db, uid, "health_memory_from_chat"):
            return False
        import doc_store
        from calc_core import local_today
        doc_store.put(db, uid, "orbit_tension", local_today().isoformat(), {"marked": True, "from": "chat"})
        return True
    except Exception:  # noqa: BLE001
        return False


def status_note(saved: list[dict[str, Any]], ask: list[dict[str, Any]]) -> str:
    """One honest paragraph about what happened to what the person said: what is already saved, and what needs their OK and why it matters."""
    parts: list[str] = []
    if saved:
        names = event_policy.labels(saved)
        parts.append("I've saved " + _join(names) + " to your logs.")
    if ask:
        names = event_policy.labels(ask, asking=True)
        parts.append(f"{_join(names, cap=True)} need{'s' if len(names) == 1 and not names[0].endswith('s') else ''} your OK before I save "
                     f"{'it' if len(ask) == 1 else 'them'}: tap Save or Skip below.")
        if any((e.get("extracted_data") or {}).get("injury") for e in ask):
            parts.append(paragraph_extras.GUIDANCE)
        if any(str((e.get("extracted_data") or {}).get("name") or "").lower() in ("fever", "temperature") for e in ask):
            parts.append("A fever is worth watching: if it's high, lasts more than a couple of days, or comes with a stiff neck, a rash, trouble breathing or confusion, please see a clinician.")
    return " ".join(parts)


def _join(names: list[str], cap: bool = False) -> str:
    text = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return text[:1].upper() + text[1:] if cap else text
