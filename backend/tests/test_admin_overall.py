"""Admin Live and Overall pages: the one named uid exception, stage fields, funnel and crash enums, rollups that survive a
restart, integer-only snapshots and the unchanged 404 for everyone but the owner."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ops_metrics
import ops_rollups
import consent
import doc_store
import ops_snapshots
import push_fcm
import ops_telemetry
from fake_db import FakeDB, Query, Result, _get
from test_admin_portal import ADMIN, admin_env, bearer  # noqa: F401  (fixture and helpers)
from test_chat_http_flow import USER, env, send  # noqa: F401


class OpsQuery(Query):
    """FakeDB's query plus what the ops readers use: lt, range and upsert with on_conflict."""
    _range = None
    _conflict: tuple[str, ...] = ()

    def lt(self, col, val):
        self.filters.append(lambda r, c=col, v=val: _get(r, c) is not None and str(_get(r, c)) < str(v))
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def upsert(self, payload, on_conflict=None, **_):
        self.op, self.payload, self._conflict = "upsert", payload, tuple((on_conflict or "").split(","))
        return self

    def execute(self):
        if self.op == "upsert":
            rows = self.db.tables.setdefault(self.table, [])
            for item in self.payload:
                same = [r for r in rows if all(r.get(k) == item.get(k) for k in self._conflict)]
                if same:
                    same[0].update(item)
                else:
                    rows.append(dict(item))
            return Result(list(self.payload))
        res = super().execute()
        if self._range:
            res.data = res.data[self._range[0]: self._range[1] + 1]
        return res


class OpsDB(FakeDB):
    def table(self, name):
        return OpsQuery(self, name)


T0 = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)


def ev(kind, minutes=0, rid=None, **data):
    return {"at": (T0 + timedelta(minutes=minutes)).isoformat(), "kind": kind, "request_id": rid, "data": data}


def stored_scenario(db):
    db.tables["bubbles_ops_events"] = [
        ev("api", 0, "a0000001", method="POST", route="/chat", status=200, latency_ms=900.0, route_kind="ai", ai_called=True,
           safety_level="GREEN", stage_pre_ms=120.0, stage_ai_ms=700.0),
        ev("api", 1, "a0000002", method="POST", route="/chat", status=200, latency_ms=40.0, route_kind="emergency", ai_called=False,
           safety_level="RED"),
        ev("api", 2, "a0000003", method="POST", route="/chat", status=200, latency_ms=20.0, route_kind="consent_needed", ai_called=False,
           safety_level="GREEN"),
        ev("api", 3, "a0000004", method="GET", route="/health/{slug}", status=500, latency_ms=70.0),
        ev("ai_attempt", 0, "a0000001", provider="Gemini", model="g", position=1, outcome="success", latency_ms=650.0,
           input_tokens=1000, output_tokens=100),
        ev("ai_reply", 0, "a0000001", provider="Gemini", model="g", outcome="answered", attempts=1, fallback_used=False, total_ms=700.0),
        ev("funnel", 4, None, step="core"),
        ev("funnel", 5, None, step="completed"),
        ev("client", 6, None, code="render_error"),
        ev("error", 3, "a0000004", category="database", component="API", route="/health/{slug}"),
    ]


@pytest.fixture()
def opsdb(monkeypatch):
    db = OpsDB({"tok": USER})
    monkeypatch.setattr(ops_telemetry, "_db", lambda: db)
    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    ops_rollups.reset_for_tests()
    ops_snapshots._cache.clear()
    return db


# ---- the named uid exception -------------------------------------------------------------------------------------------------

