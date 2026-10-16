"""Granular consent: everything off by default, each change logged, the trail survives a deletion, enforced on the server."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

import consent
import consent_ledger as L
import doc_store
from fake_db import FakeDB
from test_chat_http_flow import H, USER, env, send  # noqa: F401


@pytest.fixture()
def db():
    return FakeDB({"tok": USER})


def test_a_new_person_has_every_choice_off(db):
    states = L.state(db, USER)
    assert {s["purpose"] for s in states} == set(L.PURPOSES)
    assert not any(s["granted"] for s in states)
    assert not L.is_granted(db, USER, "health_memory_from_chat") and not L.is_granted(db, USER, "ai_chat_processing")


def test_each_change_is_logged_and_withdrawal_is_as_easy_as_the_yes(db):
    L.set_purpose(db, USER, "health_memory_from_chat", True, "settings")
    assert L.is_granted(db, USER, "health_memory_from_chat")
    L.set_purpose(db, USER, "health_memory_from_chat", False, "settings")
    assert not L.is_granted(db, USER, "health_memory_from_chat")
    log = L.history(db, USER)
    assert [(r["purpose"], r["granted"]) for r in log] == [("health_memory_from_chat", False), ("health_memory_from_chat", True)]
    assert all(r["source"] == "settings" for r in log)


def test_a_choice_that_is_not_offered_yet_cannot_be_granted(db):
    with pytest.raises(ValueError):
        L.set_purpose(db, USER, "community_visibility", True)
    with pytest.raises(KeyError):
        L.set_purpose(db, USER, "nope", True)
    assert not L.is_granted(db, USER, "community_visibility")


def test_the_old_ai_switch_and_the_new_one_are_the_same_answer(db):
    consent.set_ai_chat(db, USER, True)
    assert L.is_granted(db, USER, "ai_chat_processing")
    L.set_purpose(db, USER, "ai_chat_processing", False, "chat_card")
    assert not consent.has_ai_consent(db, USER)
    assert L.history(db, USER)[0]["source"] == "chat_card"


def test_the_trail_survives_delete_all_my_data_but_the_choices_do_not(db):
    L.set_purpose(db, USER, "email_reminders", True, "settings")
    doc_store.delete_everything(db, USER)
    assert not L.is_granted(db, USER, "email_reminders")
    assert [r["purpose"] for r in L.history(db, USER)] == ["email_reminders"]


def test_the_api_lists_changes_and_refuses_bad_input(env):
    c = env.client
    r = c.get("/consents", headers=H).json()
    assert r["status"] == "success" and not any(x["granted"] for x in r["consents"] if x["purpose"] == "partner_sharing")
    assert c.put("/consents/partner_sharing", headers=H, json={"granted": True, "source": "settings"}).status_code == 200
    assert c.put("/consents/partner_sharing", headers=H, json={"granted": "yes"}).status_code == 422
    assert c.put("/consents/unknown", headers=H, json={"granted": True}).status_code == 404
    assert c.put("/consents/community_visibility", headers=H, json={"granted": True}).status_code == 409
    hist = c.get("/consents/history", headers=H).json()["history"]
    assert hist[0]["purpose"] == "partner_sharing" and hist[0]["granted"] is True
    assert c.get("/consents").status_code in (401, 403)


def test_without_the_memory_choice_nothing_is_picked_out_of_chat(env):
    L.set_purpose(env.db, USER, "health_memory_from_chat", False, "settings")
    res = send(env, "I have had a headache since yesterday and I slept badly")
    assert res.status_code == 200, res.text
    assert res.json().get("health_events") in ([], None)
