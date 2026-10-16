"""Whole-service usage counts for the admin portal: how many different people were active and how many signed up.

Integers only. The reads pull user ids out of the database into this process to count them, and nothing returns them: the answer is
``{"active_1d": 12, "active_7d": 40, "active_30d": 90, "signups_7d": 5, "signups_30d": 18, "capped": false}``. A person counts as active on a
day they sent Bubbles a message (chat_messages, role user). Admin routes only (admin_api); never reachable by an ordinary user.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

PAGE = 1000
ROW_CAP = 20_000   # ponytail: reads at most this many message rows per call; an SQL count(distinct) function is the upgrade path


def _rows_since(db: Any, table: str, columns: str, time_column: str, since: datetime, *, role: str | None = None) -> tuple[list[dict], bool]:
    """Rows newer than ``since``, newest first, paged by the time column, at most ROW_CAP. Returns (rows, capped)."""
    rows: list[dict] = []
    cursor: str | None = None
    while len(rows) < ROW_CAP:
        query = db.table(table).select(columns).gte(time_column, since.isoformat())
        if role:
            query = query.eq("role", role)
        if cursor:
            query = query.lt(time_column, cursor)
        page = query.order(time_column, desc=True).limit(PAGE).execute().data or []
        rows += page
        if len(page) < PAGE:
            return rows, False
        cursor = str(page[-1][time_column])
    return rows[:ROW_CAP], True


def activity_counts(db: Any, now: datetime | None = None) -> dict[str, Any]:
    """Distinct active people in the last 1, 7 and 30 days, and new profiles in the last 7 and 30. A read that fails gives None for its numbers."""
    now = now or datetime.now(timezone.utc)
    out: dict[str, Any] = {"active_1d": None, "active_7d": None, "active_30d": None, "signups_7d": None, "signups_30d": None, "capped": False}
    try:
        messages, capped = _rows_since(db, "chat_messages", "user_id,created_at", "created_at", now - timedelta(days=30), role="user")
        out["capped"] = capped
        for key, days in (("active_1d", 1), ("active_7d", 7), ("active_30d", 30)):
            cutoff = (now - timedelta(days=days)).isoformat()
            out[key] = len({m["user_id"] for m in messages if m.get("user_id") and str(m.get("created_at") or "") >= cutoff})
    except Exception:  # noqa: BLE001 - a number that could not be read stays None; the page says "not available"
        pass
    try:
        profiles, _capped = _rows_since(db, "profiles", "id,created_at", "created_at", now - timedelta(days=30))
        for key, days in (("signups_7d", 7), ("signups_30d", 30)):
            cutoff = (now - timedelta(days=days)).isoformat()
            out[key] = len({p["id"] for p in profiles if p.get("id") and str(p.get("created_at") or "") >= cutoff})
    except Exception:  # noqa: BLE001
        pass
    return out
