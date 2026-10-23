"""The scheduler endpoint: ``app.include_router(push_api.build_router(supabase))`` (no user, so no get_user).

  POST /internal/push/run   header X-Cron-Secret   (anything else, including an unset secret, is the same plain 404 an unknown path gives)

Called every ~10 minutes by .github/workflows/keep-awake.yml. It sends the phone reminders that are due (push_fcm.sweep) and then
refreshes the admin rollups (ops_rollups.run_rollups). It never receives or returns a user id, token or text: the answer is counts.
The secret is BUBBLES_CRON_SECRET (NOTIFY_CRON_SECRET is accepted as the older name).
"""
from __future__ import annotations

import hmac
import os
import threading
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import push_fcm

_running = threading.Lock()   # ponytail: one API process (DEPLOY.md); the per-slot dedupe key covers a second one


def cron_secret_ok(given: str | None) -> bool:
    secret = (os.getenv("BUBBLES_CRON_SECRET") or os.getenv("NOTIFY_CRON_SECRET") or "").strip()
    return bool(secret and given) and hmac.compare_digest(given.encode(), secret.encode())  # type: ignore[union-attr]


def run_once(db: Any) -> dict[str, Any]:
    out = push_fcm.sweep(db)
    try:   # admin rollups (ops_rollups, F2); a failure there never affects the reminders
        from ops_rollups import run_rollups

        run_rollups(db)
        out["rollups"] = "done"
    except Exception:  # noqa: BLE001
        out["rollups"] = "failed"
    try:   # the Playbook: purge old de-identified candidates, then draft entries for the owner to review (counts only)
        import playbook

        out["playbook"] = playbook.maintain(db)
    except Exception:  # noqa: BLE001
        out["playbook"] = "failed"
    return out


def build_router(db: Any) -> APIRouter:
    router = APIRouter()

    # Every method is registered so that a wrong method, an unset secret and a wrong secret are all the same 404 (a 405 would show
    # that the route exists).
    @router.api_route("/internal/push/run", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"], include_in_schema=False)
    async def push_run(request: Request, x_cron_secret: str | None = Header(default=None)):
        if request.method != "POST" or not cron_secret_ok(x_cron_secret):
            raise HTTPException(status_code=404, detail="Not Found")
        if not _running.acquire(blocking=False):
            return {"status": "success", "skipped": "already_running"}
        try:
            return {"status": "success", **await run_in_threadpool(run_once, db)}
        finally:
            _running.release()

    return router
