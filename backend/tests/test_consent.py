"""Consent before a message goes to an outside AI model: the server decides, and emergencies never wait for it."""
from __future__ import annotations

import pytest

import consent
from fake_db import FakeDB

from test_chat_http_flow import H, OTHER, USER, env, send  # noqa: F401  (the same stateful app and stub model)


def revoke(env):
    consent.set_ai_chat(env.db, USER, False)


def test_without_a_yes_nothing_is_sent_to_the_model(env):
    revoke(env)
    res = send(env, "I have been feeling really tired this week and I do not know why")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["consent_required"] is True
    assert env.ai_calls == []
    assert "outside AI model" in body["response"] and "Settings" in body["response"]
    assert "urgent" in body["response"].lower()          # the safety pointer is always there


def test_with_a_yes_the_model_is_used_and_no_flag_is_raised(env):
    res = send(env, "I have been feeling really tired this week and I do not know why")
    assert res.status_code == 200 and res.json()["consent_required"] is False
    assert len(env.ai_calls) == 1


def test_an_emergency_is_answered_the_same_with_or_without_consent(env):
    revoke(env)
    res = send(env, "I have severe chest pain right now and I cannot breathe")
    body = res.json()
    assert body["safety"]["level"] == "RED" and body["consent_required"] is False
    assert env.ai_calls == []


def test_a_daily_log_is_still_understood_without_consent(env):
    revoke(env)
    res = send(env, "Slept 6h 42m. Drank about 1.8 L of water. Walked 6,420 steps. Cramps 4/10.")
    assert res.status_code == 200 and res.json()["consent_required"] is False
    assert env.ai_calls == []


def test_the_consent_endpoints_read_change_and_isolate(env):
    client = env.client
    assert client.get("/me/consent").status_code == 401
    mine = client.get("/me/consent", headers=H).json()
    assert mine["ai_chat"] is True and mine["version"] == consent.VERSION
    off = client.put("/me/consent", json={"ai_chat": False}, headers=H).json()
    assert off["ai_chat"] is False
    assert client.get("/me/consent", headers={"Authorization": "Bearer tok2"}).json()["ai_chat"] is True   # another person is unaffected
    assert client.put("/me/consent", json={"ai_chat": "yes"}, headers=H).status_code == 422
    assert client.put("/me/consent", json=[], headers=H).status_code == 422
    assert client.put("/me/consent", json={"ai_chat": True}, headers=H).json()["ai_chat"] is True


def test_an_older_version_of_the_yes_does_not_count(env):
    from doc_store import put
    put(env.db, USER, consent.KIND, consent.KEY, {"accepted": True, "version": "2020-01", "at": "x"})
    assert consent.has_ai_consent(env.db, USER) is False


def test_unreadable_consent_means_no(env):
    class Broken:
        def table(self, *_):
            raise RuntimeError("database down")
    assert consent.has_ai_consent(Broken(), USER) is False


def test_an_urgent_message_without_consent_gets_the_fixed_urgent_text_not_an_ai_question(env):
    revoke(env)
    res = send(env, "I have had a little chest tightness since this morning")
    body = res.json()
    assert body["safety"]["state"] == "URGENT"
    assert body["consent_required"] is True and env.ai_calls == []
    assert "prompt attention" in body["response"] and "outside AI model" not in body["response"]


def test_waiting_for_the_yes_saves_nothing_so_the_resend_does_not_count_twice(env):
    revoke(env)
    text = "I have had a headache 6/10 for three days"
    first = send(env, text).json()
    assert first["consent_required"] is True
    before = [e for e in env.db.rows("extracted_health_events") if "headache" in str(e.get("extracted_data", "")).lower()]
    assert before == []
    consent.set_ai_chat(env.db, USER, True)
    send(env, text)           # the app asks again after the yes, as a new message
    after = [e for e in env.db.rows("extracted_health_events") if "headache" in str(e.get("extracted_data", "")).lower()]
    assert len(after) <= 1


def test_the_card_survives_a_replay_and_a_reload(env):
    revoke(env)
    first = send(env, "I have been feeling really tired this week and I do not know why", mid="11111111-1111-4111-8111-111111111111").json()
    again = send(env, "I have been feeling really tired this week and I do not know why", conv=first["conversation_id"], mid="11111111-1111-4111-8111-111111111111").json()
    assert again.get("replayed") is True and again["consent_required"] is True
    history = env.client.get(f"/chat/conversations/{first['conversation_id']}/messages", headers=H).json()["messages"]
    assert any(m.get("consent_required") is True for m in history)
