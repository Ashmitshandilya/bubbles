"""Consent to send a conversation to an outside AI model.

Bubbles understands emergencies, corrections, daily logs and fitness questions on its own servers. Only the open-ended replies go to an
outside AI model (a free provider), and what is sent is the person's message plus a short summary of their own notes. That needs a clear
yes first. The yes is stored per person (signed document, no schema change), can be withdrawn at any time, and is checked on the server
before any message leaves it. Emergency handling never depends on it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import doc_store

KIND = "consent"
KEY = "ai_chat"
VERSION = "2026-10"
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
    who = f"{name}, " if name else ""
    return (
        f"{who}I can answer open questions with the help of an outside AI model. To do that I would send your message, your recent messages in "
        "this chat and a short summary of your own notes to that model. I will not send anything unless you say yes, and you can take it back any time in Settings.\n\n"
        "Without it I can still save what you log, show your patterns and answer questions about your cycle, sleep and fitness. "
        "If something feels urgent, contact a clinician or your local emergency number."
    )
