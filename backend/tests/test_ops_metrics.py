"""Admin portal numbers: every figure is computed from recorded events, and comparisons need a minimum sample."""
from datetime import datetime, timedelta, timezone

import ops_metrics as M
import ops_rollups
import ops_telemetry

T0 = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)


def ev(kind, seconds=0, rid=None, **data):
    return {"kind": kind, "at": (T0 + timedelta(seconds=seconds)).isoformat(), "request_id": rid, "data": data}


def attempt(rid, provider, position, outcome="success", ms=100.0, category=None, s=0):
    return ev("ai_attempt", s, rid, provider=provider, model=f"{provider}-m", position=position, outcome=outcome,
              latency_ms=ms, error_category=category)


def reply(rid, provider=None, attempts=None, outcome="answered", s=0):
    return ev("ai_reply", s, rid, provider=provider, model=f"{provider}-m" if provider else None, attempts=attempts, outcome=outcome,
              fallback_used=bool(attempts and attempts > 1) if outcome == "answered" else None, total_ms=200.0)


def test_percentile_is_nearest_rank():
    assert M.percentile([], 50) is None
    assert M.percentile([5.0], 99) == 5.0
    values = [float(v) for v in range(1, 101)]
    assert (M.percentile(values, 50), M.percentile(values, 95), M.percentile(values, 99)) == (50.0, 95.0, 99.0)


def scenario():
    events = []
    for i in range(12):   # 12 replies: Gemini answers 8, fails 4 times (3 errors, 1 timeout) and Groq answers those
        rid = f"r{i:07d}"
        if i < 8:
            events += [attempt(rid, "Gemini", 1, ms=800.0), reply(rid, "Gemini", 1)]
        else:
            events += [attempt(rid, "Gemini", 1, "timeout" if i == 8 else "error", ms=25000.0 if i == 8 else 300.0,
                               category="timeout" if i == 8 else "provider_error"),
                       attempt(rid, "Groq", 2, ms=1200.0), reply(rid, "Groq", 2)]
    events += [attempt("rdeg00001", "Gemini", 1, "error", category="rate_limited"), attempt("rdeg00001", "Groq", 2, "error"),
               attempt("rdeg00001", "NVIDIA", 3, "error"), attempt("rdeg00001", "Mistral", 4, "invalid_json"),
               reply("rdeg00001", outcome="degraded")]
    events += [ev("api", 1, route="/chat", status=200, latency_ms=900.0, route_kind="ai", ai_called=True, safety_level="GREEN"),
               ev("api", 2, route="/chat", status=200, latency_ms=40.0, route_kind="emergency", ai_called=False, safety_level="RED")]
    return events


def test_ai_summary_counts_answers_fallbacks_and_the_safety_gate():
    s = M.ai_summary(scenario())
    assert (s["replies"], s["answered"], s["degraded"], s["fallback_used"]) == (13, 12, 1, 4)
    assert (s["chat_turns"], s["ai_called"], s["answered_without_ai"], s["safety_gated"]) == (2, 1, 1, 1)
    assert s["timeouts"] == 1 and s["success_rate"] == round(12 / 13, 3)


def test_provider_table_and_who_is_actually_answering():
    rows = {r["provider"]: r for r in M.provider_table(scenario())}
    gemini, groq = rows["Gemini"], rows["Groq"]
    assert (gemini["requests"], gemini["successful"], gemini["failed"]) == (13, 8, 5)
    assert gemini["final_answers"] == 8 and gemini["final_share"] == round(8 / 12, 3) and gemini["first_choice_rate"] == 1.0
    assert gemini["error_categories"] == {"timeout": 1, "provider_error": 3, "rate_limited": 1}
    assert groq["first_choice_rate"] == 0.0 and groq["avg_position"] == 2.0 and groq["final_answers"] == 4
    assert M.answering(scenario())["provider"] == "Gemini"


def test_highlights_need_a_minimum_sample():
    rows = M.provider_table(scenario())
    h = M.highlights(rows)
    assert h["most_answers"]["provider"] == "Gemini"
    assert h["slowest"]["provider"] == "Gemini" and h["most_failing"]["provider"] == "Gemini"   # only Gemini has 10+ attempts
    assert h["most_reliable"]["provider"] == "Gemini"
    small = M.highlights(M.provider_table(scenario()[:6]))
    assert small["slowest"] is None and small["most_reliable"] is None


