"""GET /today: the one call Today makes. Each part must be exactly what its own route says (sharing work inside one request must not change an
answer), a part that cannot be read is null and alone, and nothing is remembered between requests."""
from __future__ import annotations

import pytest

from test_chat_http_flow import H, USER, env  # noqa: F401  (stateful app and fake database)


def _same(a, b):
    """Equal, ignoring the time the answer was made."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("generated_at", "at", "period", "start", "end")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(a) == strip(b)


@pytest.fixture()
def headers():
    return H


def _seed_events(env, n=6):
    for i in range(n):
        env.db.table("extracted_health_events").insert({
            "user_id": USER, "event_type": "sleep", "extracted_data": {"hours": 6 + i * 0.3, "quality": 5 + (i % 3)}, "confidence": 0.9,
            "user_confirmed": True, "extraction_status": "confirmed", "created_at": f"2026-10-{10 + i:02d}T07:00:00+00:00"}).execute()


def test_each_part_equals_its_own_route(env, headers):
    _seed_events(env)
    c = env.client
    today = c.get("/today?days=14", headers=headers).json()
    brief = c.post("/intelligence/brief", json={"days": 14}, headers=headers).json()["brief"]
    living = c.get("/intelligence/living-map?days=14", headers=headers).json()["map"]
    weekly = c.get("/insights/weekly", headers=headers).json()["insights"]
    assert today["status"] == "success"
    assert _same(today["brief"], brief)
    assert _same(today["living_map"], living)
    assert _same(today["weekly"], weekly)


def test_the_parts_alone_and_a_failed_part_is_only_null(env, headers, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("one part is down")
    monkeypatch.setattr(env.main, "build_weekly_insights", broken)
    body = env.client.get("/today", headers=headers).json()
    assert body["weekly"] is None
    assert body["brief"] is not None and set(body["trackers"]) == set(env.main.TODAY_TRACKERS) and body["lede"]["text"]


def test_nothing_is_remembered_between_requests(env, headers):
    c = env.client
    first = c.get("/today", headers=headers).json()
    _seed_events(env, 4)
    second = c.get("/today", headers=headers).json()
    assert second["brief"]["state"] != first["brief"]["state"] or second["brief"]["learning"] != first["brief"]["learning"]
    assert env.main._EVENT_MEMO.get() is None and env.main._STATE_MEMO.get() is None


def test_signed_out_is_refused(env):
    assert env.client.get("/today").status_code == 401
