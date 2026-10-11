"""Consent to send a conversation to an outside AI model.

Bubbles understands emergencies, corrections, daily logs and fitness questions on its own servers. Only the open-ended replies go to an
outside AI model (a free provider), and what is sent is the person's message, their recent messages in that chat and a short summary
of their profile and notes (context_engine.format_user_context: name, date of birth, gender, timezone, recent entries, patterns). That needs a clear
yes first. The yes is stored per person (signed document, no schema change), can be withdrawn at any time, and is checked on the server
before any message leaves it. Emergency handling never depends on it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import doc_store

KIND = "consent"
KEY = "ai_chat"
VERSION = "2026-10b"   # b: the ask now names the profile details that are sent too (date of birth, gender)
"""Bump this when what is sent, or to whom, changes: everyone is then asked again."""


def state(db: Any, uid: str) -> dict:
    doc = doc_store.get(db, uid, KIND, KEY) or {}
    accepted = bool(doc.get("accepted")) and doc.get("version") == VERSION
    return {"ai_chat": accepted, "version": VERSION, "decided_at": doc.get("at") if doc else None}


def has_ai_consent(db: Any, uid: str) -> bool:
    try:
        return state(db, uid)["ai_chat"]
    except Exception:  # noqa: BLE001 - if consent cannot be read, nothing leaves the server
        return False


def set_ai_chat(db: Any, uid: str, accepted: bool) -> dict:
    doc_store.put(db, uid, KIND, KEY, {"accepted": bool(accepted), "version": VERSION, "at": datetime.now(timezone.utc).isoformat()})
    return state(db, uid)


def consent_needed_reply(name: str | None = None) -> str:
    who = f"{name}, to" if name else "To"
    return (
        f"{who} answer this I'd use an outside AI model. It would get your message, your recent messages here and a short summary "
        "of your profile and notes (such as your date of birth, gender and recent entries). Nothing is sent unless you say yes, "
        "and you can change it any time in Settings.\n\n"
        "Without it I can still log things and answer questions about your cycle, sleep and fitness. "
        "If something feels urgent, call your local emergency number."
    )
