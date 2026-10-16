"""Builds the inputs for deficiency_map.nudges() from the person's own data, with a short per-user cache.

Sources, all optional (a missing one is simply absent, never "fine"): symptom logs and their notes, their last chat messages (read by
the same language layer as chat, only to count days), the setup answers (eating style, body, birth date, periods) and lab results.
Nothing is sent to a model from here except one hedged sentence that chat_block() may add."""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from typing import Any

import deficiency_map as D
import doc_store
import health_semantics as H
from health_logs import DOMAINS, list_domain

TTL_SECONDS = 1800
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_running: set[str] = set()
_lock = threading.Lock()


def _day(value: Any) -> str | None:
    return str(value)[:10] if value else None


def _concept_days(db: Any, uid: str, days: int) -> dict[str, int]:
    seen: dict[str, set[str]] = {}

    def add(text: Any, when: Any) -> None:
        d = _day(when)
        if not d or not isinstance(text, str) or not text.strip():
            return
        for f in H.analyze(text):
            if f.experiencer == "self" and f.assertion == "present":
                seen.setdefault(f.concept, set()).add(d)

    try:
        for e in list_domain(db, "symptoms", DOMAINS["symptoms"], uid, days)["entries"]:
            add(f"I have {e.get('symptom') or ''}. {e.get('notes') or ''}", e.get("date"))
    except Exception:  # noqa: BLE001 - an unreadable source is just absent
        pass
    try:
        rows = (db.table("chat_messages").select("content,created_at").eq("user_id", uid).eq("role", "user")
                .order("created_at", desc=True).limit(60).execute().data or [])
        for r in rows:
            add(r.get("content"), r.get("created_at"))
    except Exception:  # noqa: BLE001
        pass
    return {c: len(ds) for c, ds in seen.items()}


def _profile(db: Any, uid: str, today: date) -> dict[str, Any]:
    p: dict[str, Any] = {}
    try:
        import onboarding as ob
        a = (doc_store.get(db, uid, "onboarding", "v1") or {}).get("answers") or {}
        p["diet"] = a.get("diet_style")
        p["body"] = ob.body_of(a)
        p["age"] = ob.age_on(a.get("birth_date"), today)
        p["irregular_periods"] = a.get("periods") == "irregular"
        p["pregnancy"] = a.get("periods_reason") == "pregnant"
    except Exception:  # noqa: BLE001
        pass
    return p


def compute(db: Any, uid: str, days: int = 90) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    profile = _profile(db, uid, today)
    concepts = _concept_days(db, uid, days)
    profile["concepts"] = concepts
    profile["heavy_periods"] = concepts.get("heavy_bleeding", 0) >= 1
    try:
        labs = list_domain(db, "labs", DOMAINS["labs"], uid, 730)["entries"]
    except Exception:  # noqa: BLE001
        labs = []
    result = D.nudges(profile, labs)
    result["window_days"] = days
    with _lock:
        _cache[uid] = (time.monotonic(), result)
    return result


def cached(uid: str) -> dict[str, Any] | None:
    with _lock:
        hit = _cache.get(uid)
    return hit[1] if hit and time.monotonic() - hit[0] < TTL_SECONDS else None


def get(db: Any, uid: str, refresh: bool = False) -> dict[str, Any]:
    return (None if refresh else cached(uid)) or compute(db, uid)


def invalidate(uid: str) -> None:
    with _lock:
        _cache.pop(uid, None)


def _bg(db: Any, uid: str) -> None:
    try:
        compute(db, uid)
    except Exception:  # noqa: BLE001
        pass
    finally:
        with _lock:
            _running.discard(uid)


def chat_block(db: Any, uid: str) -> str:
    """At most one hedged sentence. Never waits: a cold cache is warmed in the background for the next message."""
    result = cached(uid)
    if result is None:
        with _lock:
            start = uid not in _running
            _running.add(uid)
        if start:
            threading.Thread(target=_bg, args=(db, uid), daemon=True).start()
        return ""
    line = D.chat_sentence(result)
    return f"\n\n{line}" if line else ""
