"""/organs/map and /organs/{organ_id} through FastAPI with the stateful fake database: auth, ownership, validation, sources."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import cycle_api  # noqa: E402
import health_logs  # noqa: E402
import organ_map_api  # noqa: E402
import organ_map_engine as E  # noqa: E402
from db_access import register_db_error_handlers  # noqa: E402
from fake_db import FakeDB, permission_denied  # noqa: E402
from test_routes_require_auth import TouchedDB, find_leaks, refuse  # noqa: E402

A, B = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
HA, HB = {"Authorization": "Bearer ta"}, {"Authorization": "Bearer tb"}
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def env():
    db = FakeDB({"ta": A, "tb": B})
    app = FastAPI()
    register_db_error_handlers(app)

    def get_user(authorization):
        uid = db.auth.tokens.get((authorization or "").removeprefix("Bearer ").strip())
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return type("U", (), {"id": uid})()

    for build in (organ_map_api.build_router, health_logs.build_router, cycle_api.build_router):
        app.include_router(build(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def add_event(db, uid, event_type, data, ago=1):
    moment = NOW - timedelta(days=ago)
    db.table("extracted_health_events").insert({
        "user_id": uid, "event_type": event_type, "extraction_status": "confirmed", "user_confirmed": True, "confidence": 1.0,
        "created_at": moment.isoformat(), "extracted_data": {**data, "date": moment.date().isoformat(), "_prov": {"source": "tracker"}},
    }).execute()


def by_id(body):
    return {o["organ_id"]: o for o in body["organs"]}


# ---- auth -----------------------------------------------------------------------------------------------------------

def test_every_route_refuses_without_credentials_and_never_touches_the_database():
    assert find_leaks(organ_map_api.build_router(refuse, TouchedDB())) == []


@pytest.mark.parametrize("path", ["/organs/map", "/organs/heart", "/organs/not-an-organ"])
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic ta"}])
def test_401_without_a_valid_token(env, path, headers):
    client, _db = env
    assert client.get(path, headers=headers).status_code == 401


def test_main_registers_the_router():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "app.include_router(build_organ_map_router(get_authenticated_user, supabase))" in source


# ---- validation -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("query", ["days=6", "days=181", "days=0", "days=-30", "days=abc", "days=30.5"])
def test_out_of_range_window_is_422(env, query):
    client, _db = env
    assert client.get(f"/organs/map?{query}", headers=HA).status_code == 422
    assert client.get(f"/organs/heart?{query}", headers=HA).status_code == 422


@pytest.mark.parametrize("days", [7, 30, 180])
def test_window_bounds_are_accepted(env, days):
    client, _db = env
    body = client.get(f"/organs/map?days={days}", headers=HA).json()
    assert body["status"] == "success" and body["window_days"] == days


def test_unknown_organ_is_404(env):
    client, _db = env
    r = client.get("/organs/spleen", headers=HA)
    assert r.status_code == 404 and "heart" in r.json()["detail"]


# ---- behaviour ------------------------------------------------------------------------------------------------------

def test_empty_account_is_all_gaps(env):
    client, _db = env
    body = client.get("/organs/map", headers=HA).json()
    assert body["not_a_diagnosis"] is True and body["counts"]["no_data"] == len(E.ORGANS) and body["unavailable"] == []
    assert [o["organ_id"] for o in body["organs"]] == list(E.ORGANS)


def test_owner_only(env):
    client, db = env
    add_event(db, A, "vital_sign", {"systolic_bp": 150, "diastolic_bp": 95})
    add_event(db, B, "symptom", {"symptom": "chest pain"})
    add_event(db, B, "hydration", {"amount_ml": 300})
    db.table("lab_results").insert({"user_id": B, "test_name": "TSH", "value": 12, "unit": "mIU/L", "tested_at": NOW.isoformat()}).execute()
    mine = by_id(client.get("/organs/map", headers=HA).json())
    assert mine["heart"]["status"] == "worth_watching" and mine["heart"]["safety"] is None
    assert [e["value"] for e in mine["heart"]["evidence"]] == ["150/95"]
    assert mine["kidneys_bladder"]["status"] == "no_data" and mine["thyroid"]["status"] == "no_data"
    theirs = by_id(client.get("/organs/map", headers=HB).json())
    assert theirs["heart"]["status"] == "talk_to_doctor" and theirs["thyroid"]["status"] == "talk_to_doctor"
    mine_ids = {e["id"] for o in mine.values() for e in o["evidence"]}
    theirs_ids = {e["id"] for o in theirs.values() for e in o["evidence"]}
    assert mine_ids and theirs_ids and not mine_ids & theirs_ids


def test_detail_matches_the_map(env):
    client, db = env
    add_event(db, A, "sleep", {"hours": 5}, 1)
    add_event(db, A, "sleep", {"hours": 5}, 2)
    add_event(db, A, "sleep", {"hours": 5}, 3)
    full = by_id(client.get("/organs/map?days=14", headers=HA).json())
    one = client.get("/organs/brain?days=14", headers=HA).json()
    assert one["status"] == "success" and one["window_days"] == 14 and one["organ"] == full["brain"]
    assert one["organ"]["status"] == "worth_watching" and "organs" not in one


def test_tracker_saves_flow_into_the_map(env):
    client, db = env
    r = client.post("/health/vitals", json={"blood_pressure": "182/100"}, headers=HA)
    assert r.status_code == 201, r.text
    for row in db.tables["extracted_health_events"]:  # the fake database stamps a fixed creation time; make it "now"
        row["created_at"] = NOW.isoformat()
    heart = client.get("/organs/heart", headers=HA).json()["organ"]
    assert heart["status"] == "talk_to_doctor" and heart["evidence"][0]["value"] == "182/100"
    assert heart["evidence_count"] == 1  # the primary row and its analytics mirror are not counted twice


def test_heavy_bleeding_from_the_cycle_log_is_urgent(env):
    client, _db = env
    today = NOW.date().isoformat()
    r = client.put(f"/cycle/day/{today}", json={"flow": "heavy", "soaking_hourly": True}, headers=HA)
    assert r.status_code == 200, r.text
    uterus = client.get("/organs/uterus_ovaries", headers=HA).json()["organ"]
    assert uterus["status"] == "talk_to_doctor" and list(uterus)[0] == "safety" and "urgent" in uterus["safety"]["message"].lower()


def test_conditions_older_than_the_window_still_count(env):
    client, db = env
    db.table("medical_conditions").insert({"user_id": A, "condition_name": "Hypothyroidism", "created_at": "2024-01-01T00:00:00+00:00"}).execute()
    assert client.get("/organs/thyroid", headers=HA).json()["organ"]["status"] == "worth_watching"


def test_a_failed_optional_source_is_named_not_hidden(env):
    client, db = env
    db.failures["lab_results"] = RuntimeError("lab table unreachable")
    body = client.get("/organs/map", headers=HA).json()
    assert body["status"] == "success" and "labs" in body["unavailable"]


def test_events_read_failure_is_an_error_not_an_empty_map(env):
    client, db = env
    db.failures["extracted_health_events"] = permission_denied("extracted_health_events")
    r = client.get("/organs/map", headers=HA)
    assert r.status_code >= 500 and "organs" not in r.text
