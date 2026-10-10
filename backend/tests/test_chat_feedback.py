"""Thumbs on Bubbles replies: ownership, validation, replacement, no free text, authentication."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import chat_feedback
from tests.fake_db import FakeDB

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
H1, H2 = {"Authorization": "Bearer t1"}, {"Authorization": "Bearer t2"}
REPLY, USER_MSG, OTHERS = "reply-aaaaaaaa-0001", "user-bbbbbbbb-0001", "reply-cccccccc-0002"


@pytest.fixture()
def env():
    db = FakeDB({"t1": U1, "t2": U2})
    db.tables["chat_messages"] = [
        {"id": REPLY, "user_id": U1, "role": "bubbles", "content": "hello"},
        {"id": USER_MSG, "user_id": U1, "role": "user", "content": "hi"},
        {"id": OTHERS, "user_id": U2, "role": "bubbles", "content": "private"},
    ]

    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        try:
            return db.auth.get_user(authorization[7:]).user
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    app = FastAPI()
    app.include_router(chat_feedback.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def test_requires_authentication(env):
    client, _ = env
    assert client.post("/chat/feedback", json={"message_id": REPLY, "rating": "up"}).status_code == 401
    assert client.get("/chat/feedback?message_ids=" + REPLY).status_code == 401


def test_rate_and_read_back_and_replace(env):
    client, _ = env
    r = client.post("/chat/feedback", json={"message_id": REPLY, "rating": "down", "reason": "unclear"}, headers=H1)
    assert r.status_code == 201 and r.json()["rating"] == "down" and r.json()["reason"] == "unclear"
    got = client.get(f"/chat/feedback?message_ids={REPLY},{USER_MSG}", headers=H1).json()["ratings"]
    assert got == {REPLY: {"rating": "down", "reason": "unclear"}}
    # changing your mind replaces it, and a thumbs up carries no reason
    client.post("/chat/feedback", json={"message_id": REPLY, "rating": "up", "reason": "unclear"}, headers=H1)
    assert client.get(f"/chat/feedback?message_ids={REPLY}", headers=H1).json()["ratings"][REPLY] == {"rating": "up", "reason": None}


def test_only_your_own_bubbles_replies_can_be_rated(env):
    client, _ = env
    assert client.post("/chat/feedback", json={"message_id": OTHERS, "rating": "up"}, headers=H1).status_code == 404
    assert client.post("/chat/feedback", json={"message_id": USER_MSG, "rating": "up"}, headers=H1).status_code == 404
    # another user never sees your rating
    client.post("/chat/feedback", json={"message_id": REPLY, "rating": "up"}, headers=H1)
    assert client.get(f"/chat/feedback?message_ids={REPLY}", headers=H2).json()["ratings"] == {}


@pytest.mark.parametrize("body", [
    {"message_id": REPLY, "rating": "meh"},
    {"message_id": REPLY, "rating": "down", "reason": "free text about my chest pain"},
    {"message_id": "x", "rating": "up"},
    {"rating": "up"},
    [],
])
def test_bad_requests_are_422_with_a_plain_message(env, body):
    client, _ = env
    r = client.post("/chat/feedback", json=body, headers=H1)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_stores_only_the_fixed_fields(env):
    client, db = env
    client.post("/chat/feedback", json={"message_id": REPLY, "rating": "down", "reason": "too_long", "note": "secret words"}, headers=H1)
    stored = [row for row in db.tables["health_events"] if row.get("event_type") == "bubbles_doc"]
    assert len(stored) == 1 and set(stored[0]["data"]["payload"]) == {"rating", "reason", "at"}
    assert "hello" not in str(stored[0]) and "secret" not in str(stored[0])
