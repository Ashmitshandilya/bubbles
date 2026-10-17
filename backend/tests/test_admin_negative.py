"""Negative tests for the admin Live and Overall pages and the rollups: who is refused, what bad input does, what never leaks."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

import ops_metrics
import ops_rollups
import ops_snapshots
import ops_telemetry
from test_admin_overall import T0, ev, opsdb, stored_scenario  # noqa: F401
from test_admin_portal import ADMIN, admin_env, bearer, jwt  # noqa: F401
from test_chat_http_flow import USER, env  # noqa: F401

PATHS = ["/admin/live", "/admin/live?since=0", "/admin/events/live?after=5", "/admin/overall", "/admin/overall?range=all"]
NOW = T0 + timedelta(hours=3)


# ---- the guard: the project keeps one answer for everyone refused (a byte-identical 404, DESIGN.md), never a 401 or 403 ------------

def test_every_new_path_refuses_anonymous_ordinary_forged_and_expired_callers_alike(admin_env):
    c, t = admin_env.client, admin_env.tokens
    unknown = c.get("/no-such-route-anywhere")
    refused = [
        {},                                                   # no token
        {"Authorization": "Bearer"},                          # empty bearer
        {"Authorization": "Basic abc"},                       # wrong scheme
        bearer("a.b.c"), bearer("not-a-jwt"), bearer(t.admin + "tampered"),   # forged
        bearer(t.user),                                       # a signed-in ordinary person
        bearer(t.aal1),                                       # the admin without the second step
        bearer(jwt(exp_in=-60)),                              # expired and unknown to the sign-in service
    ]
    for path in PATHS:
        for headers in refused:
            res = c.get(path, headers=headers)
            assert res.status_code == 404 and res.content == unknown.content, (path, headers)
    assert all(c.get(p, headers=bearer(t.admin)).status_code == 200 for p in PATHS)


def test_other_methods_on_the_new_paths_are_refused_the_same_way(admin_env):
    c, t = admin_env.client, admin_env.tokens
    unknown = c.get("/no-such-route-anywhere")
    for method in ("post", "put", "delete", "patch"):
        for path in ("/admin/live", "/admin/overall"):
            for headers in ({}, bearer(t.user)):
                res = getattr(c, method)(path, headers=headers)
                assert res.status_code == 404 and res.content == unknown.content


def test_an_admin_token_the_sign_in_service_rejects_as_expired_gets_the_same_404(admin_env):
    # Expiry is decided by Supabase (auth.get_user), not by the app; the gate must turn that refusal into the ordinary 404.
    from fastapi import HTTPException
    expired = jwt(exp_in=-60)
    original = admin_env.main._verify_token

    def verify(token):
        if token == expired:
            raise HTTPException(status_code=401, detail="token is expired")
        return original(token)

    admin_env.main._verify_token = verify
    try:
        unknown = admin_env.client.get("/no-such-route-anywhere")
        res = admin_env.client.get("/admin/overall", headers=bearer(expired))
    finally:
        admin_env.main._verify_token = original
    assert res.status_code == 404 and res.content == unknown.content


def test_not_being_on_the_list_is_enough_to_be_refused_even_with_a_valid_two_step_token(admin_env, monkeypatch):
    monkeypatch.setenv("BUBBLES_ADMIN_USER_IDS", "bbbbbbbb-0000-0000-0000-00000000000b")
    for path in PATHS:
        assert admin_env.client.get(path, headers=bearer(admin_env.tokens.admin)).status_code == 404


# ---- bad query input ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("query", ["range=", "range=2h", "range=ALL", "range=all%20", "range=../../etc", "range=1h;drop", "range=" + "9" * 500])
def test_overall_rejects_bad_windows(admin_env, query):
    res = admin_env.client.get(f"/admin/overall?{query}", headers=bearer(admin_env.tokens.admin))
    assert res.status_code == 422


@pytest.mark.parametrize("query", ["after=-1", "after=abc", "after=1.5", "since=-3", "process_started_at=" + "x" * 500])
def test_live_rejects_bad_cursors(admin_env, query):
    assert admin_env.client.get(f"/admin/live?{query}", headers=bearer(admin_env.tokens.admin)).status_code == 422


def test_a_cursor_far_ahead_or_a_stale_process_id_returns_a_sane_answer(admin_env):
    h = bearer(admin_env.tokens.admin)
    ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1.0)
    ahead = admin_env.client.get("/admin/live?after=1000000", headers=h).json()
    assert ahead["status"] == "success" and ahead["events"] == [] and ahead["next_cursor"] == 1000000
    stale = admin_env.client.get("/admin/live?after=1000000&process_started_at=2000-01-01", headers=h).json()
    assert stale["restarted"] is True and stale["events"]   # a restarted server: start again from what is in memory


def test_live_on_an_empty_ring_is_an_empty_list_not_an_error(admin_env):
    ops_telemetry.reset_for_tests()
    body = admin_env.client.get("/admin/live", headers=bearer(admin_env.tokens.admin)).json()
    assert body["events"] == [] and body["next_cursor"] == 0


def test_a_huge_ring_is_returned_in_a_bounded_page(admin_env):
    for _ in range(ops_telemetry.RING_SIZE + 500):
        ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1.0)
    body = admin_env.client.get("/admin/live", headers=bearer(admin_env.tokens.admin)).json()
    assert 0 < len(body["events"]) <= 500
    assert len(ops_telemetry._ring) == ops_telemetry.RING_SIZE


# ---- no content, no person ---------------------------------------------------------------------------------------------------

def test_the_overall_answer_has_no_user_id_message_or_free_text(admin_env, opsdb):
    stored_scenario(opsdb)
    opsdb.tables["profiles"] = [{"id": USER, "created_at": NOW.isoformat(), "full_name": "Asha Rao", "email": "asha@example.com"}]
    opsdb.tables["chat_messages"] = [{"user_id": USER, "role": "user", "content": "my chest hurts", "created_at": NOW.isoformat()}]
    opsdb.tables["consent_events"] = [{"user_hash": "deadbeefhash", "purpose": "ai_chat_processing", "granted": True,
                                       "text_version": "v1", "created_at": NOW.isoformat()}]
    h = bearer(admin_env.tokens.admin)
    out = "".join(admin_env.client.get(f"/admin/overall?range={r}", headers=h).text for r in ("1h", "24h", "7d", "30d", "all"))
    for secret in (USER, "Asha", "asha@example.com", "chest", "deadbeefhash", '"uid"'):
        assert secret not in out, secret


def test_the_uid_exists_only_on_api_and_ai_attempt_events_and_never_in_the_queue_or_note():
    token = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.bind_user(USER)
        for kind, data in (("api", {"route": "/x", "status": 200}), ("ai_attempt", {"provider": "Groq", "outcome": "success"}),
                           ("ai_reply", {"outcome": "answered"}), ("error", {"category": "database"}), ("audit", {"action": "a"}),
                           ("funnel", {"step": "core"}), ("client", {"code": "render_error"})):
            ops_telemetry.record(kind, **data)
        assert "_uid" not in ops_telemetry.current_note() and USER not in json.dumps(ops_telemetry.current_note())
    finally:
        ops_telemetry.end_request(tuple(token))
    assert {e["kind"] for e in ops_telemetry.recent(0, 50, with_uid=True) if "uid" in e} == {"api", "ai_attempt"}
    assert USER not in json.dumps(list(ops_telemetry._queue))


@pytest.mark.parametrize("bad", [None, "", 5, ["a"], "../../x", "a" * 200, "u1;drop table", "<script>", "short"])
def test_a_value_that_is_not_an_id_is_never_kept_as_a_uid(bad):
    token = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.bind_user(bad)
        ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1.0)
    finally:
        ops_telemetry.end_request(tuple(token))
    assert all("uid" not in e for e in ops_telemetry.recent(0, 10, with_uid=True))


def test_stage_fields_and_free_text_cannot_be_smuggled_in_through_the_telemetry_calls():
    ops_telemetry.record("api", method="POST", route="/chat", status=200, latency_ms=5.0, stage_ai_ms="my chest hurts", stage_pre_ms=True,
                         stage_ctx_ms=-1, stage_rag_ms=float("inf"), stage_post_ms=10 ** 9, message="hello", uid="u1", prompt="x")
    data = ops_telemetry.recent(0, 5)[0]["data"]
    assert not {"message", "uid", "prompt"} & set(data) and not [k for k in data if k.startswith("stage_")]


# ---- counters: malformed, foreign and extreme rows ---------------------------------------------------------------------------

def test_malformed_rows_and_rows_of_other_kinds_are_skipped_not_counted_and_not_fatal():
    day = "2026-10-14T09:00:00Z"
    bad = [None, "x", 5, [], {}, {"at": "2026-10-14", "kind": "api"}, {"at": day, "kind": "api", "data": None},
           {"at": day, "kind": "api", "data": "text"}, {"at": None, "kind": "api", "data": {"status": 200}},
           {"at": day, "kind": "audit", "data": {"action": "setting_changed", "actor": ADMIN}},
           {"at": day, "kind": "mystery", "data": {"x": 1}},
           {"at": day, "kind": "api", "data": {"status": "abc", "latency_ms": "slow", "route": 5}},
           {"at": day, "kind": "api", "data": {"status": True, "latency_ms": float("nan")}},
           {"at": day, "kind": "api", "data": {"status": 200, "latency_ms": -5, "route": "/chat", "method": "POST"}},
           {"at": day, "kind": "ai_attempt", "data": {"provider": "G", "model": "m", "input_tokens": float("inf"), "output_tokens": "9"}}]
    c = ops_rollups.count_events(bad)
    t = ops_rollups.totals(c)
    assert not any(dim in t for dim in ("audit", "mystery"))
    assert t["req"]["total"] == 3                      # the three api rows whose data is an object and whose day is usable
    assert not t.get("hist.api") and not t.get("tokens_in") and not t.get("tokens_out")
    assert all(isinstance(n, int) and n > 0 for n in c.values())


def test_overall_view_on_no_events_is_zeros_and_none_not_a_crash():
    view = ops_metrics.overall_view(ops_rollups.count_events([]), ["pre", "ctx", "rag", "ai", "post"], ops_telemetry.FUNNEL_STEPS)
    assert view["totals"] == {"requests": 0, "chats": 0, "server_errors": 0, "onboarding_completed": 0}
    assert view["providers"] == [] and view["ai"]["fallback_rate"] is None and view["latency"]["chat"] == {"p50_ms": None, "p95_ms": None}
    assert [f["count"] for f in view["funnel"]] == [0] * len(ops_telemetry.FUNNEL_STEPS)


def test_the_overall_endpoint_on_an_empty_database_answers_for_every_range(admin_env, opsdb):
    ops_telemetry.reset_for_tests()
    for rng in ("1h", "24h", "7d", "30d", "all"):
        body = admin_env.client.get(f"/admin/overall?range={rng}", headers=bearer(admin_env.tokens.admin)).json()
        assert body["status"] == "success" and body["totals"]["requests"] == 0, rng


def test_a_big_event_table_is_counted_with_integers(opsdb):
    opsdb.tables["bubbles_ops_events"] = [ev("api", i % 50, f"r{i:07d}", method="GET", route="/health", status=200, latency_ms=float(i % 900))
                                          for i in range(2500)]
    got = ops_rollups.collect(opsdb, "30d", now=T0 + timedelta(hours=1))
    assert ops_rollups.totals(got["counters"])["req"]["total"] == 2500 and isinstance(got["capped"], bool)


def test_percentiles_with_one_sample_and_with_nothing():
    assert ops_rollups.percentile({"100": 1}, 95) == 100.0
    assert ops_rollups.percentile({}, 95) is None and ops_rollups.percentile({"inf": 3}, 50) == float(ops_rollups.EDGES[-1])


# ---- rollups: idempotent, safe on empty and failing databases ----------------------------------------------------------------

def _counts(db):
    return {(r["day"], r["dimension"], r["key"]): r["count"] for r in db.tables.get("ops_rollups_daily", [])}


def test_running_the_rollup_twice_changes_nothing(opsdb):
    stored_scenario(opsdb)
    assert ops_rollups.run_rollups(opsdb, now=NOW)["status"] == "ok"
    once = _counts(opsdb)
    for _ in range(3):
        assert ops_rollups.run_rollups(opsdb, now=NOW)["status"] == "idle"
    assert _counts(opsdb) == once
    assert once[("2026-10-14", "req", "total")] == 4


def test_a_clock_that_goes_backwards_does_not_recount(opsdb):
    stored_scenario(opsdb)
    ops_rollups.run_rollups(opsdb, now=NOW)
    once = _counts(opsdb)
    assert ops_rollups.run_rollups(opsdb, now=T0 - timedelta(days=2))["status"] == "idle"
    assert _counts(opsdb) == once


def test_run_rollups_on_an_empty_events_table_is_idle_and_writes_nothing(opsdb):
    opsdb.tables["bubbles_ops_events"] = []
    assert ops_rollups.run_rollups(opsdb, now=NOW) == {"status": "idle", "through": None}
    assert not opsdb.tables.get("ops_rollups_daily")


def test_a_failed_write_does_not_move_the_watermark_so_the_hours_are_counted_next_time(opsdb):
    stored_scenario(opsdb)
    real = opsdb.table

    class Failing:
        def __init__(self, q):
            self.q = q

        def __getattr__(self, name):
            return getattr(self.q, name)

        def upsert(self, *a, **k):
            raise RuntimeError("write failed")

    opsdb.table = lambda name: Failing(real(name)) if name == "ops_rollups_daily" else real(name)
    assert ops_rollups.run_rollups(opsdb, now=NOW)["status"] == "error"
    assert not _counts(opsdb)
    opsdb.table = real
    assert ops_rollups.run_rollups(opsdb, now=NOW)["status"] == "ok" and _counts(opsdb)[("2026-10-14", "req", "total")] == 4


@pytest.mark.parametrize("db", [None, object(), 5])
def test_run_rollups_never_raises_on_a_broken_database(db, monkeypatch):
    def broken():
        raise RuntimeError("no database")

    monkeypatch.setattr(ops_telemetry, "_db", broken)
    assert ops_rollups.run_rollups(db, now=NOW)["status"] == "error"


def test_the_rollups_hold_counts_only_no_ids_and_no_text(opsdb):
    stored_scenario(opsdb)
    opsdb.tables["bubbles_ops_events"].append(ev("api", 5, "e0000001", method="GET", route="/health", status=200, latency_ms=3.0, uid=USER,
                                                 message="my chest hurts"))
    ops_rollups.run_rollups(opsdb, now=NOW)
    blob = json.dumps(opsdb.tables["ops_rollups_daily"])
    assert USER not in blob and "chest" not in blob
    assert all(isinstance(r["count"], int) and set(r) == {"day", "dimension", "key", "count"} for r in opsdb.tables["ops_rollups_daily"])


# ---- snapshots on bad data ---------------------------------------------------------------------------------------------------

def test_snapshots_survive_empty_and_malformed_tables(opsdb):
    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    u = ops_snapshots.users(opsdb, now)
    assert (u["dau"], u["wau"], u["mau"], u["signups_total"]) == (0, 0, 0, 0)
    opsdb.tables["profiles"] = [{"id": "u1", "created_at": "not a date"}, {"id": None, "created_at": None}, {}]
    opsdb.tables["chat_messages"] = [{"user_id": "u1", "role": "user", "created_at": "garbage"}, {"role": "user"}]
    u = ops_snapshots.users(opsdb, now)
    assert all(isinstance(u[k], int) for k in ("dau", "wau", "mau", "signups_total"))
