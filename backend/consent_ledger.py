"""Thin adapter kept for the callers that grew around the first consent log (onboarding, partner sharing, phone reminders).

The one real ledger is ``consent`` (append-only, wording hash, policy version). Everything here delegates to it, so there is a single
source of truth and a single history, and a missing answer is still NOT granted.
"""
from __future__ import annotations

from typing import Any

import consent

PURPOSES = consent.PURPOSES
_cache = consent._cache   # the one cache (tests clear it)


def is_granted(db: Any, uid: str, purpose: str) -> bool:
    return consent.is_granted(db, uid, purpose)


def set_purpose(db: Any, uid: str, purpose: str, granted: bool, source: str = "settings") -> dict[str, Any]:
    """Record a yes or a withdrawal. A yes quotes the current wording (the caller's own switch is the in-context ask)."""
    pid = consent.canonical(purpose)
    if pid not in PURPOSES:
        raise KeyError(purpose)
    if granted and not PURPOSES[pid]["available"]:
        raise ValueError("not_available")
    state = consent.set_purpose(db, uid, pid, bool(granted), source=source, hash_seen=consent.text_hash(pid) if granted else None)
    return {"purpose": pid, "granted": bool(state.get("granted")), "decided_at": state.get("decided_at")}


def history(db: Any, uid: str, limit: int = 100) -> list[dict[str, Any]]:
    return [{**e, "at": e.get("created_at")} for e in consent.history(db, uid, limit)]


def forget(uid: str) -> None:
    consent.forget(uid)


def record_if_changed(db: Any, uid: str, purpose: str, granted: bool, source: str = "settings") -> None:
    """Log a choice made through an existing switch only when it differs from the recorded answer. Never raises."""
    try:
        if consent.is_granted(db, uid, purpose) != bool(granted):
            set_purpose(db, uid, purpose, granted, source)
    except Exception:  # noqa: BLE001 - the switch itself already worked; the log must never break it
        pass
