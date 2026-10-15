"""Android push routes: ``app.include_router(push_api.build_router(get_authenticated_user, supabase))``.

  POST   /notifications/push/register   {token, platform: "android", app_version}   (422 unless the person's push switch is on)
  DELETE /notifications/push/register   {token}                                     (revokes only the caller's own token)
  POST   /internal/push/run             header X-Cron-Secret                         (scheduler; anything else is a plain 404)

The scheduler is called by .github/workflows/keep-awake.yml. It never receives or returns a user id, token or text: the answer is
a handful of counts.
"""
from __future__ import annotations

import hmac
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import notifications as N
import ops_telemetry
import push_devices
import push_fcm

BATCH_USERS = int(os.getenv("BUBBLES_PUSH_BATCH", "200"))      # users handled per run; the rest are picked up by the next runs
TIME_BUDGET_S = float(os.getenv("BUBBLES_PUSH_BUDGET_S", "90"))  # the host answers within this, even for a big batch
_running = threading.Lock()   # ponytail: one process serves the API (DEPLOY.md); the per-slot dedupe key covers anything else


def run_scheduler(db: Any, *, now: datetime | None = None, pusher: Callable[..., Any] | None = None,
                  batch: int | None = None, budget_s: float | None = None) -> dict[str, Any]:
    """One scheduler pass: for each user with an active token and push on, create the reminders that are due and push them.
    Idempotent (per-slot dedupe), bounded (batch and time budget) and fail-soft per user. Returns counts only."""
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    batch = BATCH_USERS if batch is None else batch
    budget_s = TIME_BUDGET_S if budget_s is None else budget_s
    out = {"users": 0, "created": 0, "sent": 0, "failed": 0, "revoked_users": 0, "errors": 0, "partial": False, "rollups": "unavailable"}

    def counting(tokens: list[str], title: str, body: str, kind: str) -> dict[str, Any]:
        result = (pusher or push_fcm.send)(tokens, title, body, kind)
        out["sent"] += int(result.get("sent") or 0)
        out["failed"] += int(result.get("failed") or 0)
        return result
    try:
        users = push_devices.users_with_active_tokens(db)
    except push_devices.PushUnavailable:
        return {**out, "device_table": "not_ready"}
    if len(users) > batch:   # fair over time without any stored cursor: a random slice, a different one each run
        users = random.sample(users, batch)
        out["partial"] = True
    for uid in users:
        if time.monotonic() - started > budget_s:
            out["partial"] = True
            break
        out["users"] += 1
        try:
            if not N.load_settings(db, uid)["channels"].get("push"):   # the switch was turned off: stop pushing to its phones
                push_devices.revoke_all(db, uid)
                out["revoked_users"] += 1
                continue
            out["created"] += len(N.generate_due(db, uid, now, pusher=counting))
        except Exception:  # noqa: BLE001 - one person's problem never stops the others
            out["errors"] += 1
    try:   # admin rollups (lane L9); a missing module or a failure never affects the push run
        from ops_rollups import run_rollups
        run_rollups(db)
        out["rollups"] = "done"
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        out["rollups"] = "failed"
    ops_telemetry.record("audit", action="push_run", target="cron",
                         outcome=f"users={out['users']} created={out['created']} errors={out['errors']}")
    return out


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be an object")
        return body

    def not_ready() -> dict:
        return {"status": "success", "registered": False, "reason": "not_ready"}

    def register(uid: str, body: dict) -> dict:
        if not N.load_settings(db, uid)["channels"].get("push"):
            raise HTTPException(status_code=422, detail="Turn on phone notifications first, then Bubbles can register this phone.")
        try:
            return {"status": "success", **push_devices.register(db, uid, body.get("token"), body.get("platform", "android"), body.get("app_version"))}
        except push_devices.PushInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except push_devices.PushUnavailable:
            return not_ready()

    @router.post("/notifications/push/register")
    async def register_device(request: Request, authorization: str | None = Header(default=None)):
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        return await run_in_threadpool(register, uid, await body_of(request))

    def unregister(uid: str, body: dict) -> dict:
        try:
            return {"status": "success", "revoked": push_devices.unregister(db, uid, body.get("token"))}
        except push_devices.PushInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except push_devices.PushUnavailable:
            return {"status": "success", "revoked": 0, "reason": "not_ready"}

    @router.delete("/notifications/push/register")
    async def unregister_device(request: Request, authorization: str | None = Header(default=None)):
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        return await run_in_threadpool(unregister, uid, await body_of(request))

    def cron_secret_ok(given: str | None) -> bool:
        secret = (os.getenv("BUBBLES_CRON_SECRET") or os.getenv("NOTIFY_CRON_SECRET") or "").strip()
        return bool(secret and given) and hmac.compare_digest(given.encode(), secret.encode())  # type: ignore[union-attr]

    # Every method is registered so that a wrong method, an unset secret and a wrong secret are all the same plain 404 an unknown
    # path gives (a 405 would reveal that the route exists).
    @router.api_route("/internal/push/run", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"], include_in_schema=False)
    async def push_run(request: Request, x_cron_secret: str | None = Header(default=None)):
        if request.method != "POST" or not cron_secret_ok(x_cron_secret):
            raise HTTPException(status_code=404, detail="Not Found")
        if not _running.acquire(blocking=False):
            return {"status": "success", "skipped": "already_running"}
        try:
            return {"status": "success", **await run_in_threadpool(run_scheduler, db, pusher=push_fcm.send)}
        finally:
            _running.release()

    return router
