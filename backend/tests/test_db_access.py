"""db_access: permission-denied detection, clean API errors, and the cached row-free probe."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import BaseModel

import db_access
from db_access import (PERMISSION_FIX, PROBE_TABLES, database_permission_response, denied_table, is_permission_denied,
                       probe_database, register_db_error_handlers, reset_probe_cache)


def denied(table="sleep_logs"):
    return APIError({"code": "42501", "message": f"permission denied for table {table}", "details": None, "hint": None})


def other(code="XX000", message="boom with internals"):
    return APIError({"code": code, "message": message, "details": "secret detail", "hint": None})


# --- is_permission_denied / denied_table --------------------------------------------

def test_is_permission_denied_recognises_every_wrapping():
    assert is_permission_denied(denied())
    assert is_permission_denied(APIError({"code": "42501", "message": "new row violates row-level security policy"}))
    assert is_permission_denied(APIError({"code": None, "message": "permission denied for table x"}))
    assert is_permission_denied(Exception("permission denied for table profiles"))
    assert is_permission_denied(Exception("ERROR: PERMISSION DENIED for relation foo"))
    assert is_permission_denied(Exception({"code": "42501", "message": "nope"}))
    assert is_permission_denied({"code": "42501"})
    assert is_permission_denied(RuntimeError("db failed", {"code": "42501"}))
    assert is_permission_denied(SimpleNamespace(code=42501))


def test_is_permission_denied_rejects_everything_else():
    assert not is_permission_denied(other())
    assert not is_permission_denied(APIError({"code": "23505", "message": "duplicate key"}))
    assert not is_permission_denied(ValueError("nope"))
    assert not is_permission_denied(httpx.ConnectError("refused"))
    assert not is_permission_denied(Exception("row 142501 not found"))  # 42501 only as a whole token
    assert not is_permission_denied(None)


def test_is_permission_denied_never_raises_on_hostile_exceptions():
    class Hostile(Exception):
        def __str__(self):
            raise RuntimeError("no str for you")

    assert is_permission_denied(Hostile()) is False
    assert denied_table(Hostile()) is None


def test_denied_table_parses_the_table_name():
    assert denied_table(denied("sleep_logs")) == "sleep_logs"
    assert denied_table(Exception("permission denied for table public.mood_logs")) == "mood_logs"
    assert denied_table(Exception('permission denied for relation "profiles"')) == "profiles"
    assert denied_table(APIError({"code": "42501", "message": 'new row violates row-level security policy for table "allergies"'})) == "allergies"
    assert denied_table(APIError({"code": "42501", "message": "permission denied"})) is None
    assert denied_table(other()) is None


def test_database_permission_response_is_a_plain_503():
    response = database_permission_response(denied("lab_results"))
    assert response.status_code == 503
    import json
    body = json.loads(response.body)
    assert set(body) == {"detail", "code", "table"}
    assert body["code"] == "database_permission_denied" and body["table"] == "lab_results"
    assert "lab_results" in body["detail"] and body["detail"].endswith(PERMISSION_FIX)
    unnamed = json.loads(database_permission_response(Exception("permission denied")).body)
    assert unnamed["table"] is None and PERMISSION_FIX in unnamed["detail"]
    assert PERMISSION_FIX == "Apply supabase/migrations/20261006_coco_service_role_grants.sql in the Supabase SQL editor."


# --- exception handlers on a tiny app ------------------------------------------------

class Item(BaseModel):
    n: int


def make_app(cors=False):
    app = FastAPI()
    if cors:
        app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
    register_db_error_handlers(app)

    @app.get("/denied")
    def denied_route():
        raise denied("sleep_logs")

    @app.get("/other")
    def other_route():
        raise other()

    @app.get("/http")
    def http_route():
        raise HTTPException(status_code=418, detail="teapot")

    @app.post("/item")
    def item_route(item: Item):
        return item

    @app.get("/boom")
    def boom_route():
        raise RuntimeError("plain bug")

    return app


def test_permission_errors_become_a_clean_503():
    response = TestClient(make_app()).get("/denied")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "database_permission_denied" and body["table"] == "sleep_logs"
    assert "sleep_logs" in body["detail"] and PERMISSION_FIX in body["detail"]


def test_other_database_errors_become_a_generic_500_without_internals():
    response = TestClient(make_app()).get("/other")
    assert response.status_code == 500
    assert response.json() == {"detail": "Database error", "code": "database_error"}
    assert "boom" not in response.text and "secret" not in response.text


def test_existing_http_and_validation_handlers_still_work():
    client = TestClient(make_app(), raise_server_exceptions=False)
    assert client.get("/http").status_code == 418 and client.get("/http").json() == {"detail": "teapot"}
    assert client.get("/nope").status_code == 404
    invalid = client.post("/item", json={"n": "x"})
    assert invalid.status_code == 422 and isinstance(invalid.json()["detail"], list)
    assert client.post("/item", json={"n": 3}).json() == {"n": 3}
    assert client.get("/boom").status_code == 500  # unrelated exceptions are left alone


def test_handled_database_errors_carry_cors_headers_so_the_browser_can_read_them():
    client = TestClient(make_app(cors=True))
    for path, status in (("/denied", 503), ("/other", 500)):
        response = client.get(path, headers={"Origin": "http://localhost:3000"})
        assert response.status_code == status
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_the_handler_survives_a_failing_logger(monkeypatch):
    import logging_util

    def broken(*_a, **_k):
        raise RuntimeError("logger down")

    monkeypatch.setattr(logging_util.logger, "error", broken)
    assert TestClient(make_app()).get("/other").status_code == 500


# --- probe_database ------------------------------------------------------------------

class ProbeDB:
    def __init__(self, errors=None, rows=None):
        self.errors, self.rows, self.probed, self.selects = errors or {}, rows or [{"id": "secret-id", "email": "a@b.c"}], [], []

    def table(self, name):
        db, state = self, {"name": name}

        class Q:
            def select(self, *cols):
                db.selects.append((name, cols))
                return self

            def limit(self, n):
                state["limit"] = n
                return self

            def execute(self):
                db.probed.append(name)
                if name in db.errors:
                    raise db.errors[name]
                return SimpleNamespace(data=db.rows)

        return Q()


@pytest.fixture(autouse=True)
def _fresh_cache():
    reset_probe_cache()
    yield
    reset_probe_cache()


def test_probe_ok():
    result = probe_database(ProbeDB())
    assert result == {"database": "ok", "denied": [], "accessible": list(PROBE_TABLES), "compat_mode": False}


def test_probe_permission_denied_is_compat_mode():
    db = ProbeDB({"profiles": denied("profiles"), "sleep_logs": denied(), "health_events": denied("health_events")})
    result = probe_database(db)
    assert result["database"] == "permission_denied" and result["compat_mode"] is True
    assert result["denied"] == ["profiles", "sleep_logs", "health_events"]
    assert result["accessible"] == ["extracted_health_events", "chat_messages"]


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), ConnectionError("down"),
                                   TimeoutError("t"), OSError("no route"), other(code="503", message="upstream")])
def test_probe_network_errors_are_unreachable_and_stop_early(error):
    db = ProbeDB({"profiles": error})
    result = probe_database(db)
    assert result["database"] == "unreachable" and result["compat_mode"] is False
    assert db.probed == ["profiles"]  # one timeout is enough


def test_probe_unreachable_wins_over_earlier_denials():
    db = ProbeDB({"profiles": denied("profiles"), "sleep_logs": httpx.ConnectError("x")})
    result = probe_database(db)
    assert result["database"] == "unreachable" and result["compat_mode"] is False


def test_probe_unknown_for_other_errors_but_denied_is_more_actionable():
    assert probe_database(ProbeDB({"sleep_logs": other()}))["database"] == "unknown"
    reset_probe_cache()
    mixed = probe_database(ProbeDB({"sleep_logs": other(), "profiles": denied("profiles")}))
    assert mixed["database"] == "permission_denied" and mixed["accessible"] == ["health_events", "extracted_health_events", "chat_messages"]


def test_probe_never_raises_and_never_returns_row_data():
    assert probe_database(None)["database"] == "unknown"
    assert probe_database(object())["database"] == "unknown"
    result = probe_database(ProbeDB(), ttl=0)
    assert "secret-id" not in str(result) and "a@b.c" not in str(result)
    assert set(result) == {"database", "denied", "accessible", "compat_mode"}


def test_probe_selects_only_the_id_column_and_never_user_preferences():
    db = ProbeDB()
    probe_database(db)
    assert db.probed == list(PROBE_TABLES)
    assert all(cols == ("id",) for _, cols in db.selects)
    assert "user_preferences" not in PROBE_TABLES


def test_probe_is_cached_for_ttl_seconds(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(db_access.time, "monotonic", lambda: clock[0])
    db = ProbeDB()
    first = probe_database(db, ttl=30)
    clock[0] += 29
    probe_database(db, ttl=30)
    assert len(db.probed) == len(PROBE_TABLES)  # second call served from cache
    db.errors["profiles"] = denied("profiles")
    assert probe_database(db, ttl=30) == first  # still the cached answer
    clock[0] += 2  # now 31s old
    refreshed = probe_database(db, ttl=30)
    assert refreshed["database"] == "permission_denied" and len(db.probed) == 2 * len(PROBE_TABLES)


def test_probe_ttl_zero_always_probes_and_other_clients_do_not_share_the_cache():
    db = ProbeDB()
    probe_database(db, ttl=0)
    probe_database(db, ttl=0)
    assert len(db.probed) == 2 * len(PROBE_TABLES)
    other_db = ProbeDB({"profiles": denied("profiles")})
    assert probe_database(db)["database"] == "ok"
    assert probe_database(other_db)["database"] == "permission_denied"


def test_probe_returns_copies_so_callers_cannot_poison_the_cache():
    db = ProbeDB()
    result = probe_database(db)
    result["accessible"].clear()
    result["database"] = "tampered"
    again = probe_database(db)
    assert again["database"] == "ok" and again["accessible"] == list(PROBE_TABLES)


def test_probe_failures_are_cached_too_so_a_dead_database_is_not_hammered():
    db = ProbeDB({"profiles": httpx.ConnectError("x")})
    probe_database(db)
    probe_database(db)
    assert db.probed == ["profiles"]
