"""GET /nutrients/nudges: soft "might be worth a blood test" items and plain lab notes over the signed-in user's own data
(deficiency_map), plus chat_block() for the chat context.

Authenticated and owner-scoped (every read filters on the caller's uid), read-only, no new tables, no model. The computation never
leaves the server and nothing is stored, so it needs no consent of its own; the chat sentence only reaches an outside model on the
path that already required the `ai_chat_processing` yes (chat_block also re-checks it, so it is safe to call from anywhere).
Events must load (an error is an error, never an empty answer that looks like "nothing"); labs, conditions, medicines and
onboarding answers are best effort and named in ``unavailable`` when skipped. Under-18 profiles get nothing.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header

import deficiency_map as DM

EVENTS_TABLE = "extracted_health_events"
EVENT_LIMIT = 1000
TTL_SECONDS = 1800
_cache: dict[str, tuple[float, str]] = {}
_running: set[str] = set()
_lock = threading.Lock()


def load(db: Any, uid: str) -> dict[str, Any]:
    from calc_core import local_today
    from health_logs import DOMAINS, list_domain
    import doc_store
    unavailable: list[str] = []

    def optional(name: str, read: Callable[[], Any], empty: Any) -> Any:
        try:
            return read()
        except Exception:  # noqa: BLE001 - one missing source must not blank the rest
            unavailable.append(name)
            return empty

    today = local_today()
    onboarding = optional("answers", lambda: doc_store.get(db, uid, "onboarding", "v1") or {}, {})
    if onboarding.get("age_gate") == "under_18":
        return {"nudges": [], "lab_notes": [], "unavailable": [], "under_18": True}
    since = (datetime.now(timezone.utc) - timedelta(days=DM.WINDOW_DAYS + 90)).isoformat()
    events = (db.table(EVENTS_TABLE).select("id, event_type, extracted_data, confidence, created_at, user_confirmed, extraction_status")
              .eq("user_id", uid).gte("created_at", since).order("created_at", desc=True).limit(EVENT_LIMIT).execute().data or [])
    labs = optional("labs", lambda: list_domain(db, "labs", DOMAINS["labs"], uid, 730)["entries"], [])
    conds = optional("conditions", lambda: list_domain(db, "conditions", DOMAINS["conditions"], uid, 730)["entries"], [])
    meds = optional("medicines", lambda: list_domain(db, "medications", DOMAINS["medications"], uid, 730)["entries"], [])
    answers = onboarding.get("answers") if isinstance(onboarding.get("answers"), dict) else {}
    profile = {"labs": labs, "answers": answers, "meds": [m.get("name") for m in meds if isinstance(m, dict)],
               "conditions": [c.get("condition_name") for c in conds if isinstance(c, dict)]}
    res = DM.evaluate(DM.signals_from_rows(events, profile, today=today))
    return {**res, "unavailable": unavailable, "under_18": False}


def chat_block(db: Any, uid: str, consent_ok: Callable[[Any, str], bool] | None = None) -> str:
    """At most one sentence for the reply. Cached text now; otherwise warm the cache in the background and return "" (never waits)."""
    try:
        if consent_ok is None:
            from consent import is_granted
            consent_ok = lambda d, u: is_granted(d, u, "ai_chat_processing")  # noqa: E731
        if not uid or not consent_ok(db, uid):
            return ""
    except Exception:  # noqa: BLE001 - no clear yes means nothing leaves
        return ""
    with _lock:
        hit = _cache.get(uid)
        if hit and time.monotonic() - hit[0] < TTL_SECONDS:
            return hit[1]
        start = uid not in _running
        _running.add(uid)
    if start:
        threading.Thread(target=_warm, args=(db, uid), daemon=True).start()
    return ""


def _warm(db: Any, uid: str) -> None:
    text = ""
    try:
        res = load(db, uid)
        for n in res["nudges"]:
            if n["level"] == "medium" or n["signs"] >= DM.CHAT_MIN_SIGNS:
                text = "\n\n" + DM.hint_text(n)
                break
    except Exception:  # noqa: BLE001 - an extra for chat only
        pass
    with _lock:
        _cache[uid] = (time.monotonic(), text)
        _running.discard(uid)
        if len(_cache) > 2000:
            for k, _v in sorted(_cache.items(), key=lambda kv: kv[1][0])[:500]:
                _cache.pop(k, None)


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/nutrients/nudges")
    def nudges(authorization: str | None = Header(default=None)):
        uid = str(get_user(authorization).id)
        return {"status": "success", **load(db, uid)}

    return router
