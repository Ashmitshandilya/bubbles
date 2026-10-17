"""Batch confirmation: one request saves many details, the decision is durable before anything is copied, pressing twice is harmless,
dismissing something saved is refused, another person's id is ignored, and a failed copy never turns a saved decision into an error."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-key")
BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import health_event_confirm as hec  # noqa: E402
from fake_db import FakeDB  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000a1"
OTHER = "00000000-0000-0000-0000-0000000000b2"
IDS = [f"33333333-3333-4333-8333-3333333333{i:02d}" for i in range(1, 13)]
H = {"Authorization": "Bearer tok"}


def _event(event_id, uid=USER, status="pending", name="headache"):
    return {"id": event_id, "user_id": uid, "event_type": "symptom", "extracted_data": {"name": name, "severity": 3},
            "confidence": 0.8, "user_confirmed": status == "confirmed", "extraction_status": status, "message_id": None}


@pytest.fixture()
def env(monkeypatch):
    db = FakeDB({})
    for i, event_id in enumerate(IDS[:10]):
        db.table("extracted_health_events").insert(_event(event_id, name=f"symptom {i}")).execute()
    db.table("extracted_health_events").insert(_event(IDS[10], uid=OTHER)).execute()
    db.table("extracted_health_events").insert({**_event(IDS[11]), "extraction_status": None}).execute()   # saved before statuses were written
    remembered: list[str] = []
    monkeypatch.setattr(hec, "promote_health_event", lambda **kw: remembered.append(kw["event_id"]) or {"promoted": True})
    monkeypatch.setattr(hec, "_compat_until", 0.0)

    def get_user(authorization):
        if authorization != "Bearer tok":
            raise HTTPException(status_code=401, detail="Authentication required")
        return SimpleNamespace(id=USER)

    app = FastAPI()
    app.include_router(hec.build_router(get_user, db))
    return TestClient(app), db, remembered


def _status(db, event_id):
    return next(r for r in db.table("extracted_health_events").select("*").execute().data if r["id"] == event_id)["extraction_status"]


def test_ten_decisions_are_one_request_and_become_ledger_rows_and_memory(env):
    c, db, remembered = env
    r = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": i, "confirmed": True} for i in IDS[:10]]})
    assert r.status_code == 200
    results = r.json()["results"]
    assert [x["id"] for x in results] == IDS[:10] and all(x["status"] == "confirmed" and x["projection"] == "queued" for x in results)
    assert all(_status(db, i) == "confirmed" for i in IDS[:10])
    assert len(db.rows("health_events")) == 10 and len(db.rows("symptoms")) == 10      # copied after the answer, in batches
    assert sorted(remembered) == sorted(IDS[:10])                                       # confirming remembers by the usual memory rules


def test_a_mix_of_save_and_dismiss_updates_both(env):
    c, db, _ = env
    r = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}, {"id": IDS[1], "confirmed": False}]})
    assert [x["status"] for x in r.json()["results"]] == ["confirmed", "rejected"]
    assert _status(db, IDS[0]) == "confirmed" and _status(db, IDS[1]) == "rejected"
    assert len(db.rows("health_events")) == 1   # a dismissed detail is never copied


def test_a_row_without_a_status_can_be_saved_too(env):
    c, db, _ = env
    r = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[11], "confirmed": True}]})
    assert r.json()["results"][0]["status"] == "confirmed" and _status(db, IDS[11]) == "confirmed"


def test_pressing_twice_changes_nothing_and_never_duplicates(env):
    c, db, _ = env
    body = {"decisions": [{"id": IDS[0], "confirmed": True}]}
    first = c.post("/health-events/confirmation", headers=H, json=body).json()["results"][0]
    second = c.post("/health-events/confirmation", headers=H, json=body).json()["results"][0]
    assert first["projection"] == "queued" and second["status"] == "confirmed" and second["projection"] == "done"
    assert len(db.rows("health_events")) == 1 and len(db.rows("symptoms")) == 1


def test_dismissing_something_already_saved_is_refused_with_409(env):
    c, db, _ = env
    c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]})
    out = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": False}]}).json()["results"][0]
    assert out["status"] == "error" and out["code"] == 409 and _status(db, IDS[0]) == "confirmed"
    assert c.patch(f"/health-events/{IDS[0]}/confirmation", headers=H, json={"confirmed": False}).status_code == 409


def test_another_persons_id_and_junk_ids_are_ignored(env):
    c, db, _ = env
    out = c.post("/health-events/confirmation", headers=H, json={"decisions": [
        {"id": IDS[10], "confirmed": True}, {"id": "not-an-id", "confirmed": True}, {"id": IDS[0], "confirmed": True}]}).json()["results"]
    assert [(x["id"], x["status"], x.get("code")) for x in out] == [(IDS[10], "error", 404), ("not-an-id", "error", 404), (IDS[0], "confirmed", None)]
    assert _status(db, IDS[10]) == "pending"


def test_a_withdrawn_detail_cannot_come_back(env):
    c, db, _ = env
    db.table("extracted_health_events").update({"extraction_status": "retracted"}).eq("id", IDS[0]).execute()
    out = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]}).json()["results"][0]
    assert out["code"] == 409 and _status(db, IDS[0]) == "retracted"


def test_a_failed_copy_never_turns_a_saved_decision_into_an_error(env, monkeypatch):
    c, db, _ = env

    def boom(**_k):
        raise RuntimeError("canonical table hiccup")
    monkeypatch.setattr(hec, "project_confirmed_events", boom)
    r = c.patch(f"/health-events/{IDS[0]}/confirmation", headers=H, json={"confirmed": True})
    assert r.status_code == 200 and r.json()["projection"]["status"] == "queued" and _status(db, IDS[0]) == "confirmed"


def test_a_failed_copy_is_tried_again_on_the_next_save(env, monkeypatch):
    c, db, _ = env
    real = hec.project_confirmed_events
    monkeypatch.setattr(hec, "project_confirmed_events", lambda **_k: (_ for _ in ()).throw(RuntimeError("down")))
    c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]})
    assert db.rows("health_events") == []
    monkeypatch.setattr(hec, "project_confirmed_events", real)
    c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]})
    assert len(db.rows("health_events")) == 1


def test_a_permission_error_switches_the_answer_to_compat(env, monkeypatch):
    c, db, _ = env

    def denied(**_k):
        raise RuntimeError("permission denied for table health_events (42501)")
    monkeypatch.setattr(hec, "project_confirmed_events", denied)
    c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]})
    out = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[1], "confirmed": True}]}).json()["results"][0]
    assert out["projection"] == "compat" and _status(db, IDS[1]) == "confirmed"


def test_the_update_failing_reports_an_error_per_item_not_a_crash(env):
    c, db, _ = env
    db.failures["extracted_health_events"] = RuntimeError("down")
    out = c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}]}).json()["results"][0]
    assert out["status"] == "error" and out["code"] == 500


def test_validation_and_auth(env):
    c, _, _ = env
    assert c.post("/health-events/confirmation", headers=H, json={"decisions": []}).status_code == 422
    assert c.post("/health-events/confirmation", headers=H, json={"decisions": [{"id": IDS[0], "confirmed": True}] * 31}).status_code == 422
    assert c.post("/health-events/confirmation", json={"decisions": [{"id": IDS[0], "confirmed": True}]}).status_code == 401
    assert c.patch(f"/health-events/{IDS[0]}/confirmation", json={"confirmed": True}).status_code == 401