def test_uid_is_in_the_live_endpoint_only_and_never_stored_or_in_other_readers(admin_env, monkeypatch):
    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    c, h = admin_env.client, bearer(admin_env.tokens.admin)
    assert send(admin_env, "I have been feeling really tired this week and I do not know why").status_code == 200
    live = c.get("/admin/events/live?after=0", headers=h).json()
    api = [e for e in live["events"] if e["kind"] == "api" and e["data"]["route"] == "/chat"]
    assert api and api[0]["uid"] == USER and api[0]["feature"] == "Chat"
    assert "uid" not in json.dumps([e["data"] for e in live["events"]])
    # the same events through every other reader and the write queue carry no uid
    other = json.dumps([c.get(p, headers=h).json() for p in ("/admin/events?range=1h", "/admin/overview?range=1h", "/admin/overall?range=1h")])
    assert USER not in other
    assert USER not in json.dumps(ops_telemetry.recent(0, 5000)) and USER not in json.dumps(list(ops_telemetry._queue))
    assert USER not in json.dumps(ops_telemetry.memory_events(datetime.now(timezone.utc) - timedelta(hours=1)))
    # nothing the flusher would write holds it either
    wrote = []
    class _T:
        def insert(self, rows):
            wrote.extend(rows)
            return self

        def execute(self):
            return None

    monkeypatch.setattr(ops_telemetry, "_db", lambda: type("D", (), {"table": staticmethod(lambda name: _T())})())
    ops_telemetry.flush_once()
    assert wrote and USER not in json.dumps(wrote)


def test_the_live_alias_and_new_endpoints_are_the_same_404_for_everyone_but_the_admin(admin_env):
    c, t = admin_env.client, admin_env.tokens
    unknown = c.get("/no-such-route-anywhere")
    for path in ("/admin/live", "/admin/events/live", "/admin/overall", "/admin/overall?range=all"):
        for headers in ({}, bearer("junk"), bearer(t.user), bearer(t.aal1)):
            res = c.get(path, headers=headers)
            assert res.status_code == 404 and res.content == unknown.content, (path, headers)
    assert c.get("/admin/live", headers=bearer(t.admin)).status_code == 200
    assert c.get("/admin/overall?range=nope", headers=bearer(t.admin)).status_code == 422


def test_ai_attempts_carry_the_uid_in_the_ring_too():
    tokens = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.bind_user(USER)
        ops_telemetry.record("ai_attempt", provider="Groq", model="m", position=2, outcome="success", latency_ms=5.0)
        ops_telemetry.record("ai_reply", provider="Groq", model="m", outcome="answered", total_ms=5.0)
    finally:
        ops_telemetry.end_request(tuple(tokens))
    live = {e["kind"]: e for e in ops_telemetry.recent(0, 10, with_uid=True)}
    assert live["ai_attempt"]["uid"] == USER and "uid" not in live["ai_reply"]
    assert all("uid" not in e for e in ops_telemetry.recent(0, 10))


def test_a_made_up_uid_is_ignored():
    tokens = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.bind_user("x; drop table")
        ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1.0)
        assert "uid" not in ops_telemetry.recent(0, 10, with_uid=True)[0]
    finally:
        ops_telemetry.end_request(tuple(tokens))


# ---- fields ------------------------------------------------------------------------------------------------------------------

def test_stage_timings_are_numeric_only_and_noted_on_the_api_event():
    tokens = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.note(stage_pre_ms=12.34, stage_ctx_ms="slow", stage_rag_ms=True, stage_ai_ms=700, stage_post_ms=-5, stage_nope_ms=1)
        assert ops_telemetry.current_note() == {"stage_pre_ms": 12.3, "stage_ai_ms": 700.0}
        ops_telemetry.record("api", method="POST", route="/chat", status=200, latency_ms=900.0, stage_ctx_ms="chest pain", **ops_telemetry.current_note())
    finally:
        ops_telemetry.end_request(tuple(tokens))
    data = ops_telemetry.recent(0, 5)[0]["data"]
    assert data["stage_pre_ms"] == 12.3 and data["stage_ai_ms"] == 700.0 and "stage_ctx_ms" not in data
    assert set(ops_telemetry.STAGE_FIELDS) == {"stage_pre_ms", "stage_ctx_ms", "stage_rag_ms", "stage_ai_ms", "stage_post_ms"}
    assert set(ops_telemetry.STAGE_FIELDS) <= ops_telemetry.FIELDS["api"]


