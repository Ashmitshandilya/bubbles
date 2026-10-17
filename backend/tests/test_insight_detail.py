"""Stable insight ids, the additive numbers behind them, and GET /insights/{id} (owner-scoped, bounded)."""
from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import association_insights as ai
import association_loader
import insights_api
import pattern_engine as pe
import schemas
from tests.fake_db import FakeDB
from weekly_insights import build_weekly_insights, to_response_shape

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
H1, H2 = {"Authorization": "Bearer t1"}, {"Authorization": "Bearer t2"}
NOW = datetime.now(timezone.utc)
URL_SAFE = re.compile(r"^[a-z0-9_:|>-]+$")


def ev(event_type, subject, days_ago, event_id, user=U1):
    return {"id": event_id, "user_id": user, "event_type": event_type, "extracted_data": {"symptom": subject}, "confidence": 0.9,
            "created_at": (NOW - timedelta(days=days_ago)).isoformat(), "extraction_status": "confirmed"}


def backaches(n, user=U1):
    return [ev("symptom", "Low back pain", i, f"h{user[-1]}{i}", user) for i in range(1, n + 1)]


def test_recurrence_has_a_stable_url_safe_id_and_dated_occurrences():
    rows = backaches(20)
    p = pe.recurring_patterns(rows)[0]
    assert p["id"] == "rec:symptom:low-back-pain" and URL_SAFE.match(p["id"])
    assert p["id"] == pe.recurring_patterns(list(reversed(rows)))[0]["id"]          # input order does not matter
    assert len(p["occurrences"]) == pe.MAX_OCCURRENCES == 14
    assert all(set(o) == {"id", "date"} and re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["date"]) for o in p["occurrences"])
    assert [o["date"] for o in p["occurrences"]] == sorted((o["date"] for o in p["occurrences"]), reverse=True)   # newest first
    assert p["occurrence_count"] == 20                                               # the count is still the real one


def test_correlation_has_id_label_and_at_most_twelve_dated_pairs():
    rows = []
    for i in range(1, 30):
        rows.append(ev("sleep", "poor sleep", i * 2, f"s{i}"))
        rows.append(ev("symptom", "headache", i * 2 - 1, f"c{i}"))
    c = pe.temporal_correlations(rows, window_days=2, min_pairs=3)[0]
    assert c["id"].startswith("co:") and "|" in c["id"] and URL_SAFE.match(c["id"])
    assert len(c["pairs"]) == pe.MAX_PAIRS
    first = c["pairs"][0]
    assert c["a"]["subject"] == "poor sleep" and first["a"]["id"].startswith("s") and first["b"]["id"].startswith("c")   # a is the first by (type, subject)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first["a"]["date"]) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", first["b"]["date"])
    assert c["confidence_label"] == pe.correlation_confidence(c["pair_count"]) == "high"


def test_confidence_word_comes_from_one_rule():
    assert pe.recurrence_confidence(3, 5, 0.9) == "low"
    assert pe.recurrence_confidence(5, 5, 0.9) == "medium"
    assert pe.recurrence_confidence(8, 14, 0.9) == "high"
    assert pe.recurrence_confidence(9, 30, 0.4) == "low"
    assert pe.correlation_confidence(3) == "low" and pe.correlation_confidence(4) == "medium"


def test_weekly_items_carry_id_label_and_a_number_that_agrees_with_it():
    data = build_weekly_insights(backaches(6), now=NOW)
    shaped = to_response_shape(data)
    top = shaped["insights"][0]
    assert top["id"] == "rec:symptom:low-back-pain" and top["confidence_label"] == "medium" and top["confidence"] == 0.6
    assert schemas.WeeklyInsightsData(**shaped).insights[0].id == top["id"]
    gap = to_response_shape(build_weekly_insights([], now=NOW))["insights"][0]
    assert gap["id"] == "gap:week" and gap["confidence"] == 0.0


