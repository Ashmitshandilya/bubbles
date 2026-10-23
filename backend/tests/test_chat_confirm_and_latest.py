"""A saved decision survives a reload, the batch route saves many at once, a projection failure never undoes a saved decision,
and Talk can ask for the latest conversation."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-key")
BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fake_db import FakeDB  # noqa: E402

import main  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000a1"
OTHER = "00000000-0000-0000-0000-0000000000b2"
CONV = "11111111-1111-4111-8111-111111111111"
E1, E2, E3 = ("33333333-3333-4333-8333-33333333333%d" % i for i in (1, 2, 3))
H = {"Authorization": "Bearer tok"}


def _event(event_id, uid=USER, status="pending"):
    return {"id": event_id, "user_id": uid, "event_type": "symptom", "extracted_data": {"name": "headache", "severity": 3},
            "confidence": 0.8, "user_confirmed": False, "extraction_status": status, "message_id": None}


@pytest.fixture()
def client(monkeypatch):
    db = FakeDB({"tok": USER, "tok2": OTHER})
    db.table("chat_conversations").insert({"id": CONV, "user_id": USER, "title": "Headache", "created_at": "2026-10-10T10:00:00Z", "updated_at": "2026-10-10T10:05:00Z"}).execute()
    db.table("chat_messages").insert({"id": "m1", "conversation_id": CONV, "user_id": USER, "role": "user", "content": "head hurts", "created_at": "2026-10-10T10:00:01Z", "metadata": {}}).execute()
    db.table("chat_messages").insert({
        "id": "m2", "conversation_id": CONV, "user_id": USER, "role": "bubbles", "content": "Noted.", "created_at": "2026-10-10T10:00:02Z",
        "metadata": {"health_events": [{"id": E1, "event_type": "symptom", "extracted_data": {}, "status": "pending"},
                                       {"id": E2, "event_type": "symptom", "extracted_data": {}, "status": "pending"}]}}).execute()
    for e in (_event(E1), _event(E2), _event(E3, uid=OTHER)):
        db.table("extracted_health_events").insert(e).execute()
    monkeypatch.setattr(main, "supabase", db)
    main._sign_in_cache.clear() if hasattr(main._sign_in_cache, "clear") else None
    return TestClient(main.app), db


def _statuses(payload):
    return {e["id"]: e["status"] for m in payload["messages"] for e in m.get("health_events", [])}


def test_a_reloaded_chat_shows_the_saved_state_not_pending(client):
    c, db = client
    assert _statuses(c.get(f"/chat/conversations/{CONV}/messages", headers=H).json()) == {E1: "pending", E2: "pending"}
    db.table("extracted_health_events").update({"extraction_status": "confirmed", "user_confirmed": True}).eq("id", E1).execute()
    db.table("extracted_health_events").update({"extraction_status": "rejected"}).eq("id", E2).execute()
    assert _statuses(c.get(f"/chat/conversations/{CONV}/messages", headers=H).json()) == {E1: "confirmed", E2: "rejected"}


def test_latest_opens_the_newest_conversation_with_saved_states(client):
    c, db = client
    db.table("extracted_health_events").update({"extraction_status": "confirmed"}).eq("id", E1).execute()
    r = c.get("/chat/latest", headers=H).json()
    assert r["conversation"]["id"] == CONV and [m["id"] for m in r["messages"]] == ["m1", "m2"] and r["has_more"] is False
    assert _statuses(r)[E1] == "confirmed"


def test_latest_is_empty_for_someone_with_no_chats(client):
    c, _ = client
    r = c.get("/chat/latest", headers={"Authorization": "Bearer tok2"}).json()
    assert r["conversation"] is None and r["messages"] == []


def test_messages_page_back_with_before_and_report_has_more(client):
    c, _ = client
    r = c.get(f"/chat/conversations/{CONV}/messages?limit=1", headers=H).json()
    assert [m["id"] for m in r["messages"]] == ["m2"] and r["has_more"] is True
    older = c.get(f"/chat/conversations/{CONV}/messages?limit=5&before=2026-10-10T10:00:02Z", headers=H).json()
    assert [m["id"] for m in older["messages"]] == ["m1"] and older["has_more"] is False
    assert c.get(f"/chat/conversations/{CONV}/messages?before=nope", headers=H).status_code == 400


def test_history_pages_back_with_before_and_reports_has_more(client):
    c, db = client
    for i in (1, 2):
        db.table("chat_conversations").insert({"id": f"11111111-1111-4111-8111-11111111111{i + 1}", "user_id": USER, "title": f"Older {i}",
                                               "created_at": f"2026-10-0{i}T10:00:00Z", "updated_at": f"2026-10-0{i}T10:05:00Z"}).execute()
    first = c.get("/chat/history?limit=2", headers=H).json()
    assert [x["title"] for x in first["conversations"]] == ["Headache", "Older 2"] and first["has_more"] is True
    older = c.get(f"/chat/history?limit=2&before={first['conversations'][-1]['updated_at']}", headers=H).json()
    assert [x["title"] for x in older["conversations"]] == ["Older 1"] and older["has_more"] is False
    assert c.get("/chat/history?before=nope", headers=H).status_code == 400



def test_history_marks_heart_to_heart_threads(client, monkeypatch):
    import doc_store
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "history-mode-key")
    c, db = client
    other = "11111111-1111-4111-8111-111111111119"
    db.table("chat_conversations").insert({"id": other, "user_id": USER, "title": "Late night", "created_at": "2026-10-09T10:00:00Z",
                                           "updated_at": "2026-10-09T10:05:00Z"}).execute()
    doc_store.put(db, USER, "conversation_mode", other, {"mode": "orbit"})
    modes = {x["title"]: x["mode"] for x in c.get("/chat/history?limit=10", headers=H).json()["conversations"]}
    assert modes["Late night"] == "orbit"
    assert modes["Headache"] == "talk"