def test_funnel_and_client_events_take_fixed_words_only():
    ops_telemetry.funnel("completed")
    ops_telemetry.funnel("my back hurts")
    ops_telemetry.client("render_error")
    ops_telemetry.client("boom: chest pain")
    ops_telemetry.record("funnel", step="core", note="free text")
    got = [(e["kind"], e["data"]) for e in ops_telemetry.recent(0, 50)]
    assert got == [("funnel", {"step": "completed"}), ("client", {"code": "render_error"}), ("funnel", {"step": "core"})]


# ---- counters ----------------------------------------------------------------------------------------------------------------

def test_count_events_and_percentiles_from_buckets():
    events = [ev("api", i, f"r{i:07d}", method="POST", route="/chat", status=200, latency_ms=float(ms), route_kind="ai", ai_called=True,
                 safety_level="GREEN") for i, ms in enumerate([90, 100, 110, 4000])]
    c = ops_rollups.count_events(events)
    t = ops_rollups.totals(c)
    assert t["req"]["total"] == 4 and t["chat"]["total"] == 4 and t["safety"]["GREEN"] == 4 and t["route_kind"]["ai"] == 4
    assert ops_rollups.percentile(t["hist.chat"], 50) == 100.0 and ops_rollups.percentile(t["hist.chat"], 95) == 4800.0
    assert ops_rollups.percentile({}, 50) is None
    assert ops_rollups.bucket(999999) == "inf"


def test_overall_view_counts_rates_stages_funnel_and_cost(opsdb):
    stored_scenario(opsdb)
    rows = [{"at": e["at"], "kind": e["kind"], "request_id": e["request_id"], "data": e["data"]} for e in opsdb.tables["bubbles_ops_events"]]
    view = ops_metrics.overall_view(ops_rollups.count_events(rows), ["pre", "ctx", "rag", "ai", "post"], ops_telemetry.FUNNEL_STEPS)
    assert view["totals"] == {"requests": 4, "chats": 3, "server_errors": 1, "onboarding_completed": 1}
    ai = view["ai"]
    assert (ai["answered"], ai["degraded"], ai["fallback_used"]) == (1, 0, 0)
    assert ai["ai_share"] == round(1 / 3, 3) and ai["consent_needed"] == 1 and ai["consent_needed_rate"] == round(1 / 3, 3)
    assert ai["deterministic_share"] == round(1 / 3, 3)
    assert view["providers"][0]["cost"]["cost_usd"] == 0.0 and view["providers"][0]["cost"]["label"] == "free tier" and view["providers"][0]["tokens_in"] == 1000
    assert {s["stage"]: s["n"] for s in view["stages"]} == {"pre": 1, "ctx": 0, "rag": 0, "ai": 1, "post": 0}
    assert view["safety"]["totals"] == {"GREEN": 2, "RED": 1} and view["safety"]["per_day"][0]["RED"] == 1
    assert [f["count"] for f in view["funnel"]][:4] == [1, 0, 0, 1] and view["client_crashes"] == {"render_error": 1}
    assert {f["feature"] for f in view["features"]} >= {"Chat", "Trackers"}
    assert ops_metrics.model_cost("SomethingNew", "unknown", 1, 1)["cost_usd"] is None


# ---- rollups -----------------------------------------------------------------------------------------------------------------

