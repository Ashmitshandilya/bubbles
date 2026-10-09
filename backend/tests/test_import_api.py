from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import health_logs
import import_api
from db_access import register_db_error_handlers
from tests.fake_db import FakeDB

H1, H2 = {"Authorization": "Bearer user-1"}, {"Authorization": "Bearer user-2"}


@pytest.fixture
def env():
    db = FakeDB()

    def get_user(a):
        if not a:
            raise HTTPException(status_code=401, detail="Missing token")
        return SimpleNamespace(id=a.removeprefix("Bearer "))

    app = FastAPI()
    register_db_error_handlers(app)
    app.include_router(health_logs.build_router(get_user, db))
    app.include_router(import_api.build_router(get_user, db))
    return TestClient(app), db


def test_weight_csv_with_kg_header_and_dedupe(env):
    c, _ = env
    csv_text = "Date,Weight (kg)\n2026-02-01,80.4\n2026-02-02,80.1\n2026-02-03,bad\n2026-02-04,5\n"
    r = c.post("/import/csv", json={"kind": "weight", "csv_text": csv_text}, headers=H1)
    assert r.status_code == 201 and r.json()["imported"] == 2 and r.json()["rows_skipped"] == 2
    again = c.post("/import/csv", json={"kind": "weight", "csv_text": csv_text}, headers=H1).json()
    assert again["imported"] == 0 and again["duplicates_skipped"] == 2
    entries = c.get("/health/weight?days=730", headers=H1).json()["entries"]
    assert len(entries) == 2 and entries[0]["weight"] == pytest.approx(176.6, abs=0.3)
    assert c.get("/health/weight?days=730", headers=H2).json()["entries"] == []


def test_lb_semicolon_and_other_kinds(env):
    c, _ = env
    assert c.post("/import/csv", json={"kind": "weight", "csv_text": "date;weight (lb)\n2026-01-01;170\n"}, headers=H1).json()["imported"] == 1
    assert c.post("/import/csv", json={"kind": "sleep", "csv_text": "Day,Sleep duration (minutes)\n2026-01-01,420\n2026-01-02,380\n"}, headers=H1).json()["imported"] == 2
    assert c.get("/health/sleep?days=730", headers=H1).json()["entries"][0]["duration"] in (7.0, 6.33)
    assert c.post("/import/csv", json={"kind": "hydration", "csv_text": "date,water (l)\n2026-01-01,1.5\n"}, headers=H1).json()["imported"] == 1
    assert c.get("/health/hydration?days=730", headers=H1).json()["entries"][0]["volume"] == 1500
    a = c.post("/import/csv", json={"kind": "activity", "csv_text": "date,activity,minutes\n2026-01-01,Yoga,30\n"}, headers=H1).json()
    assert a["imported"] == 1 and c.get("/health/activity?days=730", headers=H1).json()["entries"][0]["type"] == "Yoga"


@pytest.mark.parametrize("payload,status", [({"kind": "weight", "csv_text": ""}, 422), ({"kind": "mood", "csv_text": "a,b\n1,2"}, 422), ({"kind": "weight", "csv_text": "foo,bar\n1,2"}, 422),
                                             ({"kind": "weight"}, 422), ({"kind": "weight", "csv_text": "x" * 1_100_000}, 422), ([1], 422)])
def test_bad_input_is_a_clear_422(env, payload, status):
    c, _ = env
    r = c.post("/import/csv", json=payload, headers=H1)
    assert r.status_code == status and isinstance(r.json()["detail"], str)


def test_requires_auth_and_caps_rows(env):
    c, _ = env
    assert c.post("/import/csv", json={"kind": "weight", "csv_text": "date,weight\n2026-01-01,70"}).status_code == 401
    rows = "\n".join(f"2020-01-01,{60 + (i % 40) + i / 10000:.4f}" for i in range(2500))
    r = c.post("/import/csv", json={"kind": "weight", "csv_text": "date,weight\n" + rows}, headers=H1).json()
    assert r["imported"] + r["duplicates_skipped"] <= 2000 and "stopped after 2000 rows" in r["skipped"]
