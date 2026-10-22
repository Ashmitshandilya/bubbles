"""Export and delete the user's Whole-Health OS data (profile, plans, food/workout logs, cycle days, schedules, notifications).

Tracker entries (sleep, weight, ...) keep their own privacy endpoints; this covers the JSON documents stored through doc_store.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query
from starlette.concurrency import run_in_threadpool

import doc_store

EXPORT_LIMIT = 5000


MIRROR_DOMAINS = ("food_log",)       # analytics copies this feature wrote to extracted_health_events


def export_documents(db: Any, uid: str) -> list[dict]:
    rows = (db.table(doc_store.TABLE).select("*").eq("user_id", uid).eq("event_type", doc_store.EVENT_TYPE).order("event_date", desc=True).limit(EXPORT_LIMIT + 1).execute().data or [])
    return [{k: v for k, v in doc_store._unpack(r).items() if k not in ("id", "valid")} for r in rows if doc_store.row_is_valid(r)]


def delete_mirrors(db: Any, uid: str) -> int:
    """Remove the analytics copies of food-log entries so insights and AI context stop using them."""
    removed = 0
    for domain in MIRROR_DOMAINS:
        try:
            rows = (db.table("extracted_health_events").select("id").eq("user_id", uid).eq("extracted_data->_prov->>domain", domain).limit(2000).execute().data or [])
            for r in rows:
                db.table("extracted_health_events").delete().eq("id", r["id"]).eq("user_id", uid).execute()
                removed += 1
        except Exception:  # noqa: BLE001
            pass
    return removed


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/me/whole-health/export")
    def export(authorization: str | None = Header(default=None)):
        uid = str(get_user(authorization).id)
        docs = export_documents(db, uid)
        truncated = len(docs) > EXPORT_LIMIT
        docs = docs[:EXPORT_LIMIT]
        by_kind: dict[str, int] = {}
        for d in docs:
            by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
        try:
            import community_api
            community: dict | None = community_api.export_mine(db, uid)   # your own posts and comments only
        except Exception:  # noqa: BLE001 - said out loud below, never silently left out
            community = None
        return {"status": "success", "exported_at": datetime.now(timezone.utc).isoformat(), "count": len(docs), "truncated": truncated, "kinds": by_kind, "documents": docs,
                "community": community, "community_included": community is not None,
                "note": "Your tracker entries (sleep, weight, symptoms and so on) are separate and can be exported from their own pages."}

    @router.delete("/me/whole-health/data")
    async def delete_all(confirm: bool = Query(default=False), authorization: str | None = Header(default=None)):
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        if not confirm:
            raise HTTPException(status_code=422, detail="Add confirm=true to delete all of your Fitness, Cycle and plan data. This cannot be undone.")
        incomplete = None
        try:
            before = await run_in_threadpool(doc_store.delete_everything, db, uid)
        except doc_store.IncompleteDelete as e:   # everything else is gone; do not say "success"
            before, incomplete = e.removed, e
        mirrors = await run_in_threadpool(delete_mirrors, db, uid)
        if incomplete:
            raise HTTPException(status_code=503, detail="Most of your data was deleted, but some of your community posts could not be removed yet. Please try again in a minute.")
        return {"status": "success", "deleted": before, "analytics_copies_removed": mirrors,
                "note": ("Your tracker entries (sleep, weight, symptoms and so on) are separate and were not deleted. "
                         "If Bubbles recently paused a plan for your safety, that short safety hold stays in place so a strict plan cannot restart straight away.")}

    @router.delete("/me/account")
    async def delete_account(confirm: bool = Query(default=False), authorization: str | None = Header(default=None)):
        """Erases the person: every document (safety holds and community posts included), then the sign-in itself. Every table keyed by
        user_id is linked to auth.users on delete cascade, so removing the sign-in removes the rest. Nothing is claimed unless both steps worked."""
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        if not confirm:
            raise HTTPException(status_code=422, detail="Add confirm=true to delete your account and everything in it. This cannot be undone.")
        try:
            await run_in_threadpool(doc_store.delete_everything, db, uid, ())
        except doc_store.IncompleteDelete:
            raise HTTPException(status_code=503, detail="Your account was not deleted because some of your community posts could not be removed yet. Please try again in a minute.")
        await run_in_threadpool(delete_mirrors, db, uid)
        try:
            await run_in_threadpool(db.auth.admin.delete_user, uid)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=503, detail="Your data was deleted but the sign-in could not be removed yet. Please try again in a minute.")
        import ttl_cache
        ttl_cache.clear_all()   # a cached sign-in must not keep answering for a person who no longer exists
        return {"status": "success", "deleted": True}

    return router
