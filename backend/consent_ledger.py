"""Granular consent with a log: one switch per purpose, everything off until the person turns it on, every change written down.

Purposes are separate on purpose (nothing is bundled and nothing is pre-ticked). The current answer per purpose is a signed document
(``consent`` / ``<purpose>``; the AI purpose keeps its old key ``ai_chat`` so nothing already granted is lost) and every change also
appends one ``consent_event`` document: purpose, granted or withdrawn, wording version, where it was changed. No free text is stored.
The trail is kept when "delete all my data" runs (doc_store keeps ``consent_event``). A missing answer means NOT granted, and a
purpose that is not offered yet (``available`` false) can never be granted.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

import consent as ai_consent
import doc_store
from ttl_cache import TTLCache

EVENT_KIND = "consent_event"
SOURCES = ("settings", "chat_card", "onboarding", "system")

# id -> what the person sees. `version` changes when the wording or what is shared changes (everyone is asked again).
PURPOSES: dict[str, dict[str, Any]] = {
    "ai_chat_processing": {
        "title": "Outside AI for open questions", "version": ai_consent.VERSION, "available": True,
        "what": "Your message, recent chat and a short summary of your profile and entries go to an outside AI to write its answer. Off: nothing is sent.",
    },
    "health_memory_from_chat": {
        "title": "Save details I notice in chat", "version": "2026-10a", "available": True,
        "what": "Bubbles suggests saving health details it notices in your chat (like a headache or your sleep). You confirm each one. Off: nothing is picked out of chat.",
    },
    "partner_sharing": {
        "title": "Partner sharing", "version": "2026-10a", "available": True,
        "what": "Lets you choose what a partner can see. Off: nothing is shared, whatever was set before.",
    },
    "email_reminders": {
        "title": "Reminders by email", "version": "2026-10a", "available": True,
        "what": "Sends plain reminders (no health details) to your sign-in email. Off: reminders stay inside the app.",
    },
    "push_notifications": {
        "title": "Reminders on your phone", "version": "2026-10a", "available": False,
        "what": "Plain reminders (no health details) as phone notifications in the Android app. Coming soon.",
    },
    "community_visibility": {
        "title": "Community", "version": "2026-10a", "available": False,
        "what": "Lets you post and answer in the community, with a name or anonymously. Coming soon.",
    },
    "product_usage_metrics": {
        "title": "Usage counts to improve Bubbles", "version": "2026-10a", "available": False,
        "what": "Anonymous counts of which features are used, never your messages or health details. Not collected today.",
    },
}

_cache = TTLCache("consent_ledger", ttl_s=300, max_entries=20000)


def _key(purpose: str) -> str:
    return "ai_chat" if purpose == "ai_chat_processing" else purpose


def _check(purpose: str) -> dict[str, Any]:
    if purpose not in PURPOSES:
        raise KeyError(purpose)
    return PURPOSES[purpose]


def _read(db: Any, uid: str, purpose: str) -> tuple[bool, str | None]:
    meta = _check(purpose)
    doc = doc_store.get(db, uid, ai_consent.KIND, _key(purpose)) or {}
    granted = bool(doc.get("accepted")) and doc.get("version") == meta["version"] and meta["available"]
    return granted, doc.get("at")


def is_granted(db: Any, uid: str, purpose: str) -> bool:
    """True only for a recorded, current yes. Anything unreadable is a no (nothing is processed on a guess)."""
    try:
        _check(purpose)
        if purpose == "ai_chat_processing":
            return ai_consent.has_ai_consent(db, uid)
        return _cache.get_or_compute((uid, purpose), lambda: _read(db, uid, purpose)[0])
    except Exception:  # noqa: BLE001
        return False


def state(db: Any, uid: str) -> list[dict[str, Any]]:
    out = []
    for purpose, meta in PURPOSES.items():
        granted, at = _read(db, uid, purpose)
        out.append({"purpose": purpose, "title": meta["title"], "what": meta["what"], "available": meta["available"],
                    "version": meta["version"], "granted": granted, "decided_at": at})
    return out


def set_purpose(db: Any, uid: str, purpose: str, granted: bool, source: str = "settings") -> dict[str, Any]:
    """Record a yes or a withdrawal (and log it). Raises KeyError for an unknown purpose, ValueError for one not offered yet."""
    meta = _check(purpose)
    if granted and not meta["available"]:
        raise ValueError("not_available")
    source = source if source in SOURCES else "settings"
    now = datetime.now(timezone.utc).isoformat()
    _cache.invalidate((uid, purpose))
    try:
        if purpose == "ai_chat_processing":
            ai_consent.set_ai_chat(db, uid, granted)
        else:
            doc_store.put(db, uid, ai_consent.KIND, _key(purpose), {"accepted": bool(granted), "version": meta["version"], "at": now})
        doc_store.put(db, uid, EVENT_KIND, f"{purpose}:{now}:{secrets.token_hex(3)}",
                      {"purpose": purpose, "granted": bool(granted), "version": meta["version"], "source": source, "at": now})
    finally:
        _cache.invalidate((uid, purpose))
    granted_now, at = _read(db, uid, purpose)
    return {"purpose": purpose, "granted": granted_now, "decided_at": at}


def history(db: Any, uid: str, limit: int = 100) -> list[dict[str, Any]]:
    docs = doc_store.list_docs(db, uid, EVENT_KIND, limit=limit)
    rows = []
    for d in docs:
        p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        if p.get("purpose") in PURPOSES:
            rows.append({"purpose": p["purpose"], "title": PURPOSES[p["purpose"]]["title"], "granted": bool(p.get("granted")),
                         "source": p.get("source"), "at": p.get("at")})
    return sorted(rows, key=lambda r: str(r["at"]), reverse=True)


def forget(uid: str) -> None:
    for purpose in PURPOSES:
        _cache.invalidate((uid, purpose))


def record_if_changed(db: Any, uid: str, purpose: str, granted: bool, source: str = "settings") -> None:
    """Log a choice made through an existing switch (reminder email, partner sharing) only when it differs from the recorded answer. Never raises."""
    try:
        if _read(db, uid, purpose)[0] != bool(granted):
            set_purpose(db, uid, purpose, granted, source)
    except Exception:  # noqa: BLE001 - the switch itself already worked; the log must never break it
        pass
