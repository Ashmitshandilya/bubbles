"""Admin portal API (/admin/*): operational data only, for the ids in BUBBLES_ADMIN_USER_IDS signed in with two-step sign-in.

The real gate is main._admin_gate, which runs in the middleware BEFORE routing and answers a plain 404 to everyone else. The
dependency here is a second lock on the same door (it relies on what the gate stored on the request). Nothing here reads a
user's health data: every number comes from ops_telemetry events, which hold technical metadata only.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

import admin_settings
import ops_metrics
import ops_telemetry
import ttl_cache

RANGES = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(hours=24),
          "7d": timedelta(days=7), "30d": timedelta(days=30)}
RANGE_PATTERN = "^(15m|1h|6h|24h|7d|30d)$"
NOW_WINDOW = timedelta(minutes=5)
LIVE_REFRESH_SECONDS = 5
PAGE_MAX = 200
_REQUEST_ID = re.compile(r"^[0-9a-f]{8,12}$")
_KEY_ENV = {"Gemini": "GEMINI_API_KEY", "Groq": "GROQ_API_KEY", "NVIDIA": "NVIDIA_API_KEY", "Mistral": "MISTRAL_API_KEY"}
_OUTCOMES = {"success", "error", "timeout", "budget_spent", "invalid_json", "answered", "degraded"}


def _admin(request: Request) -> str:
    admin_id = getattr(request.state, "admin_user_id", None)
    if not admin_id:
        raise HTTPException(status_code=404, detail="Not Found")
    return admin_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window(range_: str) -> tuple[datetime, datetime]:
    until = _now()
    return until - RANGES[range_], until


def _meta(source: str, capped: bool, range_: str | None = None) -> dict[str, Any]:
    out = {"generated_at": _now().isoformat(), "source": source, "capped": capped, "cap": ops_telemetry.READ_CAP}
    if range_:
        out["range"] = range_
    return out


def _persistence() -> dict[str, Any]:
    s = dict(ops_telemetry.status)
    return {"mode": s["mode"], "written": s["written"], "dropped": s["dropped"], "write_errors": s["write_errors"],
            "last_write_at": s["last_write_at"], "last_prune_at": s["last_prune_at"], "retention_days": ops_telemetry.retention_days}


def _chain() -> list[dict[str, Any]]:
    return [{"provider": name, "position": i, "paused": admin_settings.is_paused(name), "key_configured": bool(os.getenv(_KEY_ENV.get(name, "")))}
            for i, name in enumerate(admin_settings.chain_names(), start=1)]


def _cache_stats() -> list[dict[str, Any]]:
    return [{k: v for k, v in s.items() if k != "saved_ms_estimate"} for s in ttl_cache.all_stats()]


def _keyless_health_pool() -> bool:
    import ai_provider
    return ai_provider.ALLOW_KEYLESS_AI and ai_provider.ALLOW_KEYLESS_HEALTH_DATA


class SettingChange(BaseModel):
    key: str
    value: bool | int


def build_admin_router(database_report: Callable[[], dict[str, Any]]) -> APIRouter:
    router = APIRouter(prefix="/admin", include_in_schema=False, dependencies=[Depends(_admin)])

    @router.get("/me")
    def me(admin_id: str = Depends(_admin)):
        return {"status": "success", "admin": True, "you": admin_id,
                "environment": "production" if os.getenv("RENDER") else "local",
                "commit": (os.getenv("RENDER_GIT_COMMIT") or "")[:7] or None,
                "started_at": ops_telemetry.STARTED_AT.isoformat(), "persistence": _persistence(), "chain": _chain(),
                "live_refresh_seconds": LIVE_REFRESH_SECONDS, "generated_at": _now().isoformat()}

    @router.get("/overview")
    def overview(range_: str = Query("1h", alias="range", pattern=RANGE_PATTERN)):
        since, until = _window(range_)
        events, capped, source = ops_telemetry.stored_events(since, ["api", "ai_attempt", "ai_reply", "error"])
        now_events = ops_telemetry.memory_events(until - NOW_WINDOW)
        ai_now, api_now = ops_metrics.ai_summary(now_events), ops_metrics.api_summary(now_events, until - NOW_WINDOW, until)
        try:
            database = database_report().get("database", "unknown")
        except Exception:  # noqa: BLE001
            database = "unknown"
        chain = _chain()
        return {
            "status": "success", **_meta(source, capped, range_),
            "headline": ops_metrics.headline(database=database, persistence_mode=ops_telemetry.status["mode"],
                                             all_paused=all(c["paused"] for c in chain) and not _keyless_health_pool(),
                                             ai_now=ai_now, api_now=api_now),
            "now": {"window_minutes": 5, "ai": ai_now, "api": api_now, "answering": ops_metrics.answering(now_events)},
            "system": {
                "components": {"database": database, "ai_keys": {c["provider"]: c["key_configured"] for c in chain}},
                "version": "0.1.0", "environment": "production" if os.getenv("RENDER") else "local",
                "commit": (os.getenv("RENDER_GIT_COMMIT") or "")[:7] or None,
                "started_at": ops_telemetry.STARTED_AT.isoformat(),
                "uptime_s": int((until - ops_telemetry.STARTED_AT).total_seconds()),
                "persistence": _persistence(),
            },
            "ai": {**ops_metrics.ai_summary(events), "answering": ops_metrics.answering(events)},
            "api": ops_metrics.api_summary(events, since, until),
            "errors": ops_metrics.error_summary(events),
            "cache": _cache_stats(),
            "chain": chain,
        }

    @router.get("/ai")
    def ai(range_: str = Query("1h", alias="range", pattern=RANGE_PATTERN)):
        since, _until = _window(range_)
        events, capped, source = ops_telemetry.stored_events(since, ["api", "ai_attempt", "ai_reply"])
        rows = ops_metrics.provider_table(events)
        chain = _chain()
        return {"status": "success", **_meta(source, capped, range_), "summary": ops_metrics.ai_summary(events),
                "providers": rows, "highlights": ops_metrics.highlights(rows), "chain": chain,
                "flow": ops_metrics.fallback_chain(events, [c["provider"] for c in chain])}

    @router.get("/api")
    def api(range_: str = Query("1h", alias="range", pattern=RANGE_PATTERN)):
        since, until = _window(range_)
        events, capped, source = ops_telemetry.stored_events(since, ["api"])
        return {"status": "success", **_meta(source, capped, range_), "summary": ops_metrics.api_summary(events, since, until),
                "routes": ops_metrics.api_table(events, since, until)}

    @router.get("/events")
    def events(
        range_: str = Query("1h", alias="range", pattern=RANGE_PATTERN),
        kind: str | None = Query(None, pattern="^(api|ai_attempt|ai_reply|error|audit)$"),
        provider: str | None = Query(None, max_length=40),
        outcome: str | None = Query(None, max_length=20),
        status_class: str | None = Query(None, alias="status", pattern="^[2345]xx$"),
        route: str | None = Query(None, max_length=120),
        request_id: str | None = Query(None, max_length=12),
        before: str | None = Query(None, max_length=40),
        limit: int = Query(50, ge=1, le=PAGE_MAX),
    ):
        if provider is not None and provider not in admin_settings.chain_names():
            raise HTTPException(status_code=422, detail="unknown provider")
        if outcome is not None and outcome not in _OUTCOMES:
            raise HTTPException(status_code=422, detail="unknown outcome")
        if request_id is not None and not _REQUEST_ID.match(request_id):
            raise HTTPException(status_code=422, detail="request id is 8 to 12 hex characters")
        if before is not None:
            try:
                datetime.fromisoformat(before)
            except ValueError as error:
                raise HTTPException(status_code=422, detail="before must be an ISO time") from error
        since, _until = _window(range_)
        rows, capped, source = ops_telemetry.stored_events(since, [kind] if kind else None, request_id=request_id, before=before)

        def keep(e: dict[str, Any]) -> bool:
            d = e.get("data") or {}
            return ((provider is None or d.get("provider") == provider) and (outcome is None or d.get("outcome") == outcome)
                    and (route is None or d.get("route") == route)
                    and (status_class is None or str(d.get("status", ""))[:1] == status_class[0]))

        matched = [e for e in rows if keep(e)]
        page = matched[:limit]
        return {"status": "success", **_meta(source, capped, range_), "events": page,
                "next_before": page[-1]["at"] if len(matched) > limit else None}

    @router.get("/events/live")
    def live(after: int = Query(0, ge=0), process_started_at: str | None = Query(None, max_length=40)):
        restarted = process_started_at is not None and process_started_at != ops_telemetry.STARTED_AT.isoformat()
        rows = ops_telemetry.recent(0 if restarted else after, limit=PAGE_MAX)
        oldest = rows[0]["seq"] if rows else None
        return {"status": "success", "generated_at": _now().isoformat(), "events": rows,
                "next_cursor": rows[-1]["seq"] if rows else (0 if restarted else after),
                "process_started_at": ops_telemetry.STARTED_AT.isoformat(), "restarted": restarted,
                "gap": bool(after and not restarted and oldest is not None and oldest > after + 1),
                "refresh_seconds": LIVE_REFRESH_SECONDS}

    @router.get("/settings")
    def settings():
        return {"status": "success", "generated_at": _now().isoformat(), "settings": admin_settings.describe(),
                "persisted": admin_settings.state["persisted"], "chain": _chain()}

    @router.put("/settings")
    def change_setting(change: SettingChange, admin_id: str = Depends(_admin)):
        try:
            result = admin_settings.update(change.key, change.value, actor=admin_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail={"code": str(error), "message": "That setting or value is not allowed."}) from error
        return {"status": "success", **result}

    @router.get("/audit")
    def audit(range_: str = Query("7d", alias="range", pattern=RANGE_PATTERN), limit: int = Query(100, ge=1, le=PAGE_MAX)):
        since, _until = _window(range_)
        rows, capped, source = ops_telemetry.stored_events(since, ["audit"])
        return {"status": "success", **_meta(source, capped, range_), "events": rows[:limit]}

    @router.post("/cache/clear")
    def clear_caches(admin_id: str = Depends(_admin)):
        count = ttl_cache.clear_all()
        ops_telemetry.record("audit", action="caches_cleared", target="all", new=count, outcome="done", actor=admin_id)
        return {"status": "success", "cleared": count}

    return router
