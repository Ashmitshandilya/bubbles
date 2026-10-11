"""Request-level protections that sit in front of every route: a streamed body-size cap, address-based limits and a log filter.

Kept in one small module so each rule can be tested without starting the app.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from fastapi import HTTPException

MAX_BODY_BYTES = 2_000_000
"""No request body anywhere in the API is larger than this. Guarded routes keep their own, lower cap (main.py)."""


def _too_large() -> HTTPException:
    return HTTPException(status_code=413, detail="That request is too large.")


class BodyLimitMiddleware:
    """Refuses oversized request bodies, including chunked bodies that carry no Content-Length header.

    A declared size over the limit is refused before anything is read. An undeclared (streamed) body is counted as it arrives and
    the read stops with a 413 the moment it passes the limit, so a client cannot make the server buffer an unbounded body.
    """

    def __init__(self, app: Any, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        declared = next((v for k, v in scope.get("headers", []) if k == b"content-length"), None)
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._refuse(send)
            return
        received = 0

        async def limited_receive() -> dict:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _too_large()
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _refuse(send: Any) -> None:
        body = b'{"detail":"That request is too large.","code":"too_large"}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


# Share links carry a secret token in the address. The server log must never keep it (or a search term in the query string).
_TOKEN_PATH = re.compile(r"(/(?:cycle/)?partner/)[^/\s?#]+")


def redact_path(target: str) -> str:
    """The request target with the query string removed and any share token replaced."""
    path = target.split("?", 1)[0]
    return _TOKEN_PATH.sub(r"\1[redacted]", path)


class AccessLogRedactor(logging.Filter):
    """Applied to uvicorn's access log: the logged path is redacted (see ``redact_path``)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - the logging API's name
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], redact_path(args[2]), *args[3:])
        return True


def install_access_log_redaction() -> None:
    """Attach the filter once (importing the app twice must not stack filters)."""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, AccessLogRedactor) for f in logger.filters):
        logger.addFilter(AccessLogRedactor())


def admin_ids() -> frozenset[str]:
    """User ids allowed to read operational data (``BUBBLES_ADMIN_USER_IDS``, comma separated). Empty means nobody."""
    return frozenset(part.strip() for part in os.getenv("BUBBLES_ADMIN_USER_IDS", "").split(",") if part.strip())


def require_admin(user: Any) -> None:
    """Raises 403 unless the signed-in user is on the admin list. Process-wide metadata is not for ordinary accounts."""
    if str(getattr(user, "id", "")) not in admin_ids():
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Insufficient permissions for this operation"})