def test_rollups_count_each_hour_once_and_survive_a_restart(opsdb):
    stored_scenario(opsdb)
    now = T0 + timedelta(hours=3)
    first = ops_rollups.run_rollups(opsdb, now=now)
    assert first["status"] == "ok" and first["hours"] == 3   # the 09, 10 and 11 o'clock hours; the current hour is not complete
    again = ops_rollups.run_rollups(opsdb, now=now)
    assert again["status"] == "idle"
    ops_telemetry.reset_for_tests()   # a restart: nothing in memory
    ops_rollups.reset_for_tests()
    opsdb.tables["bubbles_ops_events"].clear()   # and the raw rows pruned
    got = ops_rollups.collect(opsdb, "all", now=now)
    t = ops_rollups.totals(got["counters"])
    assert got["rollups"]["mode"] == "ok" and got["source"].startswith("rollups")
    assert t["req"]["total"] == 4 and t["chat"]["total"] == 3 and t["funnel"]["completed"] == 1
    # a later hour is added, not recounted
    opsdb.tables["bubbles_ops_events"].append(ev("api", 4 * 60, "b0000001", method="GET", route="/health", status=200, latency_ms=5.0))
    assert ops_rollups.run_rollups(opsdb, now=T0 + timedelta(hours=6))["status"] == "ok"
    assert ops_rollups.totals(ops_rollups.collect(opsdb, "all", now=T0 + timedelta(hours=6))["counters"])["req"]["total"] == 5


def test_a_range_adds_the_events_after_the_watermark(opsdb):
    stored_scenario(opsdb)
    ops_rollups.run_rollups(opsdb, now=T0 + timedelta(hours=2, minutes=40))   # through 11:00? no: through the 11:00 boundary
    opsdb.tables["bubbles_ops_events"].append(ev("api", 3 * 60 + 10, "c0000001", method="GET", route="/health", status=200, latency_ms=5.0))
    got = ops_rollups.collect(opsdb, "7d", now=T0 + timedelta(hours=3, minutes=20))
    assert ops_rollups.totals(got["counters"])["req"]["total"] == 5


def test_without_the_rollup_table_the_range_is_counted_from_raw_events_and_says_so(opsdb):
    stored_scenario(opsdb)
    opsdb.failures["ops_rollups_daily"] = Exception("PGRST205 Could not find the table 'public.ops_rollups_daily'")
    assert ops_rollups.run_rollups(opsdb, now=T0 + timedelta(hours=3)) == {"status": "not_set_up"}
    got = ops_rollups.collect(opsdb, "30d", now=T0 + timedelta(hours=3))
    assert got["rollups"]["mode"] == "not_set_up" and ops_rollups.totals(got["counters"])["req"]["total"] == 4


def test_run_rollups_never_raises_and_skips_when_events_are_only_in_memory(opsdb):
    stored_scenario(opsdb)
    opsdb.failures["bubbles_ops_events"] = Exception("boom")
    assert ops_rollups.run_rollups(opsdb, now=T0 + timedelta(hours=3))["status"] in {"skipped", "error"}
    assert ops_rollups.run_rollups(object(), now=T0)["status"] == "error"


# ---- snapshots ---------------------------------------------------------------------------------------------------------------

