"""POST /telemetry/client {code}: the website or the app says that something broke, as one of a fixed list of codes.

Open to everyone on purpose (a crash can happen before sign-in), so it can only ever add one counter tick: the code must be one of
ops_telemetry.CLIENT_CODES, nothing else in the body is read, nothing is stored but the code, and a global limit stops a flood.
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

import ops_telemetry
from chat_pipeline import RateLimiter

_limiter = RateLimiter(limit=120, window=60.0)   # ponytail: one global bucket, not per address; enough to keep one script from filling the log


class ClientProblem(BaseModel):
    code: str


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/telemetry/client", status_code=204)
    def report(problem: ClientProblem):
        if _limiter.allow("all") and problem.code in ops_telemetry.CLIENT_CODES:
            ops_telemetry.client(problem.code)
        return Response(status_code=204)   # the same answer whatever was sent: nothing to probe

    return router
