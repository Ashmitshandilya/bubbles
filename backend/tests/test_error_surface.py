"""Errors must reach the browser as readable JSON WITH CORS headers.

Why: an exception that escapes the app is turned into a 500 by Starlette's outermost layer, which sits
outside CORSMiddleware. That response has no Access-Control-Allow-Origin, so the browser reports a network
failure ("can't connect to backend") although the server answered. These tests pin the behaviour that
prevents that, plus the /health database report and CORS on any local dev port.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fake_db import FakeAPIError, FakeDB, permission_denied  # noqa: E402

ORIGIN = {"Origin": "http://localhost:3000"}
AUTH = {"Authorization": "Bearer tok"}


@pytest.fixture()
def env():
    db = FakeDB({"tok": "00000000-0000-0000-0000-000000000001"})
    fake_mod = types.ModuleType("supabase_client")
    fake_mod.supabase = db
    saved = sys.modules.get("supabase_client")
    sys.modules["supabase_client"] = fake_mod
    touched = ("main", "memory_manager", "memory_retrieval", "memory_promotion", "context_engine", "rag", "rl.service", "health_logs", "chat_pipeline", "db_access")
    for m in touched:
        sys.modules.pop(m, None)
    import db_access
    import main
    from fastapi.testclient import TestClient

    db_access.reset_probe_cache()
    main._probe_future = None
    client = TestClient(main.app, raise_server_exceptions=False)
    yield types.SimpleNamespace(client=client, db=db, main=main, db_access=db_access)
    if saved is not None:
        sys.modules["supabase_client"] = saved
    else:
        sys.modules.pop("supabase_client", None)
    for m in touched:
        sys.modules.pop(m, None)


def test_unhandled_exception_is_json_with_cors_headers(env):
    @env.main.app.get("/_boom")
    def boom():
        raise RuntimeError("boom with secret-looking detail sk-123")

    res = env.client.get("/_boom", headers=ORIGIN)
    assert res.status_code == 500
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    body = res.json()
    assert body["code"] == "server_error" and "sk-123" not in res.text  # readable, and no internals leaked
    assert res.headers.get("cache-control") == "no-store"  # security headers still applied


def test_database_permission_error_is_503_with_cors_and_a_fix_hint(env):
    env.db.failures["chat_conversations"] = permission_denied("chat_conversations")
    res = env.client.get("/chat/history", headers={**AUTH, **ORIGIN})
    # /chat/history swallows DB errors by design; a route that does not must still be readable:
    @env.main.app.get("/_denied")
    def denied():
        raise permission_denied("profiles")

    res = env.client.get("/_denied", headers=ORIGIN)
    assert res.status_code == 503
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    body = res.json()
    assert body["code"] == "database_permission_denied" and body["table"] == "profiles"
    assert "20261006_coco_service_role_grants.sql" in body["detail"]


def test_other_database_errors_are_generic_500_json_with_cors(env):
    @env.main.app.get("/_dberr")
    def dberr():
        raise FakeAPIError("relation does not exist: secret_table", "42P01")

    res = env.client.get("/_dberr", headers=ORIGIN)
    assert res.status_code == 500 and res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "secret_table" not in res.text


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3456"])
def test_cors_allows_any_local_dev_port(env, origin):
    res = env.client.options("/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "authorization,content-type"})
    assert res.status_code == 200 and res.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", ["http://evil.example", "https://localhost:3000", "http://localhost.evil.example", "http://192.168.1.5:3000", "http://localhost:3000.evil.example"])
def test_cors_rejects_foreign_origins(env, origin):
    res = env.client.options("/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert res.headers.get("access-control-allow-origin") is None


def test_health_reports_ok_when_every_probed_table_is_readable(env):
    body = env.client.get("/health").json()
    assert body["status"] == "healthy" and body["services"]["database"] == "ok"
    assert body["compat_mode"] is False and body["denied_tables"] == []


def test_health_reports_compat_mode_and_names_denied_tables_but_stays_healthy(env):
    env.db.failures["profiles"] = permission_denied("profiles")
    env.db.failures["sleep_logs"] = permission_denied("sleep_logs")
    body = env.client.get("/health").json()
    assert body["status"] == "healthy"  # the backend itself is fine; it is running in compatibility mode
    assert body["services"]["database"] == "permission_denied" and body["compat_mode"] is True
    assert set(body["denied_tables"]) == {"profiles", "sleep_logs"}


def test_health_never_hangs_when_the_probe_is_slow(env):
    import threading
    import time

    release = threading.Event()

    def slow(*_a, **_k):
        release.wait(5)
        return {"database": "ok", "denied": [], "accessible": [], "compat_mode": False}

    env.main.probe_database = slow
    start = time.perf_counter()
    res = env.client.get("/health")
    elapsed = time.perf_counter() - start
    release.set()
    assert res.status_code == 200 and elapsed < 3.5
    assert res.json()["services"]["database"] == "unknown"
