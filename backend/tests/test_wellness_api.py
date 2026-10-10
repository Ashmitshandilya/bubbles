"""The /wellness/* and /notifications routes through FastAPI with a stateful fake database: flows, IDOR, 422s, safety gate."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import doc_store
import nutrition_calc as N
import wellness_api
from tests.fake_db import FakeDB

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
H1, H2 = {"Authorization": "Bearer t1"}, {"Authorization": "Bearer t2"}
URGENT = "I want to end my life"
CHEST = "I have severe chest pain right now and I cannot breathe"


def now_utc():
    return datetime.now(timezone.utc)


def today():
    return now_utc().date()


@pytest.fixture()
def env():
    db = FakeDB({"t1": U1, "t2": U2})

    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        try:
            return db.auth.get_user(authorization[7:]).user
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    app = FastAPI()
    router = wellness_api.build_router(get_user, db)
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    client.wellness_router = router
    client.put("/notifications/settings", json={"quiet_hours": {"enabled": False}}, headers=H1)
    client.put("/notifications/settings", json={"quiet_hours": {"enabled": False}}, headers=H2)
    return client, db


def detail_is_string(r):
    assert r.status_code == 422, r.text
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]


# --- every route needs a token --------------------------------------------------------------------------------------------------------

def test_every_route_requires_authentication(env):
    client, _db = env
    n = 0
    for route in client.wellness_router.routes:
        if not hasattr(route, "methods"):
            continue
        path = route.path.replace("{sid}", "aaaaaaaaaaaa").replace("{jid}", "aaaaaaaaaaaaaaaa")
        if not path.startswith(("/wellness", "/notifications")):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = client.request(method, path, json={} if method in ("POST", "PUT") else None)
            assert r.status_code == 401, (method, path, r.status_code)
            n += 1
    assert n == 31


def test_associations_endpoint_reports_gaps_without_zero_filling_and_is_per_user(env):
    import association_loader as AL
    AL._cache.clear()
    client, _db = env
    empty = client.get("/wellness/associations", headers=H1).json()
    assert empty["status"] == "success" and empty["insights"] == [] and empty["data_days"] == {} and empty["message"]
    for i in range(12):
        assert log_sleep(client, H1, i + 1, 6 + i % 3).status_code in (200, 201)
    out = client.get("/wellness/associations?days=60&refresh=true", headers=H1).json()
    assert out["data_days"]["sleep_hours"] == 12 and out["insights"] == [] and out["window_days"] == 60
    assert client.get("/wellness/associations?days=3", headers=H1).status_code == 422                     # window is bounded (14-365)
    assert client.get("/wellness/associations", headers=H2).json()["data_days"] == {}                      # another user sees none of it
    AL._cache.clear()


# --- sleep -------------------------------------------------------------------------------------------------------------------------------

def log_sleep(client, headers, i, hours, **kw):
    day = (today() - timedelta(days=i)).isoformat()
    return client.post("/wellness/sleep/log", json={"date": day, "duration": hours, **kw}, headers=headers)


def test_sleep_flow_goal_logs_tags_and_overview(env):
    client, db = env
    assert client.post("/wellness/sleep/goal", json={"hours": 7.5, "bedtime": "23:00"}, headers=H1).json()["goal"]["hours"] == 7.5
    for i in range(14):
        tagged = i % 2 == 0
        r = log_sleep(client, H1, i, 6.0 if tagged else 8.0, quality=7, tags=["caffeine"] if tagged else [], bedtime="23:30", wake="06:45")
        assert r.status_code == 201, r.text
    o = client.get("/wellness/sleep/overview?days=30", headers=H1).json()
    assert o["status"] == "success" and o["nights_logged"] == 14 and 0 <= o["score"]["value"] <= 100
    assert o["goal"]["hours"] == 7.5 and o["goal"]["source"] == "you"
    assert o["winddown"]["bedtime"] == "23:00" and o["regularity"]["basis"] == "times"
    assert any(i["tag"] == "caffeine" and "tended to" in i["text"] for i in o["insights"])
    assert db.rows("sleep_logs", user_id=U1)[0]["duration_minutes"] in (360, 480)       # went through the normal tracker table
    assert db.rows("extracted_health_events", user_id=U1)                                   # and was mirrored for the insight engines


def test_sleep_log_from_bed_and_wake_and_nap_only(env):
    client, _db = env
    r = client.post("/wellness/sleep/log", json={"bedtime": "23:00", "wake": "06:30"}, headers=H1)
    assert r.status_code == 201 and r.json()["entry"]["duration"] == 7.5
    nap = client.post("/wellness/sleep/log", json={"nap_minutes": 25, "date": (today() - timedelta(days=1)).isoformat()}, headers=H1)
    assert nap.status_code == 201 and nap.json()["entry"] is None and nap.json()["details"]["nap_minutes"] == 25


def test_sleep_isolation_between_users(env):
    client, _db = env
    log_sleep(client, H1, 0, 7)
    o2 = client.get("/wellness/sleep/overview", headers=H2).json()
    assert o2["nights_logged"] == 0 and o2["score"] is None
    client.post("/wellness/sleep/goal", json={"hours": 9}, headers=H1)
    assert client.get("/wellness/sleep/overview", headers=H2).json()["goal"]["source"] == "age"


@pytest.mark.parametrize("body", [
    {"duration": 30}, {"duration": "abc"}, {"duration": 7, "quality": 11}, {"duration": 7, "tags": ["magic"]}, {"duration": 7, "tags": "caffeine"},
    {"duration": 7, "date": "tomorrow"}, {"duration": 7, "date": (today() + timedelta(days=3)).isoformat()}, {"duration": 7, "date": "2001-01-01"},
    {"bedtime": "25:99", "wake": "07:00"}, {"bedtime": "07:00", "wake": "07:00"}, {}, {"duration": 7, "cycle_phase": "moon"}, {"duration": 7, "nap_minutes": 9999},
])
def test_sleep_log_validation(env, body):
    client, _db = env
    detail_is_string(client.post("/wellness/sleep/log", json=body, headers=H1))


def test_sleep_request_shape_errors(env):
    client, _db = env
    detail_is_string(client.post("/wellness/sleep/goal", json={"hours": 1}, headers=H1))
    detail_is_string(client.post("/wellness/sleep/goal", data="{not json", headers={**H1, "Content-Type": "application/json"}))
    detail_is_string(client.post("/wellness/sleep/goal", json=[1, 2], headers=H1))
    assert client.get("/wellness/sleep/overview?days=0", headers=H1).status_code == 422
    assert client.get("/wellness/sleep/overview?days=9999", headers=H1).status_code == 422


def test_sleep_note_with_urgent_text_returns_safety_and_saves_nothing(env):
    client, db = env
    r = client.post("/wellness/sleep/log", json={"duration": 5, "notes": CHEST}, headers=H1)
    assert r.status_code == 201 and r.json()["status"] == "safety" and r.json()["saved"] is False
    assert not db.rows("sleep_logs") and not [r for r in db.tables.get("health_events", []) if r["title"].startswith("sleep_tags")]


# --- hydration -----------------------------------------------------------------------------------------------------------------------------

def test_hydration_flow_presets_beverages_and_goal(env):
    client, db = env
    doc_store.put(db, U1, "profile", "body", {"weight_kg": 70})
    g = N.hydration_target(70)
    r = client.post("/wellness/hydration/log", json={"preset": "glass"}, headers=H1)
    assert r.status_code == 201 and r.json()["effective_ml"] == 250 and r.json()["goal"]["goal_ml"] == g
    client.post("/wellness/hydration/log", json={"ml": 500, "type": "coffee"}, headers=H1)
    o = client.get("/wellness/hydration/overview", headers=H1).json()
    assert o["raw_ml"] == 750 and o["effective_ml"] == 650 and o["by_type"] == {"water": 250, "coffee": 500}
    row = db.rows("hydration_logs", user_id=U1)[1]
    assert row["amount_ml"] == 500 and row["drink_type"] == "coffee"                       # existing tracker storage keeps raw ml
    assert any(e["extracted_data"].get("amount_ml") == 500 for e in db.rows("extracted_health_events", user_id=U1))
    assert [p["ml"] for p in o["presets"]] == [150, 250, 500, 750, 1000]
    assert client.get("/wellness/hydration/overview", headers=H2).json()["raw_ml"] == 0


def test_reaching_the_goal_grows_the_garden_and_streak(env):
    client, db = env
    doc_store.put(db, U1, "profile", "body", {"weight_kg": 60})
    goal = N.hydration_target(60)
    left = goal
    while left > 0:
        ml = min(left, 1000)
        r = client.post("/wellness/hydration/log", json={"ml": ml}, headers=H1)
        left -= ml
    o = r.json()
    assert o["effective_ml"] >= goal and o["percent"] == 100 and o["reminders"]["slots"] == []
    assert o["streak"]["current"] == 1 and o["garden"]["goal_days"] == 1 and o["garden"]["total_litres"] >= goal / 1000 - 0.1
    again = client.get("/wellness/hydration/overview", headers=H1).json()
    assert again["garden"]["goal_days"] == 1                                                 # reading is idempotent


def test_fluid_restricted_user_gets_a_note_not_a_target(env):
    client, db = env
    db.tables["medical_conditions"] = [{"user_id": U1, "condition_name": "Chronic kidney disease", "id": "c", "created_at": "2026-01-01"}]
    r = client.post("/wellness/hydration/log", json={"preset": "cup"}, headers=H1)
    assert r.status_code == 201
    o = client.get("/wellness/hydration/overview", headers=H1).json()
    assert o["goal"]["goal_ml"] is None and "clinician" in o["message"] and o["percent"] is None and o["garden"] is None


def test_workout_day_raises_the_goal(env):
    client, db = env
    doc_store.put(db, U1, "profile", "body", {"weight_kg": 70})
    base = client.get("/wellness/hydration/overview", headers=H1).json()["goal"]["goal_ml"]
    db.tables["activity_logs"] = [{"user_id": U1, "activity_type": "run", "duration_minutes": 60, "activity_date": now_utc().isoformat(),
                                   "id": "a1", "created_at": "c"}]
    o = client.get("/wellness/hydration/overview", headers=H1).json()["goal"]
    assert o["goal_ml"] == N.hydration_target(70, 60) > base and o["workout_bonus_ml"] > 0


@pytest.mark.parametrize("body", [{"ml": 2001}, {"ml": 5}, {"ml": -100}, {"ml": "lots"}, {}, {"preset": "tank"}, {"ml": 250, "date": "yesterday"},
                                  {"ml": 250, "date": (today() + timedelta(days=1)).isoformat()}, {"ml": 250, "date": "2020-01-01"}])
def test_hydration_validation(env, body):
    client, db = env
    detail_is_string(client.post("/wellness/hydration/log", json=body, headers=H1))
    assert not db.rows("hydration_logs")


def test_hydration_date_param_validation(env):
    client, _db = env
    detail_is_string(client.get("/wellness/hydration/overview?date=nope", headers=H1))
    detail_is_string(client.get(f"/wellness/hydration/overview?date={(today() + timedelta(days=2)).isoformat()}", headers=H1))
    assert client.get("/wellness/hydration/overview?tz_offset_minutes=9999", headers=H1).status_code == 422


def test_hydration_backfill_goes_to_that_day(env):
    client, _db = env
    y = (today() - timedelta(days=2)).isoformat()
    client.post("/wellness/hydration/log", json={"ml": 400, "date": y}, headers=H1)
    assert client.get(f"/wellness/hydration/overview?date={y}", headers=H1).json()["raw_ml"] == 400
    assert client.get("/wellness/hydration/overview", headers=H1).json()["raw_ml"] == 0


# --- medications -----------------------------------------------------------------------------------------------------------------------------

def hhmm():
    n = now_utc()
    return f"{n.hour:02d}:{n.minute:02d}"


def add_med(client, headers=H1, **kw):
    body = {"name": "Metformin", "dose_label": "500 mg", "times": [hhmm()], **kw}
    r = client.post("/wellness/meds/schedules", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["schedule"]


def test_medication_schedule_today_dose_and_pill_counter(env):
    client, db = env
    s = add_med(client, pill_count=10)
    assert re.fullmatch(r"[a-f0-9]{12}", s["id"])
    t = client.get("/wellness/meds/today", headers=H1).json()
    item = t["items"][0]
    assert item["status"] == "due" and item["name"] == "Metformin" and "pharmacist or prescriber" in t["missed_dose_help"]
    r = client.post("/wellness/meds/dose", json={"schedule_id": s["id"], "time": item["time"], "status": "taken"}, headers=H1)
    assert r.status_code == 201 and r.json()["record"]["status"] == "taken"
    assert client.get("/wellness/meds/today", headers=H1).json()["items"][0]["status"] == "taken"
    assert client.get("/wellness/meds/schedules", headers=H1).json()["schedules"][0]["pill_count"] == 9
    client.post("/wellness/meds/dose", json={"schedule_id": s["id"], "time": item["time"], "status": "skipped", "reason": "side_effects"}, headers=H1)
    assert client.get("/wellness/meds/schedules", headers=H1).json()["schedules"][0]["pill_count"] == 10
    a = client.get("/wellness/meds/adherence?days=7", headers=H1).json()
    assert a["total"]["skipped"] == 1 and a["percent"] is None
    lb = client.get("/wellness/meds/logbook?days=14", headers=H1).json()
    assert lb["medications"][0]["skip_reasons"] == {"side_effects": 1} and "Medication logbook" in lb["text"]


def test_medication_update_pause_and_delete(env):
    client, _db = env
    s = add_med(client)
    r = client.put(f"/wellness/meds/schedules/{s['id']}", json={"active": False}, headers=H1)
    assert r.status_code == 200 and r.json()["schedule"]["active"] is False and r.json()["schedule"]["name"] == "Metformin"
    assert client.get("/wellness/meds/today", headers=H1).json()["items"] == []
    assert client.delete(f"/wellness/meds/schedules/{s['id']}", headers=H1).json()["deleted"] is True
    assert client.delete(f"/wellness/meds/schedules/{s['id']}", headers=H1).status_code == 404


def test_medication_idor(env):
    client, _db = env
    s = add_med(client)
    assert client.get("/wellness/meds/schedules", headers=H2).json()["schedules"] == []
    assert client.get("/wellness/meds/today", headers=H2).json()["items"] == []
    assert client.put(f"/wellness/meds/schedules/{s['id']}", json={"name": "Hacked"}, headers=H2).status_code == 404
    assert client.delete(f"/wellness/meds/schedules/{s['id']}", headers=H2).status_code == 404
    r = client.post("/wellness/meds/dose", json={"schedule_id": s["id"], "time": hhmm(), "status": "taken"}, headers=H2)
    assert r.status_code == 404
    assert client.get("/wellness/meds/schedules", headers=H1).json()["schedules"][0]["name"] == "Metformin"
    assert client.delete("/wellness/meds/schedules/not-a-real-id", headers=H1).status_code == 404


@pytest.mark.parametrize("body", [
    {"name": "", "times": ["08:00"]}, {"name": "x"}, {"name": "x", "times": ["99:00"]}, {"name": "x", "times": ["08:00"], "weekdays": [9]},
    {"name": "x", "times": ["08:00"], "kind": "wizard"}, {"name": "x" * 500, "times": ["08:00"], "pill_count": "many"},
    {"name": "x", "times": ["08:00"], "start_date": "soon"}, {"name": "x", "kind": "cycle_pill", "times": ["21:00"]},
    {"name": "x", "times": "08:00"}, {"name": ["a"], "times": ["08:00"]},
])
def test_medication_schedule_validation(env, body):
    client, _db = env
    detail_is_string(client.post("/wellness/meds/schedules", json=body, headers=H1))


def test_dose_validation(env):
    client, _db = env
    s = add_med(client, times=["08:00"])
    base = {"schedule_id": s["id"], "time": "08:00", "status": "taken"}
    for patch in ({"status": "eaten"}, {"time": "13:00"}, {"time": None}, {"schedule_id": "zzz"}, {"schedule_id": None}, {"status": "skipped", "reason": "bored"},
                  {"status": "snoozed", "snooze_minutes": 7}, {"site": "elbow"}, {"date": "2020-01-01"}, {"date": (today() + timedelta(days=1)).isoformat()}):
        detail_is_string(client.post("/wellness/meds/dose", json={**base, **patch}, headers=H1))


def test_interaction_checker_endpoint(env):
    client, db = env
    r = client.post("/wellness/meds/interactions", json={"names": ["Warfarin", "Ibuprofen", "Paracetamol"]}, headers=H1).json()
    assert r["interactions"][0]["level"] == "high" and "pharmacist" in r["interactions"][0]["message"] and r["lookup"] == "curated"
    assert client.post("/wellness/meds/interactions", json={"names": ["Paracetamol"]}, headers=H1).json()["interactions"] == []
    db.tables["allergies"] = [{"user_id": U1, "allergen": "Penicillin", "id": "al", "created_at": "c"}]
    w = client.post("/wellness/meds/interactions", json={"names": ["Augmentin"]}, headers=H1).json()["allergy_warnings"]
    assert w and w[0]["allergen"] == "Penicillin"
    assert client.post("/wellness/meds/interactions", json={"names": ["Augmentin"]}, headers=H2).json()["allergy_warnings"] == []   # allergies are per user
    add_med(client, name="Insulin glargine")
    both = client.post("/wellness/meds/interactions", json={"names": [], "include_my_medicines": True, "context": {"calorie_deficit": True}}, headers=H1).json()
    assert any(i["rule"] == "hypoglycaemia" for i in both["interactions"])
    detail_is_string(client.post("/wellness/meds/interactions", json={"names": "warfarin"}, headers=H1))
    detail_is_string(client.post("/wellness/meds/interactions", json={"names": ["a"] * 50}, headers=H1))


def test_schedules_list_carries_warnings_for_my_medicines(env):
    client, _db = env
    add_med(client, name="Warfarin")
    r = client.post("/wellness/meds/schedules", json={"name": "Ibuprofen", "times": ["09:00"]}, headers=H1).json()
    assert r["interactions"] and r["interactions"][0]["rule"] == "warfarin_nsaid"


def test_glp1_tracker_and_log(env):
    client, db = env
    s = add_med(client, name="Semaglutide", kind="glp1", weekdays=[today().weekday()], dose_label="0.5 mg")
    g = client.get("/wellness/meds/glp1", headers=H1).json()
    assert g["detected"] and g["schedule"]["dose_day_today"] and "prescriber decides" in g["note"]
    client.post("/wellness/meds/dose", json={"schedule_id": s["id"], "time": hhmm(), "status": "taken", "site": "abdomen_left"}, headers=H1)
    g = client.get("/wellness/meds/glp1", headers=H1).json()
    assert g["schedule"]["suggested_site"] == "abdomen_right" and g["schedule"]["days_until"] == 7
    r = client.post("/wellness/meds/glp1/log", json={"appetite": 2, "nausea": 8, "notes": "queasy mornings"}, headers=H1)
    assert r.status_code == 201 and any("prescriber" in n for n in r.json()["nudges"])
    assert not re.search(r"\b(increase|decrease|reduce|double|skip your dose)\b", " ".join(r.json()["nudges"]), re.I)
    detail_is_string(client.post("/wellness/meds/glp1/log", json={"nausea": 99}, headers=H1))
    detail_is_string(client.post("/wellness/meds/glp1/log", json={}, headers=H1))
    assert client.get("/wellness/meds/glp1", headers=H2).json()["recent_logs"] == []
    danger = client.post("/wellness/meds/glp1/log", json={"nausea": 9, "notes": CHEST}, headers=H1).json()
    assert danger["status"] == "safety" and danger["saved"] is False
    assert all("chest pain" not in str(r["data"]) for r in db.tables["health_events"])


# --- mind ----------------------------------------------------------------------------------------------------------------------------------------

def test_mind_checkin_pixels_and_overview(env):
    client, db = env
    r = client.post("/wellness/mind/checkin", json={"face": 4, "activities": ["exercise", "social"], "notes": "good walk"}, headers=H1)
    assert r.status_code == 201 and r.json()["level"] == 4 and r.json()["activities"] == ["exercise", "social"]
    assert db.rows("mood_logs", user_id=U1)[0]["intensity"] == 8 and "Activities: exercise, social" in db.rows("mood_logs")[0]["notes"]
    px = client.get("/wellness/mind/pixels", headers=H1).json()
    assert px["logged_days"] == 1 and any(d["level"] == 4 for d in px["days"])
    assert client.get("/wellness/mind/pixels", headers=H2).json()["logged_days"] == 0
    o = client.get("/wellness/mind/overview", headers=H1).json()
    assert o["entries"][0]["activities"] == ["exercise", "social"] and o["screen"]["due"] is True and o["average_mood"] == 8
    low = client.post("/wellness/mind/checkin", json={"mood": 1}, headers=H1).json()
    assert "crisis line" in low["support"] or "emergency number" in low["support"]


def test_year_pixels_keep_old_days_even_when_tracker_rows_roll_off(env):
    client, db = env
    year = today().year
    doc_store.put(db, U1, "mind_pixels", str(year), {"days": {f"{year}-01-02": {"m": 9.0, "n": 1}}})
    client.post("/wellness/mind/checkin", json={"mood": 5}, headers=H1)
    px = client.get(f"/wellness/mind/pixels?year={year}", headers=H1).json()
    assert px["logged_days"] == 2 and next(d for d in px["days"] if d["date"] == f"{year}-01-02")["level"] == 5


@pytest.mark.parametrize("body", [{}, {"mood": 0}, {"mood": 11}, {"mood": "ok"}, {"mood": 5, "activities": ["skydiving"]}, {"mood": 5, "activities": "run"},
                                  {"mood": 5, "stress": 20}, {"face": 6}, {"mood": 5, "date": "never"}])
def test_checkin_validation(env, body):
    client, db = env
    detail_is_string(client.post("/wellness/mind/checkin", json=body, headers=H1))
    assert not db.rows("mood_logs")


@pytest.mark.parametrize("text", [URGENT, CHEST])
def test_urgent_text_in_checkin_returns_the_safety_response_and_stores_nothing(env, text):
    client, db = env
    r = client.post("/wellness/mind/checkin", json={"mood": 2, "notes": text}, headers=H1)
    j = r.json()
    assert r.status_code == 201 and j["status"] == "safety" and j["saved"] is False and j["message"] and "entry" not in j
    assert not db.rows("mood_logs") and not db.rows("extracted_health_events")


@pytest.mark.parametrize("text", [URGENT, CHEST])
def test_urgent_text_in_journal_returns_the_safety_response_and_stores_nothing(env, text):
    client, db = env
    j = client.post("/wellness/mind/journal", json={"text": text, "local_only": True}, headers=H1).json()
    assert j["status"] == "safety" and j["saved"] is False
    assert client.get("/wellness/mind/journal", headers=H1).json()["entries"] == []
    assert not [r for r in db.tables.get("health_events", []) if r["data"].get("kind") == "journal"]


def test_crisis_message_gives_crisis_resources(env):
    client, _db = env
    msg = client.post("/wellness/mind/journal", json={"text": URGENT}, headers=H1).json()["message"]
    assert "988" in msg or "emergency number" in msg


def test_journal_roundtrip_local_only_flag_and_idor(env):
    client, db = env
    a = client.post("/wellness/mind/journal", json={"text": "A quiet day, felt calm.", "local_only": True, "mood": 7}, headers=H1)
    b = client.post("/wellness/mind/journal", json={"text": "Shareable thoughts."}, headers=H1)
    assert a.status_code == 201 and a.json()["entry"]["local_only"] is True and b.json()["entry"]["local_only"] is False
    entries = client.get("/wellness/mind/journal", headers=H1).json()["entries"]
    assert len(entries) == 2 and {e["local_only"] for e in entries} == {True, False}
    jid = a.json()["entry"]["id"]
    assert client.get("/wellness/mind/journal", headers=H2).json()["entries"] == []
    assert client.delete(f"/wellness/mind/journal/{jid}", headers=H2).status_code == 404
    assert len(client.get("/wellness/mind/journal", headers=H1).json()["entries"]) == 2
    assert client.delete(f"/wellness/mind/journal/{jid}", headers=H1).json()["deleted"] is True
    assert client.delete("/wellness/mind/journal/short", headers=H1).status_code == 404
    # journal text is never mirrored into the analytics events any AI context is built from
    assert not db.rows("extracted_health_events")
    for bad in ({"text": ""}, {"text": "hi", "local_only": "yes"}, {}):
        detail_is_string(client.post("/wellness/mind/journal", json=bad, headers=H1))


def test_screening_flow(env):
    client, _db = env
    q = client.get("/wellness/mind/screen?kind=gad2", headers=H1).json()
    assert len(q["questions"]) == 2 and len(q["options"]) == 4
    r = client.post("/wellness/mind/screen", json={"kind": "phq2", "answers": [2, 1]}, headers=H1)
    assert r.status_code == 201 and r.json()["suggest_talking_to_someone"] and "diagnos" not in r.json()["message"].lower()
    assert client.get("/wellness/mind/overview", headers=H1).json()["screen"]["due"] is False
    assert client.get("/wellness/mind/overview", headers=H2).json()["screen"]["due"] is True
    detail_is_string(client.post("/wellness/mind/screen", json={"kind": "phq2", "answers": [5, 1]}, headers=H1))
    detail_is_string(client.post("/wellness/mind/screen", json={"kind": "phq9", "answers": [1, 1]}, headers=H1))
    assert client.get("/wellness/mind/screen?kind=zzz", headers=H1).status_code == 422


def test_exercises_and_insights(env):
    client, _db = env
    ex = client.get("/wellness/mind/exercises", headers=H1).json()
    assert {e["id"] for e in ex["exercises"]} >= {"box_breathing", "grounding_54321"}
    ins = client.get("/wellness/mind/insights", headers=H1).json()
    assert ins["insights"] == [] and ins["data_gaps"]


def test_mood_insights_from_logged_days(env):
    client, db = env
    for i in range(14):
        day = (today() - timedelta(days=i)).isoformat()
        client.post("/wellness/mind/checkin", json={"mood": 8 if i % 2 == 0 else 4, "date": day}, headers=H1)
        db.tables.setdefault("activity_logs", []).append({"user_id": U1, "activity_type": "walk", "duration_minutes": 30,
                                                          "activity_date": f"{day}T10:00:00+00:00", "id": f"a{i}", "created_at": "c"}) if i % 2 == 0 else None
    ins = client.get("/wellness/mind/insights?days=30", headers=H1).json()
    assert any(i["factor"] == "exercise" and "tended to" in i["text"] for i in ins["insights"])


# --- notifications API ----------------------------------------------------------------------------------------------------------------------------

def test_notification_settings_roundtrip_and_validation(env):
    client, _db = env
    s = client.get("/notifications/settings", headers=H1).json()
    assert s["settings"]["channels"] == {"in_app": True, "email": False, "push": False} and s["channels"]["push"]["available"] is False
    r = client.put("/notifications/settings", json={"daily_cap": 3, "types": {"water": False}, "tz_offset_minutes": 330}, headers=H1).json()
    assert r["settings"]["daily_cap"] == 3 and r["settings"]["types"]["water"] is False and r["settings"]["quiet_hours"]["enabled"] is False
    assert client.get("/notifications/settings", headers=H2).json()["settings"]["daily_cap"] == 5
    for bad in ({"daily_cap": 500}, {"channels": {"sms": True}}, {"quiet_hours": {"start": "xx"}}, {"types": {"water": "no"}}, {"tz_offset_minutes": 5000}):
        detail_is_string(client.put("/notifications/settings", json=bad, headers=H1))


def test_notifications_list_generate_and_mark_read(env):
    client, _db = env
    s = add_med(client, name="Metformin", times=[hhmm()])
    client.put("/notifications/settings", json={"types": {"water": False, "winddown": False}}, headers=H1)
    out = client.get("/notifications", headers=H1).json()
    assert out["unread_count"] == 1 and out["notifications"][0]["kind"] == "med"
    text = out["notifications"][0]["title"] + out["notifications"][0]["body"]
    assert "Metformin" not in text and not re.search(r"\d", text)
    assert client.get("/notifications", headers=H1).json()["unread_count"] == 1                    # no duplicates on refresh
    # Isolation: user 2 never sees user 1's notifications. (User 2 may legitimately get their OWN wind-down notice
    # during the 30-minute window each day, so "no notifications at all" was clock-dependent.)
    h2 = client.get("/notifications", headers=H2).json()["notifications"]
    assert not {n["id"] for n in h2} & {n["id"] for n in out["notifications"]} and all(n["kind"] != "med" for n in h2)
    nid = out["notifications"][0]["id"]
    assert client.post("/notifications/read", json={"ids": [nid]}, headers=H2).json()["marked"] == 0     # IDOR: not theirs
    assert client.get("/notifications?refresh=false", headers=H1).json()["unread_count"] == 1
    assert client.post("/notifications/read", json={"ids": [nid]}, headers=H1).json() == {"status": "success", "marked": 1, "unread_count": 0}
    assert client.get("/notifications?unread_only=true&refresh=false", headers=H1).json()["notifications"] == []
    for bad in ({}, {"ids": "x"}, {"ids": [1]}, {"all": "yes"}, {"ids": ["a"] * 101}):
        detail_is_string(client.post("/notifications/read", json=bad, headers=H1))
    assert s["id"]


def test_notifications_survive_a_failing_generator(env, monkeypatch):
    client, _db = env
    import notifications

    def boom(*a, **k):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(notifications, "generate_due", boom)
    r = client.get("/notifications", headers=H1)
    assert r.status_code == 200 and "secret" not in r.text


def test_unexpected_failures_do_not_return_exception_text(env):
    client, db = env
    db.failures["sleep_logs"] = RuntimeError("secret internal detail")
    r = client.get("/wellness/sleep/overview", headers=H1)
    assert r.status_code == 500 and "secret internal detail" not in r.text
