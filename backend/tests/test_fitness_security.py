"""Regression tests for the findings of the security audit (pause bypass, clearance, sticky screen, cadence, limits, forged documents)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import clinical_constants as K
import data_rights
import plan_engine
import transformation as T
from tests.test_fitness_api import H1, SCOFF_OK, env, put_profile, start_body  # noqa: F401
from test_chat_http_flow import env as chat_env, H as CHAT_H  # noqa: F401

TODAY = datetime.now(timezone.utc).date()


def test_clearance_must_name_what_it_covers(env):
    c, _ = env
    for bad in ({"cleared": True, "date": "2026-01-01"}, {"cleared": True, "date": "2026-01-01", "areas": []}, {"cleared": True, "date": "2026-01-01", "areas": ["everything"]}):
        r = c.put("/profile/body", json={"clinician_clearance": bad}, headers=H1)
        assert r.status_code == 422, bad
    ok = c.put("/profile/body", json={"clinician_clearance": {"cleared": True, "date": "2026-01-01", "areas": ["heart disease"]}}, headers=H1)
    assert ok.status_code == 200


def test_blanket_clearance_does_not_unlock_anything():
    profile = {"age": 30, "height_cm": 165, "weight_kg": 80, "target_weight_kg": 68, "formula_basis": "female", "conditions": ["kidney disease"],
               "clinician_clearance": {"cleared": True, "date": TODAY.isoformat(), "areas": []}}
    assert T.screen(profile, [False] * 5, today=TODAY)["decision"] == "refused"
    profile["clinician_clearance"]["areas"] = ["kidney disease"]
    r = T.screen(profile, [False] * 5, today=TODAY)
    assert r["decision"] != "refused" and r["cleared_areas"] == ["kidney disease"]


def test_a_safety_pause_cannot_be_replaced_or_skipped_by_finishing(env):
    c, _ = env
    put_profile(c)
    c.post("/fitness/transform/start", json=start_body(), headers=H1)
    c.post("/fitness/transform/checkin", json={"note": "I want to starve myself"}, headers=H1)           # safety pause
    plan = c.get("/fitness/transform/plan", headers=H1).json()["plan"]
    assert plan["status"] == "paused" and plan["paused"]["safety"] is True
    since = plan["paused"]["since"]
    again = c.post("/fitness/transform/pause", json={"reason": "just a normal pause"}, headers=H1).json()["plan"]
    assert again["paused"]["safety"] is True and again["paused"]["since"] == since              # not downgraded to an ordinary pause
    assert c.post("/fitness/transform/resume", json={"scoff": SCOFF_OK}, headers=H1).status_code == 409
    assert c.post("/fitness/transform/finish", headers=H1).status_code == 409                    # finishing is no way round the cooldown
    r = c.post("/fitness/transform/screen", json={"scoff": SCOFF_OK}, headers=H1).json()          # a fresh start is also blocked
    assert any(e["code"] == "recent_safety_pause" and e["clearable"] is False for e in r["exclusions"])


def test_positive_eating_screen_is_sticky_and_keeps_numbers_gentle(env):
    c, _ = env
    put_profile(c)
    assert c.post("/fitness/transform/screen", json={"scoff": [True, True, False, False, False]}, headers=H1).json()["decision"] == "refused"
    again = c.post("/fitness/transform/screen", json={"scoff": SCOFF_OK}, headers=H1).json()
    assert again["decision"] == "refused" and any(e["code"] == "eating_concern" for e in again["exclusions"])
    t = c.get("/fitness/targets", headers=H1).json()["targets"]
    assert t["goal"] == "maintain" and t["deficit_kcal"] == 0 and any("gentle" in n for n in t["notes"])


def test_eating_history_flag_alone_keeps_targets_gentle(env):
    c, _ = env
    put_profile(c, eating_disorder_history=True)
    t = c.get("/fitness/targets", headers=H1).json()["targets"]
    assert t["goal"] == "maintain" and t["deficit_kcal"] == 0


def test_weekly_checkin_cannot_be_repeated_or_applied_stale(env):
    c, _ = env
    put_profile(c)
    c.post("/fitness/transform/start", json=start_body(), headers=H1)
    for i in range(14):
        d = TODAY - timedelta(days=13 - i)
        c.post("/health/weight", json={"weight": 176.4 - 0.07 * i, "date": d.isoformat() + "T08:00:00Z"}, headers=H1)
        c.post("/fitness/food-log", json={"text": "chicken biryani, 2 rotis", "date": d.isoformat()}, headers=H1)
    first = c.post("/fitness/transform/checkin", json={}, headers=H1)
    assert first.status_code == 200
    if first.json()["decision"] != "pause":
        assert c.post("/fitness/transform/checkin/apply", json={"accept": True}, headers=H1).status_code == 200
        assert c.post("/fitness/transform/checkin", json={}, headers=H1).status_code == 409          # not again this week
    stale = c.post("/fitness/transform/checkin/apply", json={"accept": True}, headers=H1)
    assert stale.status_code in (404, 409)


def test_logging_dates_are_bounded(env):
    c, _ = env
    put_profile(c)
    for bad in ("1999-01-01", "2090-01-01", (TODAY + timedelta(days=30)).isoformat()):
        assert c.post("/fitness/food-log", json={"text": "roti", "date": bad}, headers=H1).status_code == 422, bad
        assert c.post("/fitness/workouts/log", json={"title": "walk", "minutes": 10, "date": bad}, headers=H1).status_code == 422
    assert c.post("/fitness/food-log", json={"text": "roti", "date": (TODAY - timedelta(days=30)).isoformat()}, headers=H1).status_code == 201


def test_exercise_credit_is_capped():
    t = plan_engine.build_targets({"age": 30, "height_cm": 165, "weight_kg": 80, "target_weight_kg": 70, "formula_basis": "female"})
    assert plan_engine.day_budget(t, 1500, 5000)["exercise_credit_kcal"] == K.EXERCISE_CREDIT_MAX_KCAL


def test_profile_type_confusion_is_a_422_not_a_500(env):
    c, _ = env
    for bad in ({"activity_level": ["x"]}, {"formula_basis": {"a": 1}}, {"units": 5}, {"diet_style": ["vegan"]}, {"weight_kg": 10 ** 400}, {"height_cm": [1]}):
        r = c.put("/profile/body", json=bad, headers=H1)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str), bad


def test_delete_everything_also_removes_analytics_copies(env):
    c, db = env
    put_profile(c)
    c.post("/fitness/food-log", json={"text": "2 rotis and dal"}, headers=H1)
    assert any(r["extracted_data"]["_prov"]["domain"] == "food_log" for r in db.tables["extracted_health_events"])
    app = FastAPI()
    app.include_router(data_rights.build_router(lambda a: SimpleNamespace(id="user-1"), db))
    out = TestClient(app).delete("/me/whole-health/data?confirm=true").json()
    assert out["analytics_copies_removed"] == 1 and out["deleted"] >= 1
    assert not [r for r in db.tables["extracted_health_events"] if r["extracted_data"]["_prov"]["domain"] == "food_log"]
    assert "truncated" in TestClient(app).get("/me/whole-health/export").json()


def test_forged_plan_row_written_straight_to_the_database_is_ignored(env):
    c, db = env
    put_profile(c)
    db.table("health_events").insert({"user_id": "user-1", "event_type": "bubbles_doc", "title": "transform_plan:current",
                                      "data": {"kind": "transform_plan", "key": "current", "version": 1,
                                               "payload": {"status": "active", "targets": {"kcal": 300, "floor_kcal": 0}, "target_weight_kg": 50, "start_weight_kg": 80}}}).execute()
    assert c.get("/fitness/transform/plan", headers=H1).json()["exists"] is False
    assert c.get("/fitness/transform/today", headers=H1).status_code == 404


def test_oversized_bodies_and_floods_are_refused(chat_env):
    e = chat_env
    big = e.client.post("/fitness/meal/parse", content=b"x" * 1_600_000, headers={**CHAT_H, "Content-Type": "application/json"})
    assert big.status_code == 413
    codes = {e.client.get("/fitness/targets", headers=CHAT_H).status_code for _ in range(260)}
    assert 429 in codes and 200 in codes
    assert e.client.get("/cycle/partner/" + "a" * 30).status_code in (404, 429)
