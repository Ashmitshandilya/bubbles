"""GET /me/predictions: Bubbles scores its own earlier guesses against what the person logged, makes today's, and says only what it has earned.

One signed document per person (``prediction_ledger``); it holds dates, numbers and hit counts, never words. It is read with the same data the
Patterns page uses, so it needs no extra consent, and it is removed with the rest of the person's documents.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header
from starlette.concurrency import run_in_threadpool

import doc_store
import prediction_ledger as pl

KIND, KEY = "prediction_ledger", "main"


def run(db: Any, uid: str) -> dict[str, Any]:
    import association_loader
    names = {n for link in pl.LINKS for n in link[:2]}
    series, today = association_loader.load_some(db, uid, names)
    ledger = doc_store.get(db, uid, KIND, KEY) or {"entries": [], "stats": {}}
    scored = pl.score(ledger, series, today)
    fresh = pl.make(series, today, ledger)
    ledger["entries"] = ledger.get("entries", []) + fresh
    pl.prune(ledger)
    if scored or fresh:
        doc_store.put(db, uid, KIND, KEY, ledger)
    sentences = [s for s in (pl.line(ledger, g) for g in fresh) if s]
    links = [{"link": [x, y], **pl.trust(ledger, x, y)} for x, y, *_ in pl.LINKS]
    return {"status": "success", "today": sentences, "links": links, "scored_now": scored, "checked": pl.checked(ledger, today)}


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/me/predictions")
    async def predictions(authorization: str | None = Header(default=None)):
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        return await run_in_threadpool(run, db, uid)

    return router