def test_fallback_chain_follows_the_configured_order_and_counts_where_it_ends():
    flow = M.fallback_chain(scenario(), ["Gemini", "Groq", "NVIDIA", "Mistral"])
    steps = {s["provider"]: s for s in flow["steps"]}
    assert [s["provider"] for s in flow["steps"]] == ["Gemini", "Groq", "NVIDIA", "Mistral"]
    assert (steps["Gemini"]["reached"], steps["Gemini"]["answered"], steps["Gemini"]["moved_on"]) == (13, 8, 5)
    assert (steps["Groq"]["reached"], steps["Groq"]["answered"]) == (5, 4)
    assert flow["ran_out"] == 1
    transitions = {(t["from"], t["to"]): t["count"] for t in flow["transitions"]}
    assert transitions[("Gemini", "Groq")] == 5 and transitions[("Mistral", "degraded reply")] == 1


def test_api_table_uses_templates_status_classes_and_a_trend():
    events = [ev("api", s, method="GET", route="/profile", status=st, latency_ms=ms)
              for s, st, ms in [(10, 200, 100.0), (20, 200, 300.0), (3500, 404, 50.0), (3590, 503, 900.0)]]
    (row,) = M.api_table(events, T0, T0 + timedelta(hours=1))
    assert (row["requests"], row["client_errors"], row["server_errors"], row["success_rate"]) == (4, 1, 1, 0.5)
    assert row["slowest_ms"] == 900.0 and sum(row["trend"]) == 4 and row["trend"][0] == 2 and row["trend"][-1] == 2
    summary = M.api_summary(events, T0, T0 + timedelta(hours=1))
    assert summary["per_minute"] == round(4 / 60, 2) and summary["error_rate"] == 0.25


def test_headline_is_ok_warn_or_fail_with_plain_reasons():
    calm = dict(database="ok", persistence_mode="stored", all_paused=False, ai_now={"replies": 0}, api_now={"requests": 0})
    assert M.headline(**calm) == {"status": "ok", "reasons": []}
    assert M.headline(**{**calm, "persistence_mode": "not_set_up"})["status"] == "warn"
    assert M.headline(**{**calm, "ai_now": {"replies": 1, "degraded": 1, "success_rate": 0.0}})["status"] == "warn"
    assert M.headline(**{**calm, "ai_now": {"replies": 12, "degraded": 9, "success_rate": 0.25}})["status"] == "fail"
    assert M.headline(**{**calm, "all_paused": True})["status"] == "fail"
    assert M.headline(**{**calm, "database": "unreachable"})["status"] == "fail"
    for result in (M.headline(**{**calm, "all_paused": True}), M.headline(**{**calm, "persistence_mode": "write_failing"})):
        assert all("—" not in r for r in result["reasons"])


def test_the_write_queue_is_bounded_and_counts_what_it_drops(monkeypatch):
    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    monkeypatch.setattr(ops_telemetry, "QUEUE_LIMIT", 3)
    monkeypatch.setattr(ops_telemetry, "_queue", ops_telemetry.deque(maxlen=3))
    for i in range(5):
        ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=float(i))
    assert len(ops_telemetry._queue) == 3 and ops_telemetry.status["dropped"] == 2


def test_flush_writes_one_batch_and_prune_keeps_audit_longer(monkeypatch):
    calls = []

    class Query:
        def __init__(self, op):
            self.op = op

        def __getattr__(self, name):
            def step(*args, **_k):
                calls.append((self.op, name, args))
                return self
            return step

        def execute(self):
            return type("R", (), {"data": []})()

    class Table:
        def insert(self, rows):
            calls.append(("insert", len(rows)))
            return Query("insert")

        def delete(self):
            return Query("delete")

    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    monkeypatch.setattr(ops_telemetry, "_db", lambda: type("DB", (), {"table": lambda self, name: Table()})())
    for _ in range(3):
        ops_telemetry.record("error", category="rag", component="RAG", error_class="Timeout")
    assert ops_telemetry.flush_once() == 3 and ("insert", 3) in calls and ops_telemetry.status["mode"] == "stored"
    ops_telemetry.prune_once(now=T0)
    deletes = [c for c in calls if c[0] == "delete"]
    assert ("delete", "in_", ("kind", ["api", "ai_attempt", "ai_reply", "error", "client"])) in deletes
    assert ("delete", "eq", ("kind", "funnel")) in deletes and ("delete", "eq", ("kind", "audit")) in deletes
    cutoffs = sorted(c[2][1] for c in deletes if c[1] == "lt")
    assert cutoffs == sorted([(T0 - timedelta(days=365)).isoformat(), (T0 - timedelta(days=ops_telemetry.FUNNEL_RETENTION_DAYS)).isoformat(),
                              (T0 - timedelta(days=ops_telemetry.retention_days)).isoformat()])


