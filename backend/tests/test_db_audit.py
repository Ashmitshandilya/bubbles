"""B1: the N+1 fixes and the migration register. Each is checked with and without the new SQL objects (feature-detect fallback)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chat_counts
import schema_status
from fake_db import FakeAPIError, FakeDB, permission_denied
from health_logs import COMPAT_TABLE, _has_compat, build_router
from test_admin_portal import admin_env, bearer  # noqa: F401  (an app with a two-step admin)
from test_chat_http_flow import H, USER, env  # noqa: F401  (the same stateful chat app)

import pytest


class CountingDB(FakeDB):
    def __init__(self):
        super().__init__()
        self.reads: list[str] = []

    def table(self, name):
        self.reads.append(name)
        return super().table(name)


def make_conversations(db, n=4, uid=USER):
    db.tables["chat_conversations"] = [{"id": f"c{i}", "user_id": uid, "title": f"t{i}", "created_at": f"2026-10-1{i}T00:00:00+00:00",
                                        "updated_at": f"2026-10-1{i}T00:00:00+00:00"} for i in range(n)]
    db.tables["chat_messages"] = [{"id": f"m{i}-{j}", "user_id": uid, "conversation_id": f"c{i}", "role": "user", "content": "x"}
                                  for i in range(n) for j in range(i)]   # c0 has none, c3 has three


@pytest.mark.parametrize("function_installed", [True, False], ids=["with_function", "without_function"])
def test_chat_history_counts_do_not_loop_when_the_function_exists_and_still_work_without_it(env, function_installed):
    make_conversations(env.db)
    if not function_installed:
        env.db.missing_functions.add("bubbles_chat_counts")
    body = env.client.get("/chat/history?limit=10", headers=H).json()
    assert {c["id"]: c["message_count"] for c in body["conversations"]} == {"c0": 0, "c1": 1, "c2": 2, "c3": 3}
    assert env.db.rpc_calls == (1 if function_installed else 0)


def test_message_counts_of_nobody_is_empty_and_never_asks():
    db = FakeDB()
    assert chat_counts.message_counts(db, USER, []) == {} and db.rpc_calls == 0


def test_health_summary_asks_for_compat_rows_once_then_remembers_there_are_none():
    _has_compat.invalidate(USER)
    db = CountingDB()
    db.tables["sleep_logs"] = [{"id": "s1", "user_id": USER, "created_at": "2026-10-10T08:00:00+00:00"}]
    app = FastAPI()
    app.include_router(build_router(lambda _a: type("U", (), {"id": USER})(), db))
    client = TestClient(app)
    first = client.get("/health/summary").json()
    assert first["categories_with_data"] == 1 and first["total_entries"] == 1
    assert db.reads.count(COMPAT_TABLE) == 1
    second = client.get("/health/summary").json()
    assert second == first and db.reads.count(COMPAT_TABLE) == 1   # not read again


def test_a_compat_save_is_seen_at_once_even_after_the_flag_said_none():
    _has_compat.invalidate(USER)
    db = FakeDB()
    db.failures["sleep_logs"] = permission_denied("sleep_logs")
    app = FastAPI()
    app.include_router(build_router(lambda _a: type("U", (), {"id": USER})(), db))
    client = TestClient(app)
    assert client.get("/health/sleep").json()["entries"] == []
    _has_compat.put(USER, False)   # what a read of a person with no compat entries leaves behind
    saved = client.post("/health/sleep", json={"date": "2026-10-14", "duration": 7, "quality": 4})
    assert saved.status_code == 201 and saved.json()["store"] == "compat"
    assert len(client.get("/health/sleep").json()["entries"]) == 1


def test_a_refused_primary_table_never_trusts_the_no_compat_flag():
    _has_compat.put(USER, False)
    db = FakeDB()
    db.failures["sleep_logs"] = permission_denied("sleep_logs")
    db.tables[COMPAT_TABLE] = [{"id": "e1", "user_id": USER, "event_type": "sleep", "extraction_status": "confirmed", "created_at": "2026-10-10T08:00:00+00:00",
                                "extracted_data": {"_prov": {"store": "compat", "domain": "sleep"}, "_row": {"sleep_date": "2026-10-09", "duration_minutes": 400}}}]
    app = FastAPI()
    app.include_router(build_router(lambda _a: type("U", (), {"id": USER})(), db))
    assert len(TestClient(app).get("/health/sleep").json()["entries"]) == 1


def test_schema_report_lists_what_is_missing_and_survives_a_missing_register():
    schema_status._cache.clear()
    db = FakeDB()
    db.failures[schema_status.REGISTER] = FakeAPIError('relation "public.bubbles_schema_migrations" does not exist', "42P01")
    out = schema_status.report(db)
    assert out["registered"] is False and {m["name"] for m in out["missing"]} == set(schema_status.KNOWN)
    schema_status._cache.clear()
    db = FakeDB()
    db.tables[schema_status.REGISTER] = [{"name": "20261016_bubbles_indexes_v2"}, {"name": "something_else"}]
    out = schema_status.report(db)
    assert out["registered"] is True and "20261016_bubbles_indexes_v2" in out["applied"]
    assert "20261016_bubbles_indexes_v2" not in {m["name"] for m in out["missing"]} and "20261016_bubbles_consent_ledger" in {m["name"] for m in out["missing"]}
    schema_status._cache.clear()


def test_every_known_migration_has_a_file_and_an_undo_file():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "supabase"
    for name in schema_status.KNOWN:
        if name.startswith(("20261016", "20261102")):
            assert (root / "migrations" / f"{name}.sql").exists(), name
            assert (root / "undo" / f"{name}_undo.sql").exists(), name
    for sql in (root / "migrations").glob("20261016_*.sql"):
        text = sql.read_text(encoding="utf-8")
        assert sql.stem in text and "bubbles_schema_migrations" in text, f"{sql.name} must register itself"
        assert "begin;" in text and "commit;" in text


def test_the_admin_schema_route_is_not_open_to_a_plain_signed_in_user(env):
    res = env.client.get("/admin/schema", headers=H)
    assert res.status_code == 404
    assert env.client.get("/admin/schema").status_code == 404


def test_the_admin_schema_route_answers_for_an_admin(admin_env):
    schema_status._cache.clear()
    res = admin_env.client.get("/admin/schema", headers=bearer(admin_env.tokens.admin))
    assert res.status_code == 200 and res.json()["status"] == "success" and "missing" in res.json()
    assert admin_env.client.get("/admin/schema", headers=H).status_code == 404
    assert "/admin/schema" not in admin_env.client.get("/openapi.json").text
    schema_status._cache.clear()
