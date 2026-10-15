"""A5, safety first: passive-ideation wording (hits AND near-misses), the shared free-text gate, the tracker hook and India-first copy."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import health_logs
import mind_checkins as Mind
import safety_gate
from safety_engine import assess_safety
from tests.fake_db import FakeDB

U1 = "00000000-0000-0000-0000-000000000001"
H1 = {"Authorization": "Bearer t1"}

HITS = [
    "I feel like a burden to everyone",
    "I'm a burden to my family",
    "I have become a burden to everyone",
    "I feel like such a burden",
    "nobody would miss me",
    "No one would care if I disappeared",
    "nobody would notice if I was gone",
    "I feel worthless",
    "Im worthless",
    "I feel so worthless today",
    # Hinglish
    "main sabke liye bojh hoon",
    "mere jaane se kisi ko farak nahi padega",
    "koi meri kami mehsoos nahi karega",
    "main kisi kaam ka nahi hoon",
    "meri koi value nahi hai",
    "main bilkul bekaar hoon",
    "main worthless feel karta hoon",
]

NEAR_MISSES = [
    "I don't want to be a burden to my family",           # a wish about the future, common in caring for a parent
    "I do not want to become a burden on my kids when I'm old",
    "I wouldn't want to be a burden",
    "this phone is worthless",
    "he called me worthless",                              # someone else said it
    "I'm not worthless",
    "I don't feel worthless anymore",
    "I used to feel worthless years ago",
    "I felt worthless when I failed the exam last year",
    "my friend said she feels worthless",
    "my mother feels like a burden to everyone",
    "nobody would miss that show",
    "nobody would notice if I changed my hair",
    "the burden of work is heavy",
    "burden of proof",
    "What does it mean to feel worthless?",
    "mujhe nahi lagta main bojh hoon",
    "kisi kaam ka nahi hai ye phone",
    "main bekaar hoon yaar cooking mein",
]


@pytest.mark.parametrize("text", HITS)
def test_passive_ideation_is_caught(text):
    a = assess_safety(text)
    assert a.crisis, text
    assert a.state in ("EMERGENCY", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION"), text


@pytest.mark.parametrize("text", NEAR_MISSES)
def test_near_misses_stay_quiet(text):
    a = assess_safety(text)
    assert not a.crisis and a.state == "NO_REDFLAG", text


def test_existing_passive_ideation_is_unchanged():
    for text in ("everyone would be better off without me", "I want to die", "jeene ka mann nahi karta"):
        assert assess_safety(text).crisis, text


def test_gate_shape_and_crisis_only_mode():
    hit = safety_gate.safety_gate("I feel worthless")
    assert hit and hit["status"] == "safety" and hit["crisis"] and hit["saved"] is False
    assert "14416" in hit["message"] and "112" in hit["message"]
    assert safety_gate.safety_gate("a normal note", None, "") is None
    chest = "I have severe chest pain right now and I cannot breathe"
    assert safety_gate.safety_gate(chest)["status"] == "safety"
    assert safety_gate.safety_gate(chest, crisis_only=True) is None          # the symptom itself is what is being logged
    assert safety_gate.safety_gate("I feel worthless", crisis_only=True)["crisis"]


def test_mind_module_keeps_exporting_the_gate():
    assert Mind.safety_gate is safety_gate.safety_gate


def test_support_copy_is_india_first():
    assert "14416" in Mind.SUPPORT_NOTE and "112" in Mind.SUPPORT_NOTE
    positive = Mind.score_screen("phq2", [3, 3])
    assert "14416" in positive["message"]


# --- the old tracker form (POST /health/{slug}) is screened ----------------------------------------------------------------------------

@pytest.fixture()
def env():
    db = FakeDB({"t1": U1})

    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        return db.auth.get_user(authorization[7:]).user

    app = FastAPI()
    app.include_router(health_logs.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def _saved(db, table):
    return db.table(table).select("*").eq("user_id", U1).execute().data or []


def test_mood_note_with_crisis_wording_is_not_stored(env):
    client, db = env
    r = client.post("/health/mood", json={"mood": 2, "notes": "I feel like a burden to everyone"}, headers=H1)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "safety" and body["crisis"] is True and "14416" in body["message"]
    assert _saved(db, "mood_logs") == [] and _saved(db, "extracted_health_events") == []


def test_ordinary_mood_note_is_stored(env):
    client, db = env
    r = client.post("/health/mood", json={"mood": 7, "notes": "a good day, saw friends"}, headers=H1)
    assert r.status_code == 201 and r.json()["entry"]["mood"] == 7
    assert len(_saved(db, "mood_logs")) == 1


def test_symptom_name_only_stops_on_crisis_wording(env):
    client, db = env
    ok = client.post("/health/symptoms", json={"symptom": "Chest pain", "severity": 6}, headers=H1)
    assert ok.status_code == 201                                              # logging a symptom is not blocked by the symptom's own name
    blocked = client.post("/health/symptoms", json={"symptom": "I want to end my life"}, headers=H1)
    assert blocked.json()["status"] == "safety"
    assert len(_saved(db, "symptoms")) == 1


def test_notes_on_any_domain_are_screened(env):
    client, db = env
    r = client.post("/health/activity", json={"type": "Walk", "duration": 20, "notes": "I have severe chest pain right now and I cannot breathe"},
                    headers=H1)
    assert r.json()["status"] == "safety"
    assert _saved(db, "activity_logs") == []
