"""Database-access helpers: permission-denied detection, clean API errors, and a
cached, row-free reachability probe.

Why this exists: the live Supabase project denies the backend service role on
many tables (Postgres 42501) until ``20261006_coco_service_role_grants.sql`` is
applied. Without handling, an unhandled ``APIError`` becomes a bare 500 that the
browser reports as "can't connect to backend" (it bypasses the CORS middleware).
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

PERMISSION_FIX = "Apply supabase/migrations/20261006_coco_service_role_grants.sql in the Supabase SQL editor."

# user_preferences has no id column, so it is deliberately not probed.
PROBE_TABLES = ("profiles", "sleep_logs", "health_events", "extracted_health_events", "chat_messages")

_PERMISSION = re.compile(r"permission denied|\b42501\b", re.I)
_TABLE = re.compile(r"(?:permission denied|row-level security policy)\s+for\s+(?:table|relation)\s+[\"']?([\w.]+)[\"']?", re.I)
_HTTP_5XX = re.compile(r"5\d\d")


def _blob(exc: Any) -> str:
    """Every piece of text an error carries (message, dict payload, args)."""
    parts = [str(exc), repr(exc)] if not isinstance(exc, dict) else [str(exc)]
    for attr in ("code", "message", "details", "hint"):
        value = getattr(exc, attr, None)
        if value:
            parts.append(str(value))
    parts.extend(str(a) for a in getattr(exc, "args", ()))
    return " ".join(parts)


def is_permission_denied(exc: Any) -> bool:
    """True for Postgres 42501 / "permission denied" errors, however they were wrapped."""
    if str(getattr(exc, "code", "")) == "42501":
        return True
    try:
        return bool(_PERMISSION.search(_blob(exc)))
    except Exception:  # an exotic exception whose __str__ raises must not break error handling
        return False


def denied_table(exc: Any) -> str | None:
    """The table named in 'permission denied for table X' (schema prefix dropped), if any."""
    try:
        match = _TABLE.search(_blob(exc))
    except Exception:
        return None
    return match.group(1).rsplit(".", 1)[-1] if match else None


def database_permission_response(exc: Any) -> JSONResponse:
    table = denied_table(exc)
    what = f"the '{table}' table" if table else "a required table"
    detail = f"Bubbles' database refused the backend access to {what} (permission denied). {PERMISSION_FIX}"
    return JSONResponse(status_code=503, content={"detail": detail, "code": "database_permission_denied", "table": table})


def register_db_error_handlers(app: FastAPI) -> None:
    """Turn Supabase ``APIError`` into clean JSON (503 for permission, 500 otherwise, no internals).

    Handled responses pass through the CORS middleware, so the browser can read them;
    an unhandled exception would surface as a network failure instead.
    """

    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError) -> JSONResponse:
        if is_permission_denied(exc):
            return database_permission_response(exc)
        try:
            from logging_util import logger
            logger.error(component="DATABASE", operation="request", error=exc,
                         context={"path": request.url.path}, fallback_action="returning_generic_500")
        except Exception:
            pass
        return JSONResponse(status_code=500, content={"detail": "Database error", "code": "database_error"})


# --- reachability / permission probe ---------------------------------------------

_cache: dict[str, Any] = {}
_lock = threading.Lock()


def reset_probe_cache() -> None:
    with _lock:
        _cache.clear()


def _is_unreachable(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TransportError, OSError)) or bool(_HTTP_5XX.fullmatch(str(getattr(exc, "code", ""))))


def _probe(db: Any) -> dict[str, Any]:
    denied: list[str] = []
    accessible: list[str] = []
    unreachable = other = False
    for table in PROBE_TABLES:
        try:
            db.table(table).select("id").limit(1).execute()
            accessible.append(table)
        except Exception as exc:  # never raise, never keep row data
            if is_permission_denied(exc):
                denied.append(table)
            elif _is_unreachable(exc):
                unreachable = True
                break  # one timeout is enough; do not wait on four more
            else:
                other = True
    state = "unreachable" if unreachable else "permission_denied" if denied else "unknown" if other else "ok"
    return {"database": state, "denied": denied, "accessible": accessible, "compat_mode": state == "permission_denied"}


def probe_database(db: Any, *, ttl: float = 30) -> dict[str, Any]:
    """Which key tables the backend can read. Cached per process for ``ttl`` seconds; never raises."""
    with _lock:
        hit = _cache.get("probe")
        if hit and hit["db"] is db and time.monotonic() - hit["at"] < ttl:
            result = hit["result"]
        else:
            result = _probe(db)
            _cache["probe"] = {"db": db, "at": time.monotonic(), "result": result}
        return {**result, "denied": list(result["denied"]), "accessible": list(result["accessible"])}
