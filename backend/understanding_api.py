"""How Bubbles understands you: ``app.include_router(understanding_api.build_router(get_user, db))``.

GET    /me/understanding            what Bubbles has learned, as plain sentences with the reason and a word for how sure it is
PUT    /me/understanding/{trait}    {"action": "confirm" | "reject"}  ("That's me" / "Not me")
DELETE /me/understanding            wipe the whole model (rejections too)

Reads and writes only the signed ``person_model`` document of the signed-in person (person_model.py). Nothing here quotes a chat message.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException
from starlette.concurrency import run_in_threadpool

import person_model as pm

INTRO_EMPTY = "Bubbles is still getting to know you."


def _view(model: dict[str, Any], now: datetime) -> dict[str, Any]:
    traits = pm.understanding(model, now)
    out: dict[str, Any] = {"status": "success", "traits": traits, "empty": not traits}
    if not traits:
        # what it would use, so an empty page still says what this is for
        out["intro"] = INTRO_EMPTY
        out["would_use"] = [spec["learns"] for tid, spec in pm.TRAITS.items() if tid not in model["rejected"] and tid in _VISIBLE_WHEN_EMPTY]
    return out


#: the traits that are learned today (the others are filled in by Orbit and the Stars lens later)
_VISIBLE_WHEN_EMPTY = ("reply_length", "tone", "language_mix", "active_time", "stress_response")


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def uid_of(authorization: str | None) -> str:
        return str((await run_in_threadpool(get_user, authorization)).id)

    @router.get("/me/understanding")
    async def read(authorization: str | None = Header(default=None)):
        uid = await uid_of(authorization)
        model = await run_in_threadpool(pm.load, db, uid)
        return _view(model, datetime.now(timezone.utc))

    @router.put("/me/understanding/{trait}")
    async def answer(trait: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
        uid = await uid_of(authorization)
        action = payload.get("action") if isinstance(payload, dict) else None
        if trait not in pm.TRAITS:
            raise HTTPException(status_code=404, detail="Unknown trait")
        if action not in ("confirm", "reject"):
            raise HTTPException(status_code=422, detail="action must be 'confirm' or 'reject'")
        now = datetime.now(timezone.utc)

        def change() -> dict[str, Any]:
            model = pm.load(db, uid, fresh=True)
            if action == "reject":
                pm.reject(model, trait)
            elif not pm.confirm(model, trait, now):
                raise HTTPException(status_code=404, detail="Bubbles has not learned that about you")
            pm.save(db, uid, model)
            return model

        return _view(await run_in_threadpool(change), now)

    @router.delete("/me/understanding")
    async def wipe(authorization: str | None = Header(default=None)):
        uid = await uid_of(authorization)
        await run_in_threadpool(pm.wipe, db, uid)
        return _view(pm.new_model(), datetime.now(timezone.utc))

    return router