def test_association_findings_carry_numbers_for_the_detail_view():
    rng = random.Random(4)
    start = date(2026, 7, 1)

    def d(i):
        return start + timedelta(days=i)

    act = {d(i): float(10 + (i * 7) % 50) for i in range(60)}
    sleep_q = {d(i + 1): 1 + act[d(i)] / 14 + rng.random() * 0.3 for i in range(60)}
    hit = next(i for i in ai.analyze({"activity_minutes": act, "sleep_quality": sleep_q})["insights"] if i["id"] == "activity_minutes->sleep_quality")
    assert hit["lag_days"] == 1 and isinstance(hit["p"], float) and hit["repeated"] in (True, False)
    assert isinstance(hit["limitations"], list) and hit["limitations"][0] == "Only days you logged activity are compared."
    assert 0 < len(hit["pairs"]) <= ai.MAX_PAIRS
    p0 = hit["pairs"][0]
    assert set(p0) == {"date", "x", "y"} and p0["date"] > hit["pairs"][-1]["date"]    # newest first, ISO days and numbers only
    assert p0["y"] == pytest.approx(sleep_q[date.fromisoformat(p0["date"]) + timedelta(days=1)])


@pytest.fixture()
def env(monkeypatch):
    db = FakeDB({"t1": U1, "t2": U2})
    db.tables["extracted_health_events"] = backaches(5) + backaches(7, U2)

    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        return db.auth.get_user(authorization[7:]).user

    canned = {"insights": [{"id": "sleep_hours->mood", "domains": ["sleep_hours", "mood"], "lag_days": 0, "status": "candidate_association",
                            "strength": "moderate", "direction": "up", "n_days": 30, "rho": 0.5, "p": 0.01, "q": 0.02, "repeated": False,
                            "limitations": ["a"], "pairs": [{"date": "2026-10-01", "x": 7.0, "y": 6.0}], "text": "t", "sources": []}]}
    monkeypatch.setattr(association_loader, "get", lambda db_, uid, days=90, *a, **k: canned)
    app = FastAPI()
    app.include_router(insights_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def test_endpoint_requires_a_token(env):
    client, _ = env
    assert client.get("/insights/rec:symptom:low-back-pain").status_code == 401


def test_detail_of_a_pattern_is_the_callers_own_numbers(env):
    client, _ = env
    body = client.get("/insights/rec:symptom:low-back-pain", headers=H1).json()
    d = body["insight"]
    mine = {f"h1{i}" for i in range(1, 6)}
    assert "source_event_ids" not in d and d["confidence_label"] == "medium" and d["window_days"] == 30
    assert body["status"] == "success" and d["kind"] == "pattern" and d["occurrence_count"] == 5 and {o["id"] for o in d["occurrences"]} == mine
    other = client.get("/insights/rec:symptom:low-back-pain", headers=H2).json()["insight"]
    assert other["occurrence_count"] == 7 and {o["id"] for o in other["occurrences"]}.isdisjoint(mine)


def test_unknown_or_malformed_ids_are_a_plain_404(env):
    client, _ = env
    for bad in ("rec:symptom:nothing", "co:a:b|c:d", "garbage", "x" * 300, "rec:symptom:%27%3B--"):
        assert client.get(f"/insights/{bad}", headers=H1).status_code == 404, bad


def test_association_detail_resolves_from_the_engine_and_unknown_pair_is_404(env):
    client, _ = env
    d = client.get("/insights/sleep_hours->mood", headers=H1).json()["insight"]
    assert d["kind"] == "association" and d["domains"] == ["sleep_hours", "mood"] and d["pairs"][0]["date"] == "2026-10-01"
    assert client.get("/insights/mood->sleep_quality", headers=H1).status_code == 404


def test_window_is_bounded(env):
    client, _ = env
    assert client.get("/insights/rec:symptom:low-back-pain?days=100000", headers=H1).status_code == 422


def test_weekly_route_in_the_real_app_is_not_shadowed_by_the_detail_route(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "dummy")
    import main
    from types import SimpleNamespace
    monkeypatch.setattr(main, "get_authenticated_user", lambda authorization=None: SimpleNamespace(id=U1))   # only /insights/weekly looks this name up
    monkeypatch.setattr(main, "_get_user_health_events", lambda uid, days=30: [])
    r = TestClient(main.app, raise_server_exceptions=False).get("/insights/weekly", headers=H1)
    assert r.status_code == 200 and r.json()["insights"]["insights"][0]["id"] == "gap:week"


# ---- negative cases -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("days", ["0", "6", "-1", "366", "abc", ""])
def test_bad_window_values_are_rejected(env, days):
    client, _ = env
    assert client.get(f"/insights/rec:symptom:low-back-pain?days={days}", headers=H1).status_code == 422


def test_window_edges_are_accepted(env):
    client, _ = env
    for days in (7, 365):
        assert client.get(f"/insights/rec:symptom:low-back-pain?days={days}", headers=H1).status_code in (200, 404)


def test_bad_or_wrong_scheme_tokens_are_401(env):
    client, _ = env
    for headers in ({}, {"Authorization": "Basic abc"}):
        assert client.get("/insights/rec:symptom:low-back-pain", headers=headers).status_code == 401


def test_someone_elses_only_pattern_is_a_404_for_me(env):
    client, db = env
    db.tables["extracted_health_events"] = backaches(7, U2)          # only user 2 has this pattern
    assert client.get("/insights/rec:symptom:low-back-pain", headers=H1).status_code == 404
    assert client.get("/insights/rec:symptom:low-back-pain", headers=H2).status_code == 200


def test_empty_history_is_a_404_not_a_500(env):
    client, db = env
    db.tables["extracted_health_events"] = []
    for i in ("rec:symptom:low-back-pain", "co:symptom:a|symptom:b", "gap:week"):
        assert client.get(f"/insights/{i}", headers=H1).status_code == 404, i


def test_id_length_limit_is_exact(env, monkeypatch):
    client, _ = env
    looked_up = []
    monkeypatch.setattr(insights_api, "find_detail", lambda db, uid, i, days: looked_up.append(i))
    assert client.get("/insights/" + "x" * (insights_api.MAX_ID + 1), headers=H1).status_code == 404
    # at the limit it is looked up (and simply not found), still a 404 but through the lookup path
    assert looked_up == []                                  # an oversized id never reaches the database
    assert client.get("/insights/rec:" + "x" * (insights_api.MAX_ID - 4), headers=H1).status_code == 404
    assert len(looked_up) == 1                              # at the limit it is looked up


def test_huge_history_is_capped_and_still_answers(env):
    client, db = env
    db.tables["extracted_health_events"] = [ev("symptom", "Low back pain", i % 28 + 1, f"big{i}") for i in range(1200)]
    d = client.get("/insights/rec:symptom:low-back-pain?days=30", headers=H1).json()["insight"]
    assert len(d["occurrences"]) == pe.MAX_OCCURRENCES
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["date"]) for o in d["occurrences"])


