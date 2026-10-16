"""Consent routes: GET /consents, GET /consents/history, PUT /consents/{purpose}, POST /consents/acknowledgements, and the older
GET / PUT /me/consent (a shim for ai_chat_processing). The logic and the wording live in consent.py."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

import consent


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def uid_of(authorization: str | None) -> str:
        user = await run_in_threadpool(get_user, authorization)
        return str(user.id)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        return body

    async def run(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            return await run_in_threadpool(lambda: fn(*args, **kwargs))
        except consent.ConsentError as error:
            raise HTTPException(status_code=error.status, detail=error.detail)

    # ---- one row per purpose, with a history ----------------------------------------------------------------------------

    @router.get("/consents")
    async def list_consents(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", **await run(consent.overview, db, uid)}

    @router.get("/consents/history")
    async def consent_history(limit: int = Query(100, ge=1, le=500), authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", "events": await run(consent.history, db, uid, limit)}

    @router.put("/consents/{purpose}")
    async def change_consent_purpose(purpose: str, request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        body = await body_of(request)
        granted, source, seen = body.get("granted"), body.get("source", "settings"), body.get("text_hash")
        if not isinstance(granted, bool):
            raise HTTPException(status_code=422, detail="granted must be true or false")
        if not isinstance(source, str) or not isinstance(seen, (str, type(None))):
            raise HTTPException(status_code=422, detail="source and text_hash must be text")
        state = await run(consent.set_purpose, db, uid, purpose, granted, source=source, hash_seen=seen)
        return {"status": "success", "consent": state}

    @router.post("/consents/acknowledgements")
    async def acknowledge(request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        body = await body_of(request)
        version = body.get("version")
        if not isinstance(version, str):
            raise HTTPException(status_code=422, detail="version must be text")
        return {"status": "success", **await run(consent.acknowledge, db, uid, version, source="signup")}

    # ---- the older single switch ------------------------------------------------------------------------------------------

    @router.get("/me/consent")
    async def read_consent(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", **await run(consent.state, db, uid)}

    @router.put("/me/consent")
    async def change_consent(request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        body = await body_of(request)
        if not isinstance(body.get("ai_chat"), bool):
            raise HTTPException(status_code=422, detail="ai_chat must be true or false")
        return {"status": "success", **await run(consent.set_ai_chat, db, uid, body["ai_chat"])}

    return router
