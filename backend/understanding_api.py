"""How Bubbles understands you: ``app.include_router(understanding_api.build_router(get_user, db))``.

GET    /me/understanding            what Bubbles has learned, as plain sentences with the reason and a word for how sure it is
PUT    /me/understanding/{trait}    {"action": "confirm" | "reject"}  ("That's me" / "Not me")
DELETE /me/understanding            wipe the whole model (rejections too)

Reads and writes only the signed ``person_model`` document of the signed-in person (person_model.py). Nothing here quotes a chat message.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException, Query
from starlette.concurrency import run_in_threadpool

import consent
import doc_store
import person_model as pm
import stars_lens

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

    # ---- Stars lens: opt-in, a traditional lens that only ever helps choose words ---------------------------------------------------
    def _stars_state(uid: str, now: datetime) -> dict[str, Any]:
        granted = consent.is_granted(db, uid, "stars_lens")
        saved = doc_store.get(db, uid, stars_lens.KIND, stars_lens.KEY) or {}
        out: dict[str, Any] = {"status": "success", "intro": stars_lens.TRADITION_LINE, "consent": granted, "enabled": bool(granted and saved.get("birth_date"))}
        if out["enabled"]:
            place = stars_lens.city(str(saved.get("city_id")))
            if place:
                chart = stars_lens.compute_chart(date.fromisoformat(saved["birth_date"]), saved.get("birth_time"), place)
                out.update(stars_lens.view(chart, pm.load(db, uid), now))
                out["birth"] = {"date": saved["birth_date"], "time": saved.get("birth_time"), "place": {"id": place["id"], "name": place["name"], "country": place["country"]}}
        return out

    @router.get("/me/stars")
    async def stars(authorization: str | None = Header(default=None)):
        uid = await uid_of(authorization)
        return await run_in_threadpool(_stars_state, uid, datetime.now(timezone.utc))

    @router.get("/me/stars/places")
    async def stars_places(q: str = Query("", max_length=40), authorization: str | None = Header(default=None)):
        await uid_of(authorization)
        return {"status": "success", "places": stars_lens.search_cities(q)}

    @router.put("/me/stars")
    async def stars_save(payload: dict = Body(...), authorization: str | None = Header(default=None)):
        uid = await uid_of(authorization)
        if not await run_in_threadpool(consent.is_granted, db, uid, "stars_lens"):
            raise HTTPException(status_code=403, detail="Say yes to the Stars lens first")
        try:
            birth = date.fromisoformat(str(payload.get("birth_date") or ""))
        except ValueError:
            raise HTTPException(status_code=422, detail="Enter your birth date")
        if birth > date.today():
            raise HTTPException(status_code=422, detail="Your birth date cannot be in the future")
        place = stars_lens.city(str(payload.get("city_id") or ""))
        if place is None:
            raise HTTPException(status_code=422, detail="Choose your birth place from the list")
        birth_time = payload.get("birth_time") or None
        try:
            chart = stars_lens.compute_chart(birth, birth_time, place)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Enter the birth time as HH:MM, or leave it empty if you do not know it" if str(error) == "bad_time"
                                else "Birth years from 1900 to 2100 are supported")
        now = datetime.now(timezone.utc)

        def save() -> dict[str, Any]:
            doc_store.put(db, uid, stars_lens.KIND, stars_lens.KEY, {"birth_date": birth.isoformat(), "birth_time": birth_time, "city_id": place["id"], "saved_at": now.isoformat()})
            model = pm.load(db, uid, fresh=True)
            stars_lens.apply_priors(model, chart, now)
            pm.save(db, uid, model)
            return _stars_state(uid, now)

        return await run_in_threadpool(save)

    @router.delete("/me/stars")
    async def stars_off(authorization: str | None = Header(default=None)):
        """Turn the lens off: the birth date, time and place are deleted, and so are the hints it added to what Bubbles knows about you."""
        uid = await uid_of(authorization)
        now = datetime.now(timezone.utc)

        def off() -> dict[str, Any]:
            doc_store.delete(db, uid, stars_lens.KIND, stars_lens.KEY)
            model = pm.load(db, uid, fresh=True)
            stars_lens.clear_priors(model)
            pm.save(db, uid, model)
            return _stars_state(uid, now)

        return await run_in_threadpool(off)

    return router
