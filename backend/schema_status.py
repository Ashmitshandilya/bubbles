"""Which Bubbles migrations the database has: GET /admin/schema (admin only: the /admin gate in main.py runs before this router).

Every migration in supabase/migrations adds its name to public.bubbles_schema_migrations as its last step
(supabase/migrations/20261016_bubbles_schema_migrations.sql). ``KNOWN`` lists the ones the app can use; a lane that adds a migration adds its
name here. Names only, no user data. If the register itself is missing, ``registered`` is false and every entry is reported as unknown.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ttl_cache import TTLCache

REGISTER = "bubbles_schema_migrations"

KNOWN: dict[str, str] = {
    "20261016_bubbles_schema_migrations": "Register of applied migrations (run this first)",
    "20261013_bubbles_ops": "Admin telemetry is kept across restarts",
    "20261013_bubbles_db_tuneup": "Unused tables moved out of the public schema",
    "20261016_bubbles_indexes_v2": "Faster document, chat and memory reads",
    "20261016_bubbles_lookup_indexes": "Faster tracker summary, partner link, compat reads and chat history counts",
    "20261016_bubbles_consent_ledger": "Consent history table (until then it is kept as signed documents)",
}

_cache = TTLCache("schema_status", ttl_s=60, max_entries=2)   # migration names only, no user data


def report(db: Any) -> dict:
    """{registered, applied, missing[{name, why}], unknown_applied}. Never raises."""
    def compute() -> dict:
        try:
            rows = db.table(REGISTER).select("name").limit(500).execute().data or []
        except Exception:  # noqa: BLE001 - not created yet, not granted, or the database is down
            return {"registered": False, "applied": [], "missing": [{"name": n, "why": w} for n, w in KNOWN.items()]}
        applied = sorted({str(r.get("name")) for r in rows if isinstance(r, dict) and r.get("name")})
        return {"registered": True, "applied": applied,
                "missing": [{"name": n, "why": w} for n, w in KNOWN.items() if n not in applied]}
    return _cache.get_or_compute("all", compute)


def build_router(db: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/schema")
    def admin_schema():
        return {"status": "success", **report(db)}

    return router
