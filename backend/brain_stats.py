"""What Bubbles learns about its own answers, per person: which kinds of local answer helped and which missed (a thumbs up or down).

The person's own signed ``brain_stats`` document holds small counts keyed by "route:intent" (for example ``own_data:sleep.summary``). When a kind keeps
missing for a person (at least two thumbs down, and at least twice as many as thumbs up), Bubbles stops answering that kind itself for them and hands
it to the model (with their consent) instead; a kind that keeps helping stays local. Counts only: no message text is ever stored here.
"""
from __future__ import annotations

from typing import Any

import doc_store
from ttl_cache import TTLCache

KIND, KEY = "brain_stats", "v1"
MAX_KEYS = 80
MIN_DOWN = 2
KIND_MIN_DOWN = 4

_cache = TTLCache("brain_stats", ttl_s=60, max_entries=2000)   # one entry per person: holds only that person's own counts


def _empty() -> dict[str, Any]:
    return {"counts": {}}


def load(db: Any, uid: str) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        try:
            doc = doc_store.get(db, uid, KIND, KEY)
        except Exception:  # noqa: BLE001 - no stats just means no deferral
            return _empty()
        return doc if isinstance(doc, dict) and isinstance(doc.get("counts"), dict) else _empty()
    return _cache.get_or_compute(uid, read)


def _misses(counts: dict[str, int] | None, min_down: int) -> bool:
    up, down = int((counts or {}).get("up", 0)), int((counts or {}).get("down", 0))
    return down >= min_down and down >= 2 * up


def deferred(db: Any, uid: str, key: str) -> bool:
    """True when this kind of local answer keeps missing for this person, so the model should handle it for them."""
    counts = load(db, uid)["counts"]
    group = key.split(":", 1)[0]
    group_up = sum(int(v.get("up", 0)) for k, v in counts.items() if k.split(":", 1)[0] == group)
    group_down = sum(int(v.get("down", 0)) for k, v in counts.items() if k.split(":", 1)[0] == group)
    return _misses(counts.get(key), MIN_DOWN) or _misses({"up": group_up, "down": group_down}, KIND_MIN_DOWN)


def record(db: Any, uid: str, key: str, rating: str) -> bool:
    """Count one thumbs on a local answer. Never raises."""
    if rating not in ("up", "down") or ":" not in key or len(key) > 60:
        return False
    try:
        doc = doc_store.get(db, uid, KIND, KEY)
        counts = dict(doc["counts"]) if isinstance(doc, dict) and isinstance(doc.get("counts"), dict) else {}
        row = dict(counts.get(key) or {"up": 0, "down": 0})
        row[rating] = int(row.get(rating, 0)) + 1
        counts[key] = row
        while len(counts) > MAX_KEYS:
            counts.pop(next(iter(counts)))   # the oldest kind goes first
        doc_store.put(db, uid, KIND, KEY, {"counts": counts})
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        _cache.invalidate(uid)


def from_feedback(db: Any, uid: str, message_id: str, rating: str) -> bool:
    """After a thumbs on a Bubbles reply: when that reply was one of Bubbles' own local answers (the kind is stored with it), count it."""
    try:
        rows = db.table("chat_messages").select("metadata").eq("id", message_id).eq("user_id", uid).limit(1).execute().data or []
        brain = ((rows[0].get("metadata") or {}) if rows else {}).get("brain")
        key = brain.get("key") if isinstance(brain, dict) else None
        return bool(key) and record(db, uid, str(key), rating)
    except Exception:  # noqa: BLE001
        return False


def summary(db: Any, uid: str) -> dict[str, dict[str, int]]:
    """The person's counts, for the "How Bubbles understands you" screen later."""
    return {k: {"up": int(v.get("up", 0)), "down": int(v.get("down", 0))} for k, v in load(db, uid)["counts"].items()}
