"""Saved pattern notices: the associations Bubbles has found in a user's own logs, remembered over time.

association_insights.analyze() recomputes every link from scratch and forgets. This keeps one owner-scoped document per
link (doc_store kind ``pattern_notice``, key = the link id, e.g. ``sleep_hours->mood``), so Bubbles can say "something I
noticed" once, know when a pattern is new, has held up across both halves of the data, has reversed, or has faded, and
never nag about one the user dismissed. No schema change; "delete all my data" removes them like every other document.

Only the engine's derived wording and statistics are stored (never raw log values), and every notice keeps the engine's
own limits: an association in their logs, not a cause, not a diagnosis.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import doc_store

KIND = "pattern_notice"
#: a pattern must be missing from results for this long before it counts as faded (stops flapping at the threshold)
FADE_DAYS = 14
_KEEP = ("domains", "lag_days", "status", "strength", "direction", "n_days", "text")


def reconcile(previous: dict[str, dict[str, Any]], result: dict[str, Any], today: date) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Pure. previous: {link id: notice}. Returns (notices that changed, events). Event kinds:
    new | returned | stronger | reversed | faded. Dismissed notices are still kept up to date but never raise an event."""
    day = today.isoformat()
    changed: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in result.get("insights") or []:
        lid = str(item.get("id") or "")
        if not lid:
            continue
        seen.add(lid)
        old = previous.get(lid)
        note = {**(old or {}), **{k: item.get(k) for k in _KEEP}, "id": lid, "last_seen": day, "state": "active"}
        note.setdefault("first_seen", day)
        note.setdefault("dismissed", False)
        if old is None:
            kind = "new"
        elif old.get("state") == "faded":
            kind = "returned"
        elif old.get("direction") != item.get("direction"):
            kind = "reversed"
        elif old.get("status") != "repeated_pattern" and item.get("status") == "repeated_pattern":
            kind = "stronger"
        else:
            kind = None
        if kind:
            note["change"], note["changed_on"] = kind, day
        if note != old:
            changed[lid] = note
        if kind and not note["dismissed"]:
            events.append({"kind": kind, "id": lid, "text": note["text"]})
    cutoff = (today - timedelta(days=FADE_DAYS)).isoformat()
    for lid, old in previous.items():
        if lid in seen or old.get("state") == "faded" or str(old.get("last_seen", "")) > cutoff:
            continue
        changed[lid] = {**old, "state": "faded", "change": "faded", "changed_on": day}
        if not old.get("dismissed"):
            events.append({"kind": "faded", "id": lid, "text": old.get("text", "")})
    return changed, events


def _load(db: Any, uid: str) -> dict[str, dict[str, Any]]:
    return {str(d["key"]): d["payload"] for d in doc_store.list_docs(db, uid, KIND, limit=100)}


def save(db: Any, uid: str, result: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    """Remember what this analysis found; returns the events worth telling the user. Never raises: a failed save
    loses a notice, never a chat reply or an insights page."""
    try:
        changed, events = reconcile(_load(db, uid), result, today or date.today())
        for lid, note in changed.items():
            doc_store.put(db, uid, KIND, lid, note)
        return events
    except Exception:  # noqa: BLE001 - notices are a convenience on top of the analysis
        return []


def active(db: Any, uid: str) -> list[dict[str, Any]]:
    """Current, not-dismissed notices, repeated patterns first, then the most recently changed."""
    notes = [n for n in _load(db, uid).values() if n.get("state") == "active" and not n.get("dismissed")]
    notes.sort(key=lambda n: str(n.get("changed_on") or n.get("last_seen") or ""), reverse=True)
    return sorted(notes, key=lambda n: n.get("status") != "repeated_pattern")   # stable: newest first within each group


def dismiss(db: Any, uid: str, link_id: str) -> bool:
    """The user does not want to hear about this link again (it is still tracked, just never surfaced)."""
    note = _load(db, uid).get(link_id)
    if not note:
        return False
    doc_store.put(db, uid, KIND, link_id, {**note, "dismissed": True})
    return True
