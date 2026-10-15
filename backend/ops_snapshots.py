"""Integer-only snapshots for the admin Overall page, read from tables that already exist.

Everything returned here is a count: active people (DAU/WAU/MAU), signups, retention, how many people said yes or no per consent
purpose, community and push totals. No user id, no row, no text leaves this module. Every reader returns ``None`` when its table
is not there yet (the page says "not set up yet"), and nothing here can fail a request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import ttl_cache

PAGE = 1000
ROW_CAP = 50_000   # ponytail: distinct counts are taken in Python over at most this many rows; an SQL count(distinct) function is the upgrade path
RETENTION_DAYS = (1, 7, 30)
COHORT_WINDOW_DAYS = 45

_cache = ttl_cache.TTLCache("admin_overall_users", 300.0, max_entries=8)


def _pages(make_query, cap: int = ROW_CAP) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    while len(rows) < cap:
        page = make_query().range(len(rows), len(rows) + PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE:
            return rows, False
    return rows[:cap], True


def _count(db: Any, table: str, **eq: Any) -> int | None:
    try:
        q = db.table(table).select("id", count="exact")
        for k, v in eq.items():
            q = q.eq(k, v)
        return q.limit(1).execute().count
    except Exception:  # noqa: BLE001
        return None


def _day(iso: str) -> str:
    return str(iso)[:10]


def users(db: Any, now: datetime | None = None) -> dict[str, Any]:
    """Cached for five minutes. Active = sent at least one chat message in a rolling 1, 7 or 30 days."""
    return _cache.get_or_compute("users", lambda: _users(db, now or datetime.now(timezone.utc)))


def _users(db: Any, now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"dau": None, "wau": None, "mau": None, "capped": False, "signups": None, "signups_total": None, "retention": None}
    since = (now - timedelta(days=COHORT_WINDOW_DAYS)).isoformat()
    try:
        msgs, capped = _pages(lambda: db.table("chat_messages").select("user_id,created_at").eq("role", "user").gte("created_at", since).order("created_at", desc=True))
        out["capped"] = capped
        last_seen: dict[str, str] = {}
        days_by_user: dict[str, set[str]] = {}
        for m in msgs:
            uid, at = m.get("user_id"), str(m.get("created_at") or "")
            if uid and at:
                last_seen[uid] = max(last_seen.get(uid, ""), at)
                days_by_user.setdefault(uid, set()).add(_day(at))
        for key, days in (("dau", 1), ("wau", 7), ("mau", 30)):
            cut = (now - timedelta(days=days)).isoformat()
            out[key] = sum(1 for at in last_seen.values() if at >= cut)
    except Exception:  # noqa: BLE001
        return out
    out["signups_total"] = _count(db, "profiles")
    try:
        counts = {}
        for key, days in (("24h", 1), ("7d", 7), ("30d", 30)):
            q = db.table("profiles").select("id", count="exact").gte("created_at", (now - timedelta(days=days)).isoformat())
            counts[key] = q.limit(1).execute().count
        out["signups"] = counts
        profiles, _ = _pages(lambda: db.table("profiles").select("id,created_at").gte("created_at", since).order("created_at", desc=True), cap=20_000)
        out["retention"] = _retention(profiles, days_by_user, now)
    except Exception:  # noqa: BLE001
        pass
    return out


def _retention(profiles: list[dict[str, Any]], days_by_user: dict[str, set[str]], now: datetime) -> dict[str, dict[str, Any]]:
    """Of the people who signed up at least N days ago, how many sent a chat message on or after day N."""
    result = {}
    for n in RETENTION_DAYS:
        eligible = returned = 0
        for p in profiles:
            created = str(p.get("created_at") or "")
            if len(created) < 10 or created > (now - timedelta(days=n)).isoformat():
                continue
            eligible += 1
            start = (datetime.fromisoformat(created[:10]) + timedelta(days=n)).date().isoformat()
            if any(d >= start for d in days_by_user.get(p.get("id"), ())):
                returned += 1
        result[f"d{n}"] = {"eligible": eligible, "returned": returned, "rate": round(returned / eligible, 3) if eligible else None}
    return result


def consent_rates(db: Any) -> list[dict[str, Any]] | None:
    """Per purpose: how many people have it on, how many turned it off. Counts of the latest decision per person only."""
    try:
        rows, _ = _pages(lambda: db.table("consent_events").select("user_id,purpose,granted,created_at").order("created_at", desc=True))
    except Exception:  # noqa: BLE001
        return None
    latest: dict[tuple[str, str], bool] = {}
    for r in rows:   # newest first, so the first row per person and purpose is the current decision
        latest.setdefault((str(r.get("user_id")), str(r.get("purpose"))), bool(r.get("granted")))
    purposes: dict[str, list[int]] = {}
    for (_uid, purpose), granted in latest.items():
        counts = purposes.setdefault(purpose, [0, 0])
        counts[0 if granted else 1] += 1
    return [{"purpose": p, "granted": g, "declined": d, "decided": g + d, "rate": round(g / (g + d), 3)} for p, (g, d) in sorted(purposes.items())]


def community(db: Any) -> dict[str, int] | None:
    counts = {status: _count(db, "community_posts", status=status) for status in ("visible", "held", "removed")}
    if all(v is None for v in counts.values()):
        return None
    return {k: v or 0 for k, v in counts.items()}


def push(db: Any) -> dict[str, int] | None:
    active = _count(db, "device_tokens", revoked=False)
    return None if active is None else {"active_devices": active}