def _chat(seconds, route="/chat", **data):
    return ev("api", seconds, **{"method": "POST", "route": route, "status": 200, "latency_ms": 100.0, **data})


def test_a_stage_a_turn_skipped_is_not_a_zero_in_the_percentiles():
    ran = _chat(1, route_kind="ai", ai_called=True, stage_pre_ms=40.0, stage_ctx_ms=300.0, stage_rag_ms=200.0, stage_ai_ms=900.0, stage_post_ms=60.0)
    skipped = _chat(2, route_kind="daily_log", ai_called=False, stage_pre_ms=20.0, stage_post_ms=30.0)      # no ctx, rag or ai key at all
    stages = M.stage_latency([ran["data"], skipped["data"]])
    assert {k: v["n"] for k, v in stages.items()} == {"pre": 2, "ctx": 1, "rag": 1, "ai": 1, "post": 2}
    assert stages["ai"]["p50"] == 900.0 and stages["ctx"]["p95"] == 300.0          # a 0 from the skipped turn would have dragged these down
    counted = ops_rollups.totals(ops_rollups.count_events([ran, skipped]))
    assert {s: sum(counted[f"hist.stage.{s}"].values()) for s in ("pre", "ctx", "rag", "ai", "post")} == {"pre": 2, "ctx": 1, "rag": 1, "ai": 1, "post": 2}


def test_streamed_chats_are_counted_like_plain_ones_in_the_daily_counters():
    events = [_chat(1, route_kind="ai", ai_called=True, safety_level="GREEN", stage_ai_ms=500.0),
              _chat(2, route="/chat/stream", route_kind="ai", ai_called=True, safety_level="AMBER", stage_ai_ms=700.0, latency_ms=1200.0),
              _chat(3, route="/chat/stream", route_kind="emergency", ai_called=False, safety_level="RED")]
    t = ops_rollups.totals(ops_rollups.count_events(events))
    assert t["chat"]["total"] == 3 and t["req"]["total"] == 3
    assert dict(t["route_kind"]) == {"ai": 2, "emergency": 1} and dict(t["safety"]) == {"GREEN": 1, "AMBER": 1, "RED": 1}
    assert sum(t["hist.stage.ai"].values()) == 2 and sum(t["hist.chat"].values()) == 3
    assert t["route"]["POST /chat/stream"] == 2


def test_one_definition_of_deterministic_share_for_overall_and_usage():
    """ai + deterministic + consent_needed are separate and add up to the turns with a known kind, on every page."""
    kinds = ["ai", "ai", "emergency", "daily_log", "consent_needed", "small_talk"]
    split = M.chat_split({k: kinds.count(k) for k in set(kinds)})
    assert (split["turns"], split["ai"], split["deterministic"], split["consent_needed"]) == (6, 2, 3, 1)
    assert split["ai_share"] == round(2 / 6, 3) and split["deterministic_share"] == 0.5 and split["consent_needed_rate"] == round(1 / 6, 3)
    assert M.chat_split({}) == {"turns": 0, "ai": 0, "deterministic": 0, "consent_needed": 0,
                                "ai_share": None, "deterministic_share": None, "consent_needed_rate": None}
    events = [_chat(i, route="/chat/stream" if i % 2 else "/chat", route_kind=k, ai_called=k == "ai", safety_level="GREEN") for i, k in enumerate(kinds)]
    events.append(_chat(9, status=500))                                                  # a failed call with no kind is in neither figure
    overall = M.overall_view(ops_rollups.count_events(events), ["pre"], ())["ai"]
    usage = M.usage_summary(events)
    assert overall["deterministic_share"] == usage["ai_share"]["deterministic_rate"] == 0.5
    assert overall["ai_share"] == usage["ai_share"]["rate"] and overall["consent_needed_rate"] == usage["consent_needed"]["rate"]
    assert usage["ai_share"]["deterministic"] == 3 and usage["consent_needed"]["count"] == overall["consent_needed"] == 1
