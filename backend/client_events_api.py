"""POST /telemetry/client: the app reports that it crashed, as two fixed words and nothing else.

Counts only: the body is validated against fixed lists (ops_telemetry.CLIENT_CODES, CLIENT_SURFACES), no text, no user id and no
sign-in are read, and a global budget stops anyone inflating the numbers. The answer is always the same, so it reveals nothing.
Not product analytics: it is the same operational class as the server's own error counts (docs/admin/README.md).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

import ops_telemetry

BUDGET_PER_MINUTE = 60
_lock = threading.Lock()
_stamps: deque[float] = deque()


class ClientCrash(BaseModel):
    code: Literal["render_error", "unhandled_rejection", "script_error", "chunk_load", "network_error", "other"]
    surface: Literal["web", "android"] = "web"


def _within_budget() -> bool:
    now = time.monotonic()
    with _lock:
        while _stamps and now - _stamps[0] > 60:
            _stamps.popleft()
        if len(_stamps) >= BUDGET_PER_MINUTE:
            return False
        _stamps.append(now)
        return True


def build_client_events_router() -> APIRouter:
    router = APIRouter()

    @router.post("/telemetry/client", status_code=202)
    def client_crash(body: ClientCrash):
        if _within_budget():
            ops_telemetry.client_crash(body.code, body.surface)
        return {"status": "accepted"}

    return router