def test_snapshots_are_integers_only_and_hide_the_table_when_missing(opsdb):
    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    iso = lambda d: (now - timedelta(days=d)).isoformat()  # noqa: E731
    opsdb.tables["profiles"] = [{"id": "u1", "created_at": iso(20)}, {"id": "u2", "created_at": iso(10)}, {"id": "u3", "created_at": iso(0.5)}]
    opsdb.tables["chat_messages"] = [
        {"user_id": "u1", "role": "user", "created_at": iso(0.2)}, {"user_id": "u1", "role": "user", "created_at": iso(3)},
        {"user_id": "u2", "role": "user", "created_at": iso(5)}, {"user_id": "u2", "role": "assistant", "created_at": iso(0.1)},
        {"user_id": "u3", "role": "user", "created_at": iso(0.4)}]
    tv = consent.PURPOSES["ai_chat_processing"]["text_version"]
    opsdb.tables["consent_events"] = [
        {"user_hash": "h1", "purpose": "ai_chat_processing", "granted": False, "text_version": tv, "created_at": iso(9)},
        {"user_hash": "h1", "purpose": "ai_chat_processing", "granted": True, "text_version": tv, "created_at": iso(2)},
        {"user_hash": "h2", "purpose": "ai_chat_processing", "granted": False, "text_version": tv, "created_at": iso(2)}]
    opsdb.tables["community_posts"] = [{"id": "p1", "status": "visible"}, {"id": "p2", "status": "held"}]
    u = ops_snapshots.users(opsdb, now)
    assert (u["dau"], u["wau"], u["mau"], u["signups_total"]) == (2, 3, 3, 3)
    assert u["signups"] == {"24h": 1, "7d": 1, "30d": 3}
    assert u["retention"]["d1"] == {"eligible": 2, "returned": 2, "rate": 1.0}
    assert u["retention"]["d7"]["eligible"] == 2 and u["retention"]["d7"]["returned"] == 1   # u1 on/after day 7; u2 last wrote on day 5
    rates = {r["purpose"]: r for r in ops_snapshots.consent_rates(opsdb)}
    assert (rates["ai_chat_processing"]["granted"], rates["ai_chat_processing"]["declined"], rates["ai_chat_processing"]["rate"]) == (1, 1, 0.5)
    assert "product_usage_metrics" not in rates   # not offered yet, so no rate to show
    assert ops_snapshots.community(opsdb) == {"visible": 1, "held": 1, "removed": 0}
    assert ops_snapshots.push(opsdb) == {"active_devices": 0}   # the real source is the signed push_device documents, so "none yet" is 0
    for uid, token in (("u1", "t" * 40), ("u1", "s" * 40), ("u2", "r" * 40)):
        push_fcm.register_device(opsdb, uid, token)
    opsdb.tables["health_events"].append({"user_id": "u3", "event_type": doc_store.EVENT_TYPE, "title": "push_device:x",
                                          "data": {"kind": "push_device", "key": "x", "payload": {"token": "q" * 40}, "version": 1, "sig": "forged"}})
    assert ops_snapshots.push(opsdb) == {"active_devices": 3}   # three real phones; the forged row does not count
    assert "u1" not in json.dumps([u, ops_snapshots.consent_rates(opsdb)])
    opsdb.failures["consent_events"] = Exception("PGRST205")
    assert ops_snapshots.consent_rates(opsdb) is None


# ---- the endpoint and the files ----------------------------------------------------------------------------------------------

def test_overall_endpoint_returns_counts_for_every_range(admin_env, opsdb):
    stored_scenario(opsdb)
    now = datetime.now(timezone.utc)
    opsdb.tables["bubbles_ops_events"].append(ev("api", 0, "d0000001", method="GET", route="/health", status=200, latency_ms=5.0))
    opsdb.tables["bubbles_ops_events"][-1]["at"] = now.isoformat()
    h = bearer(admin_env.tokens.admin)
    for rng in ("1h", "24h", "7d", "30d", "all"):
        body = admin_env.client.get(f"/admin/overall?range={rng}", headers=h).json()
        assert body["status"] == "success" and body["range"] == rng
        assert {"totals", "ai", "providers", "stages", "safety", "funnel", "features", "users", "consent", "rollups", "latency"} <= set(body)
    assert admin_env.client.get("/admin/overall?range=1h", headers=h).json()["totals"]["requests"] >= 1


def test_migrations_are_idempotent_locked_down_and_have_undo_files():
    root = Path(__file__).resolve().parents[2] / "supabase"
    for name in ("20261016_bubbles_ops_rollups", "20261016_bubbles_ops_funnel"):
        sql = (root / "migrations" / f"{name}.sql").read_text(encoding="utf-8").lower()
        undo = (root / "undo" / f"{name}_undo.sql").read_text(encoding="utf-8").lower()
        assert "begin;" in sql and "commit;" in sql and "begin;" in undo and "commit;" in undo
        assert not [line for line in sql.splitlines() if line.startswith("grant") and ("anon" in line or "authenticated" in line)]
        assert "create policy" not in sql
    rollups = (root / "migrations" / "20261016_bubbles_ops_rollups.sql").read_text(encoding="utf-8").lower()
    assert "create table if not exists public.ops_rollups_daily" in rollups
    assert "enable row level security" in rollups and "grant select, insert, update on table public.ops_rollups_daily to service_role" in rollups
