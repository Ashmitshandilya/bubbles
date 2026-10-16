"""GET /insights/{insight_id}: the detail behind one pattern, link or Today item.

Ids are the stable ones the list endpoints already send: rec:<type>:<subject> (a repeated item), co:<a>|<b> (two things
close together) and <x>-><y> (a link between two logged series, from the association engine). The answer is rebuilt from the
signed-in person's own events inside a bounded window, so an id that no longer shows up is a plain 404, never someone else's
data. Only ISO days, counts and the engine's own wording are returned: no free text from entries.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query
from starlette.concurrency import run_in_threadpool

import association_loader
import pattern_engine

MAX_ID = 120


def _events(db: Any, uid: str, days: int) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        db.table("extracted_health_events")
        .select("id, event_type, extracted_data, confidence, created_at, user_confirmed, extraction_status")
        .eq("user_id", uid)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(1000)
        .execute()
    )
    return list(result.data or [])


def _detail(item: dict[str, Any], kind: str, days: int, drop: tuple[str, ...] = ("source_event_ids",)) -> dict[str, Any]:
    """The engine's own item (the same shape the list endpoints send), plus its kind and the window it was found in."""
    return {**{k: v for k, v in item.items() if k not in drop}, "kind": kind, "window_days": days}


def find_detail(db: Any, uid: str, insight_id: str, days: int) -> dict[str, Any] | None:
    if "->" in insight_id:
        found = next((i for i in association_loader.get(db, uid, 90).get("insights", []) if i.get("id") == insight_id), None)
        return _detail(found, "association", 90) if found else None
    if not insight_id.startswith(("rec:", "co:")):
        return None
    analysis = pattern_engine.analyze(_events(db, uid, days), days=days)
    if insight_id.startswith("rec:"):
        found = next((p for p in analysis["patterns"] if p["id"] == insight_id), None)
        return _detail(found, "pattern", days) if found else None
    found = next((c for c in analysis["correlations"] if c["id"] == insight_id), None)
    return _detail(found, "correlation", days) if found else None


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/insights/{insight_id}")
    async def insight_detail(insight_id: str, days: int = Query(default=30, ge=7, le=365), authorization: str | None = Header(None)):
        user = await run_in_threadpool(get_user, authorization)
        if not insight_id or len(insight_id) > MAX_ID:
            raise HTTPException(status_code=404, detail="Insight not found")
        detail = await run_in_threadpool(find_detail, db, str(user.id), insight_id, days)
        if detail is None:
            raise HTTPException(status_code=404, detail="Insight not found")
        return {"status": "success", "insight": detail}

    return router
