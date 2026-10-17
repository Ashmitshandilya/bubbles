"""Aggregate-only tracking: stage numbers, setup funnel, app problem codes, cost at read time, active-people counts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import ops_metrics as M
import ops_telemetry
import ops_usage
from fake_db import FakeDB
from test_admin_portal import ADMIN, _events, admin_env, bearer, env  # noqa: F401  (fixtures)
from test_ops_metrics import T0, ev


@pytest.fixture(autouse=True)
def _clean_ring():
    ops_telemetry._ring.clear()
    ops_telemetry._queue.clear()
    ops_telemetry.status["new_kinds"] = "unknown"
    yield


def _api(seconds, **data):
    return ev("api", seconds, route=data.pop("route", "/chat"), status=data.pop("status", 200), latency_ms=100.0, **data)


def test_usage_summary_counts_the_chat_mix_the_rates_and_the_funnel():
    events = [
        _api(1, route_kind="ai", ai_called=True, safety_level="GREEN"),
        _api(2, route_kind="ai", ai_called=True, safety_level="AMBER"),
        _api(3, route_kind="emergency", ai_called=False, safety_level="RED"),
        _api(4, route_kind="consent_needed", ai_called=False, safety_level="GREEN"),
        _api(5, route="/chat/stream", route_kind="daily_log", ai_called=False, safety_level="GREEN"),
        _api(6, route="/health/sleep"), _api(7, route="/health/sleep"), _api(8, route="/health/sleep", status=500),
        ev("ai_reply", 1, "a" * 8, provider="Gemini", model="gemini-3-flash-preview", outcome="answered", fallback_used=False, attempts=1, total_ms=900.0),
        ev("ai_reply", 2, "b" * 8, provider="Groq", model="openai/gpt-oss-20b", outcome="answered", fallback_used=True, attempts=2, total_ms=1900.0),
        ev("ai_reply", 3, "c" * 8, outcome="degraded", attempts=4, total_ms=9000.0),
        ev("ai_attempt", 1, "a" * 8, provider="Gemini", model="gemini-3-flash-preview", position=1, outcome="success", latency_ms=800.0, input_tokens=1000, output_tokens=200),
        ev("ai_attempt", 2, "b" * 8, provider="Gemini", model="gemini-3-flash-preview", position=1, outcome="timeout", latency_ms=9000.0),
        ev("funnel", 1, step="core"), ev("funnel", 2, step="core"), ev("funnel", 3, step="extras"), ev("funnel", 4, step="completed"),
        ev("client", 1, code="chunk_load_failed"), ev("client", 2, code="chunk_load_failed"),
    ]
    u = M.usage_summary(events)
    assert u["safety_by_day"] == {"2026-10-13": {"GREEN": 3, "AMBER": 1, "RED": 1}}
    assert u["route_mix"] == {"ai": 2, "emergency": 1, "consent_needed": 1, "daily_log": 1}
    assert u["ai_share"] == {"ai": 2, "deterministic": 3, "rate": 0.4}
    assert u["consent_needed"] == {"count": 1, "rate": 0.2}
    assert u["reliability"] == {"fallback_rate": 0.5, "degraded_rate": 0.333, "timeout_rate": 0.5}
    assert u["feature_usage"]["/health/sleep"] == 2 and u["feature_usage"]["/chat"] == 4          # the failed call is not "usage"
    assert [(f["step"], f["count"]) for f in u["funnel"] if f["count"]] == [("core", 2), ("extras", 1), ("completed", 1)]
    assert u["client_problems"] == {"chunk_load_failed": 2}
    json.dumps(u)


def test_cost_is_worked_out_when_read_free_tier_is_zero_and_unknown_says_unknown():
    events = [ev("ai_attempt", 1, "a" * 8, provider="Groq", model="openai/gpt-oss-20b", outcome="success", input_tokens=1_000_000, output_tokens=1_000_000),
              ev("ai_attempt", 2, "b" * 8, provider="NVIDIA", model="unknown", outcome="error")]
    free = {(r["provider"], r["model"]): r for r in M.cost_table(events)}
    assert free[("Groq", "openai/gpt-oss-20b")]["label"] == "free tier" and free[("Groq", "openai/gpt-oss-20b")]["cost_usd"] == 0.0
    assert free[("Groq", "openai/gpt-oss-20b")]["if_paid_usd"] == pytest.approx(0.375)       # 1M in at 0.075 + 1M out at 0.30
    assert free[("NVIDIA", "unknown")]["label"] == "unknown" and free[("NVIDIA", "unknown")]["cost_usd"] is None
    paid = {(r["provider"], r["model"]): r for r in M.cost_table(events, paid_allowed=True)}
    assert paid[("Groq", "openai/gpt-oss-20b")]["cost_usd"] == pytest.approx(0.375) and paid[("Groq", "openai/gpt-oss-20b")]["label"] == "paid"
    assert M.model_cost("Gemini", "gemini-3-flash-preview", 10, 10, paid_allowed=True)["label"] == "unknown"   # no price row: never shown as free or as a guess
    assert "cost_usd" not in str(ops_telemetry.FIELDS)                                            # cost is never stored in an event


def test_funnel_and_client_events_only_take_fixed_names():
    ops_telemetry.funnel("core")
    ops_telemetry.funnel("my name is Riya")
    ops_telemetry.funnel("")
    ops_telemetry.client("render_error")
    ops_telemetry.client("TypeError: x is undefined at /body?organ=heart")
    ops_telemetry.record("funnel", step="extras", answer="I have diabetes", user_id="u1")
    recorded = [(e["kind"], e["data"]) for e in ops_telemetry.recent(0, 100)]
    assert recorded == [("funnel", {"step": "core"}), ("client", {"code": "render_error"}), ("funnel", {"step": "extras"})]


def test_every_onboarding_step_has_a_funnel_name():
    import onboarding
    assert {s["id"] for s in onboarding.STEPS} <= set(ops_telemetry.FUNNEL_STEPS)
    assert set(M.FUNNEL_ORDER) == set(ops_telemetry.FUNNEL_STEPS)


def test_before_the_migration_the_new_kinds_stay_in_memory_and_the_old_ones_still_save(monkeypatch):
    calls = []

    class Table:
        def insert(self, rows):
            calls.append([r["kind"] for r in rows])

            class Q:
                def execute(self_inner):
                    if any(r["kind"] in {"funnel", "client"} for r in rows):
                        raise RuntimeError('new row for relation "bubbles_ops_events" violates check constraint "bubbles_ops_events_kind_check" (23514)')
            return Q()

    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    monkeypatch.setattr(ops_telemetry, "_db", lambda: type("DB", (), {"table": lambda self, name: Table()})())
    ops_telemetry.record("error", category="rag", component="RAG", error_class="Timeout")
    ops_telemetry.funnel("core")
    assert ops_telemetry.flush_once() == 1
    assert calls == [["funnel"], ["error"]] and ops_telemetry.status["new_kinds"] == "not_allowed"
    ops_telemetry.funnel("extras")
    assert not [e for e in ops_telemetry._queue if e["kind"] == "funnel"]                        # no longer queued
    assert [e["kind"] for e in ops_telemetry.recent(0, 10)][-1] == "funnel"                      # still visible live


def test_the_migration_adds_the_kinds_idempotently_and_has_an_undo():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "supabase"
    sql = (root / "migrations" / "20261016_bubbles_ops_funnel.sql").read_text(encoding="utf-8").lower()
    assert "'funnel'" in sql and "'client'" in sql and "drop constraint" in sql and "on conflict" in sql
    code = " ".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert "grant" not in code and "revoke" not in code and "policy" not in code.replace("pg_policies", "")   # no privilege or policy change
    undo = (root / "undo" / "20261016_bubbles_ops_funnel_undo.sql").read_text(encoding="utf-8").lower()
    assert "delete from public.bubbles_ops_events where kind in ('funnel', 'client')" in undo and "drop constraint if exists" in undo


def test_the_client_problem_route_takes_a_code_and_nothing_else(env):
    c = env.client
    assert c.post("/telemetry/client", json={"code": "render_error"}).status_code == 204
    assert c.post("/telemetry/client", json={"code": "TypeError at /body?organ=heart: my chest hurts"}).status_code == 204
    assert c.post("/telemetry/client", json={"nothing": 1}).status_code == 422
    stored = [e["data"] for e in _events("client")]
    assert stored == [{"code": "render_error"}]


def test_active_people_are_counted_as_integers_and_never_named():
    db = FakeDB({})
    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)

    def message(user, hours_ago, role="user"):
        db.table("chat_messages").insert({"user_id": user, "role": role, "content": "SECRET WORDS", "conversation_id": "c",
                                          "created_at": (now - timedelta(hours=hours_ago)).isoformat()}).execute()
    for user, hours in (("u1", 1), ("u1", 2), ("u2", 30), ("u3", 24 * 20), ("u4", 24 * 40)):
        message(user, hours)
    message("u9", 1, role="bubbles")                                                             # a reply is not a person being active
    for user, days in (("p1", 2), ("p2", 20), ("p3", 90)):
        db.table("profiles").insert({"id": user, "created_at": (now - timedelta(days=days)).isoformat()}).execute()
    out = ops_usage.activity_counts(db, now)
    assert out == {"active_1d": 1, "active_7d": 2, "active_30d": 3, "signups_7d": 1, "signups_30d": 2, "capped": False}
    assert "u1" not in json.dumps(out) and "SECRET" not in json.dumps(out)


def test_an_unreadable_table_gives_none_not_a_crash():
    db = FakeDB({})
    db.failures["chat_messages"] = RuntimeError("down")
    out = ops_usage.activity_counts(db)
    assert out["active_1d"] is None and out["signups_7d"] == 0


def test_the_admin_usage_route_is_admin_only_and_returns_counts(admin_env):
    c, t = admin_env.client, admin_env.tokens
    assert c.get("/admin/usage", headers=bearer(t.user)).status_code == 404
    res = c.get("/admin/usage?range=7d", headers=bearer(t.admin))
    assert res.status_code == 200
    body = res.json()
    assert set(body["usage"]) >= {"safety_by_day", "route_mix", "ai_share", "consent_needed", "reliability", "feature_usage", "funnel", "client_problems", "cost", "stage_ms"}
    assert set(body["people"]) == {"active_1d", "active_7d", "active_30d", "signups_7d", "signups_30d", "capped"}
