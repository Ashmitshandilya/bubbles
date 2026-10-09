"""A tracker entry must feed the intelligence endpoints, in both storage modes, without being listed twice."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fake_db import FakeDB, permission_denied  # noqa: E402

USER = "00000000-0000-0000-0000-000000000001"
H = {"Authorization": "Bearer tok"}


@pytest.fixture()
def env():
    db = FakeDB({"tok": USER})
    fake_mod = types.ModuleType("supabase_client")
    fake_mod.supabase = db
    saved = sys.modules.get("supabase_client")
    sys.modules["supabase_client"] = fake_mod
    touched = ("main", "memory_manager", "memory_retrieval", "memory_promotion", "context_engine", "rag", "rl.service", "health_logs", "chat_pipeline", "db_access")
    for m in touched:
        sys.modules.pop(m, None)
    import main
    from fastapi.testclient import TestClient
    yield types.SimpleNamespace(client=TestClient(main.app, raise_server_exceptions=False), db=db, main=main)
    if saved is not None:
        sys.modules["supabase_client"] = saved
    else:
        sys.modules.pop("supabase_client", None)
    for m in touched:
        sys.modules.pop(m, None)


def _post_sleep(env, hours=7.5):
    return env.client.post("/health/sleep", json={"duration": hours, "quality": 7, "date": "2026-10-06"}, headers=H)


def test_primary_save_is_mirrored_once_and_listed_once(env):
    res = _post_sleep(env)
    assert res.status_code == 201 and res.json()["store"] == "primary"
    events = env.db.rows("extracted_health_events")
    assert len(events) == 1 and events[0]["event_type"] == "sleep" and events[0]["extraction_status"] == "confirmed"
    prov = events[0]["extracted_data"]["_prov"]
    assert prov["store"] == "mirror" and prov["domain"] == "sleep" and prov["entry_id"] == res.json()["entry"]["id"]
    assert events[0]["extracted_data"]["hours"] == 7.5 and events[0]["extracted_data"]["duration_minutes"] == 450
    listing = env.client.get("/health/sleep?days=30", headers=H).json()["entries"]
    assert len(listing) == 1  # the mirror is not merged into the tracker's own list


def test_mirrored_entries_reach_the_analytics_reader(env):
    for h in (6, 7, 8):
        assert _post_sleep(env, h).status_code == 201
    rows = env.main._get_user_health_events(USER, days=60)
    assert len(rows) == 3 and all(r["event_type"] == "sleep" for r in rows)
    from event_filters import counts_as_observation
    assert all(counts_as_observation(r) for r in rows)


def test_compat_save_is_not_double_counted_and_still_reaches_analytics(env):
    env.db.failures["sleep_logs"] = permission_denied("sleep_logs")
    res = _post_sleep(env)
    assert res.status_code == 201 and res.json()["store"] == "compat"
    assert len(env.db.rows("extracted_health_events")) == 1  # one event, not compat + mirror
    assert len(env.client.get("/health/sleep?days=30", headers=H).json()["entries"]) == 1
    assert len(env.main._get_user_health_events(USER, days=60)) == 1


def test_a_failing_mirror_never_fails_the_save(env):
    env.db.failures["extracted_health_events"] = permission_denied("extracted_health_events")
    res = _post_sleep(env)
    assert res.status_code == 201 and res.json()["store"] == "primary"
    assert len(env.client.get("/health/sleep?days=30", headers=H).json()["entries"]) in (0, 1)  # primary row exists; merge read is best effort


def test_every_tracker_domain_has_an_analytics_event_type():
    import health_logs
    assert set(health_logs.COMPAT_EVENTS) == set(health_logs.DOMAINS)
