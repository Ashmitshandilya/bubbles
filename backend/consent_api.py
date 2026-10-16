"""Consent: GET/PUT /me/consent (the AI choice, kept for older clients) and the granular choices GET /consents, GET /consents/history,
PUT /consents/{purpose} (see consent_ledger.py)."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import consent
import consent_ledger as ledger


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
            raise HTTPException(status_code=422, detail="Request body must be an object")
        return body

    @router.get("/me/consent")
    async def read_consent(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", **await run_in_threadpool(consent.state, db, uid)}

    @router.put("/me/consent")
    async def change_consent(request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        body = await body_of(request)
        if not isinstance(body.get("ai_chat"), bool):
            raise HTTPException(status_code=422, detail="ai_chat must be true or false")
        await run_in_threadpool(ledger.set_purpose, db, uid, "ai_chat_processing", body["ai_chat"], "settings")
        return {"status": "success", **await run_in_threadpool(consent.state, db, uid)}

    @router.get("/consents")
    async def list_consents(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", "consents": await run_in_threadpool(ledger.state, db, uid)}

    @router.get("/consents/history")
    async def consent_history(authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        return {"status": "success", "history": await run_in_threadpool(ledger.history, db, uid)}

    @router.put("/consents/{purpose}")
    async def change_purpose(purpose: str, request: Request, authorization: str | None = Header(None)):
        uid = await uid_of(authorization)
        body = await body_of(request)
        if not isinstance(body.get("granted"), bool):
            raise HTTPException(status_code=422, detail="granted must be true or false")
        try:
            result = await run_in_threadpool(ledger.set_purpose, db, uid, purpose, body["granted"], str(body.get("source") or "settings"))
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown choice")
        except ValueError:
            raise HTTPException(status_code=409, detail="This choice is not available yet")
        return {"status": "success", **result}

    return router
