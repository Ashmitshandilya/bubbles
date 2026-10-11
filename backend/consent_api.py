"""GET and PUT /me/consent: read and change the consent to use an outside AI model (see consent.py)."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import consent


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def uid_of(authorization: str | None) -> str:
        user = await run_in_threadpool(get_user, authorization)
        return str(user.id)

    @router.get("/me/consent")
    async def read_consent(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", **await run_in_threadpool(consent.state, db, uid)}

    @router.put("/me/consent")
    async def change_consent(request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict) or not isinstance(body.get("ai_chat"), bool):
            raise HTTPException(status_code=422, detail="ai_chat must be true or false")
        return {"status": "success", **await run_in_threadpool(consent.set_ai_chat, db, uid, body["ai_chat"])}

    return router
