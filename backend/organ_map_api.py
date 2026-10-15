"""GET /organs/map and GET /organs/{organ_id}: the organ map (organ_map_engine) over the signed-in user's own data.

Authenticated and owner-scoped: every read filters on the caller's user id. Read-only, no new tables. The window is
bounded (clinical_constants.ORGAN_WINDOW_DAYS, 7 to 180 days, default 30). Inputs:

    extracted_health_events   tracker saves are mirrored here, chat observations live here (window-limited)
    labs, conditions          the tracker domains, full history (a thyroid result from last year still counts)
    cycle                     cycle_api's own state and flags (phase, heavy-bleeding and other clinician prompts)

The events read must succeed (a failure is an error, never an empty map that looks like "no data"). Labs, conditions and
cycle are best effort: if one cannot be read the map still renders and ``unavailable`` names what was skipped.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query

import clinical_constants as K
from organ_map_engine import ORGANS, build_organ_map

EVENTS_TABLE = "extracted_health_events"
EVENT_LIMIT = 1000  # ponytail: newest 1000 events in the window; page through them if heavy loggers hit the cap
LO, HI = K.ORGAN_WINDOW_DAYS


def _cycle(db: Any, uid: str, today) -> dict:
    from cycle_api import _context
    from cycle_flags import compute_flags
    ctx = _context(db, uid, today)
    state = ctx["state"]
    return {"phase": state.get("phase"), "cycle_day": state.get("cycle_day"), "flags": compute_flags(state, ctx["logs"])}


def load_organ_map(db: Any, uid: str, days: int) -> dict:
    from calc_core import local_today
    from health_logs import DOMAINS, list_domain
    today = local_today()
    since = (datetime.now(timezone.utc) - timedelta(days=days + 1)).isoformat()
    events = (db.table(EVENTS_TABLE)
              .select("id, event_type, extracted_data, confidence, created_at, user_confirmed, extraction_status")
              .eq("user_id", uid).gte("created_at", since).order("created_at", desc=True).limit(EVENT_LIMIT)
              .execute().data or [])
    unavailable: list[str] = []

    def optional(name: str, read: Callable[[], Any], empty: Any) -> Any:
        try:
            return read()
        except Exception as exc:  # noqa: BLE001 - one missing source must not blank the whole map
            unavailable.append(name)
            try:
                from logging_util import logger
                logger.warning(component="ORGAN_MAP", operation=f"load_{name}", error=exc, fallback_action="skipped_source")
            except Exception:  # noqa: BLE001
                pass
            return empty

    labs = optional("labs", lambda: list_domain(db, "labs", DOMAINS["labs"], uid, 730)["entries"], [])
    conditions = optional("conditions", lambda: list_domain(db, "conditions", DOMAINS["conditions"], uid, 730)["entries"], [])
    cycle = optional("cycle", lambda: _cycle(db, uid, today), None)
    def setup_body() -> str | None:
        import doc_store
        doc = doc_store.get(db, uid, "experience", "main") or {}
        value = (doc.get("body_map") or {}).get("reproductive") if isinstance(doc.get("body_map"), dict) else None
        return value if value in ("uterus_ovaries", "none") else None

    reproductive = optional("setup", setup_body, None)
    result = build_organ_map(events, labs=labs, conditions=conditions, cycle=cycle, today=today, window_days=days, reproductive=reproductive)
    result["unavailable"] = unavailable
    return result


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/organs/map")
    def organ_map(days: int = Query(default=K.ORGAN_WINDOW_DEFAULT_DAYS, ge=LO, le=HI), authorization: str | None = Header(default=None)):
        uid = str(get_user(authorization).id)
        return {"status": "success", **load_organ_map(db, uid, days)}

    @router.get("/organs/{organ_id}")
    def organ_detail(organ_id: str, days: int = Query(default=K.ORGAN_WINDOW_DEFAULT_DAYS, ge=LO, le=HI),
                     authorization: str | None = Header(default=None)):
        uid = str(get_user(authorization).id)
        if organ_id not in ORGANS:
            raise HTTPException(status_code=404, detail="Unknown organ. Use one of: " + ", ".join(ORGANS))
        result = load_organ_map(db, uid, days)
        organ = next((o for o in result.pop("organs") if o["organ_id"] == organ_id), None)
        if organ is None:  # an opt-in area (uterus and ovaries) for someone who has not used it
            raise HTTPException(status_code=404, detail="This area shows once you use Cycle or log something about it.")
        result.pop("counts")
        return {"status": "success", **result, "organ": organ}

    return router