def test_retracted_rows_never_count_toward_a_detail(env):
    client, db = env
    db.tables["extracted_health_events"] = [{**e, "extraction_status": "retracted"} for e in backaches(8)]
    assert client.get("/insights/rec:symptom:low-back-pain", headers=H1).status_code == 404


def test_detail_never_returns_free_text_from_entries(env):
    client, db = env
    rows = backaches(6)
    for r in rows:
        r["extracted_data"]["notes"] = "SECRET-FREE-TEXT my boss is cruel"
    db.tables["extracted_health_events"] = rows
    assert "SECRET-FREE-TEXT" not in client.get("/insights/rec:symptom:low-back-pain", headers=H1).text


def test_ids_survive_hostile_subjects():
    assert pe.recurrence_id("symptom", "../../etc/passwd; DROP TABLE") == "rec:symptom:etc-passwd-drop-table"
    assert pe.slug("") == "x" and pe.slug("   ") == "x" and len(pe.slug("a" * 500)) == 40
    assert URL_SAFE.match(pe.correlation_id("symptom", "A B|C", "sleep", "é ü"))


def test_dated_pairs_cap_and_skip_missing_values():
    sx = {date(2026, 10, 1) + timedelta(days=i): float(i) for i in range(40)}
    sy = {d: None for d in sx}
    assert ai._dated_pairs(sx, sy, 0) == []
    sy = {d: 1.0 for d in sx}
    out = ai._dated_pairs(sx, sy, 0)
    assert len(out) == ai.MAX_PAIRS and out[0]["date"] > out[-1]["date"]
    assert ai._dated_pairs({}, {}, 1) == []
