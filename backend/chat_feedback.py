"""Thumbs up/down on Bubbles replies: ``app.include_router(chat_feedback.build_router(get_user, db))``.

One signed document per rated reply (kind ``chat_feedback``, key = the reply's message id) through ``doc_store``, so there is no
schema change. Only a fixed set of reasons is stored: never free text, never the reply itself. A rating can only be placed on a
Bubbles reply that belongs to the signed-in user, and the latest rating replaces the earlier one.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

import doc_store
import person_model
import brain_stats
import playbook

KIND = "chat_feedback"
RATINGS = ("up", "down")
REASONS = ("unclear", "not_helpful", "too_long", "worried_me", "other")
MAX_IDS = 50
BUBBLES_ROLES = ("bubbles", "assistant")


def valid_id(value: Any) -> str | None:
    """The canonical lower-case UUID text for a reply id, or None. chat_messages.id is a uuid column, so anything else cannot exist."""
    if not isinstance(value, str) or len(value) > 36:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def uid_of(authorization: str | None) -> str:
        user = await run_in_threadpool(get_user, authorization)
        return str(user.id)

    def owns_reply(uid: str, message_id: str) -> bool:
        rows = (db.table("chat_messages").select("id,role").eq("id", message_id).eq("user_id", uid).limit(1).execute().data or [])
        return bool(rows) and str(rows[0].get("role", "")).lower() in BUBBLES_ROLES

    def reply_words(uid: str, message_id: str) -> int:
        rows = (db.table("chat_messages").select("content").eq("id", message_id).eq("user_id", uid).limit(1).execute().data or [])
        return len(str(rows[0].get("content") or "").split()) if rows else 0

    @router.post("/chat/feedback", status_code=201)
    async def rate_reply(request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        message_id, rating, reason = body.get("message_id"), body.get("rating"), body.get("reason")
        message_id = valid_id(message_id)
        if message_id is None:
            raise HTTPException(status_code=422, detail="message_id is invalid")
        if rating not in RATINGS:
            raise HTTPException(status_code=422, detail="rating must be 'up' or 'down'")
        if reason is not None and reason not in REASONS:
            raise HTTPException(status_code=422, detail="reason is not one of the allowed choices")
        if rating == "up":
            reason = None
        if not await run_in_threadpool(owns_reply, uid, message_id):
            raise HTTPException(status_code=404, detail="That reply was not found")
        payload = {"rating": rating, "reason": reason, "at": datetime.now(timezone.utc).isoformat()}
        await run_in_threadpool(doc_store.put, db, uid, KIND, message_id, payload)
        await run_in_threadpool(person_model.observe_feedback, db, uid, rating, reason)   # never raises; "too long" twice becomes a trait
        if rating == "up":
            try:
                await run_in_threadpool(lambda: person_model.observe_liked(db, uid, reply_words(uid, message_id)))   # a word count only, never the text
            except Exception:  # noqa: BLE001 - learning is best effort
                pass
        await run_in_threadpool(brain_stats.from_feedback, db, uid, message_id, rating)   # never raises; counts a thumbs on one of Bubbles' own local answers
        await run_in_threadpool(playbook.capture_from_feedback, db, uid, message_id, rating)   # never raises; needs a yes and a plain app question
        return {"status": "success", "message_id": message_id, "rating": rating, "reason": reason}

    @router.get("/chat/feedback")
    async def my_ratings(message_ids: str = Query("", max_length=4000), authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        wanted = list(dict.fromkeys(m for m in (valid_id(part.strip()) for part in message_ids.split(",")) if m))[:MAX_IDS]
        docs = await run_in_threadpool(doc_store.get_many, db, uid, KIND, wanted)   # one read for all of them (was one per id)
        ratings = {m: {"rating": d["rating"], "reason": d.get("reason")} for m, d in docs.items() if d.get("rating") in RATINGS}
        return {"status": "success", "ratings": ratings}

    return router
