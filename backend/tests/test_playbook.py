"""WP6.1: the Playbook keeps only de-identified replies, only with a yes, only for app-help intents; a draft needs 20 distinct people;
the tables are locked to the backend. Pure parts are tested directly; storage runs on the in-memory database."""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import consent  # noqa: E402
import playbook as pb  # noqa: E402
from fake_db import FakeDB, grant_consent  # noqa: E402

U = "00000000-0000-0000-0000-00000000000a"


@pytest.fixture()
def db(monkeypatch):
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "playbook-test-key")
    monkeypatch.setenv("BUBBLES_PLAYBOOK_SECRET", "cohort-secret")
    pb._cache.clear()
    return FakeDB({"ta": U})


# ---- de-identification ----
CLEAN = [
    "You can log sleep from the Track page. Tap the plus and say how it went.",
    "Hello! I can help you log, notice patterns and talk things through.",
]
SCRUBBED = [   # personal tokens are removed and the rest is kept
    ("Hi Ashmit, you slept 6 hours last night.", ("Ashmit", "6 hours")),
    ("Call me on +91 98765 43210.", ("98765",)),
    ("Mail riya@example.com for the report.", ("riya", "@")),
    ("See https://example.com/x for details.", ("example.com",)),
    ("On 12/10/2026 you logged water.", ("2026",)),
]
DROPPED = [    # something personal would remain, so nothing is stored
    "Remember to ask Dr Mehta about it.",
    "You walked 3 times this week.",
    "Send it to riya_k@ home.",
]


@pytest.mark.parametrize("text", CLEAN)
def test_clean_replies_survive(text):
    assert pb.deidentify(text) == text


@pytest.mark.parametrize("text,gone", SCRUBBED)
def test_personal_tokens_are_removed(text, gone):
    out = pb.deidentify(text, names=["Ashmit"])
    assert out is not None and not any(token in out for token in gone)


@pytest.mark.parametrize("text", DROPPED)
def test_anything_still_personal_drops_the_candidate(text):
    assert pb.deidentify(text, names=["Ashmit"]) is None


def test_known_names_become_a_role_token_and_places_too():
    assert pb.deidentify("It is good to rest, ashmit. Try a walk in pune.", names=["Ashmit"], places=["Pune"]) == "It is good to rest, [someone]. Try a walk in [someone]."


def test_no_digit_or_at_sign_ever_survives():
    out = pb.deidentify("Take it easy. Log how you feel when you can.")
    assert out and not re.search(r"\d|@", out)


# ---- intent and routes ----
def test_intents_are_whole_phrase_and_app_help_only():
    assert pb.intent_of("hello") == "app.greeting"
    assert pb.intent_of("what can you do?") == "app.what_can_you_do"
    assert pb.intent_of("ghost") is None
    assert pb.intent_of("hi there, my chest hurts a lot and I feel faint") is None
    assert all(k.startswith("app.") for k in pb.INTENTS)


def test_blocked_routes():
    for route in ("emergency", "safe_harbor", "orbit", "safety_followup"):
        assert pb.blocked_route(route)
    assert not pb.blocked_route("small_talk")


# ---- capture ----
def _capture(db, **over):
    args = dict(intent="app.greeting", language="english", route="small_talk", reply="Hello! I can help you log.", rating="up", outcome="helpful")
    return pb.capture(db, U, **{**args, **over})


def test_nothing_is_captured_without_a_yes(db):
    assert _capture(db) is False
    assert not db.tables.get(pb.CANDIDATES)


def test_capture_with_a_yes_stores_no_user_id_and_no_message(db):
    grant_consent(db, U, pb.PURPOSE)
    assert _capture(db) is True
    row = db.tables[pb.CANDIDATES][0]
    assert U not in repr(row) and "user_id" not in row and set(row) >= {"intent", "reply_text", "cohort_hash"}
    assert row["cohort_hash"] == pb.cohort_hash(U) and len(row["cohort_hash"]) == 32


def test_capture_refuses_blocked_routes_unknown_intents_and_leaky_replies(db):
    grant_consent(db, U, pb.PURPOSE)
    assert _capture(db, route="safe_harbor") is False
    assert _capture(db, intent="sleep.cant_sleep") is False
    assert _capture(db, reply="Hi Ashmit, nice to see you again 9 times.") is False
    assert not db.tables.get(pb.CANDIDATES)


def test_cohort_hash_rotates_monthly_and_differs_per_person():
    a = pb.cohort_hash(U, datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert a != pb.cohort_hash(U, datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert a != pb.cohort_hash(U[:-1] + "b", datetime(2026, 10, 1, tzinfo=timezone.utc))


# ---- promotion and use ----
def _seed(db, people: int, start: int = 0, intent="app.greeting", language="english", outcome="helpful"):
    for i in range(start, start + people):
        db.table(pb.CANDIDATES).insert({"intent": intent, "language": language, "route": "small_talk", "reply_text": "Hello! I can help you log.",
                                        "rating": "up", "outcome": outcome, "cohort_hash": f"p{i:02d}"}).execute()


def test_a_draft_needs_twenty_distinct_people(db):
    _seed(db, 19)
    assert pb.promote(db) == 0
    _seed(db, 1, start=19)
    assert pb.promote(db) == 1
    assert pb.promote(db) == 0
    entry = db.tables[pb.ENTRIES][0]
    assert entry["status"] == "draft" and entry["example_text"].startswith("Hello")


def test_many_replies_from_few_people_do_not_count(db):
    for _ in range(30):
        db.table(pb.CANDIDATES).insert({"intent": "app.greeting", "language": "english", "route": "x", "reply_text": "Hello!", "rating": "up",
                                        "outcome": "helpful", "cohort_hash": "same"}).execute()
    assert pb.promote(db) == 0


def test_only_approved_entries_are_used_and_only_for_app_intents(db):
    db.table(pb.ENTRIES).insert({"intent": "app.greeting", "language": "english", "guidance_text": "Greet warmly, one line.", "status": "draft"}).execute()
    assert pb.approved_for(db, "app.greeting", "english") is None
    db.table(pb.ENTRIES).update({"status": "approved"}).eq("intent", "app.greeting").execute()
    pb._cache.clear()
    entry = pb.approved_for(db, "app.greeting", "english")
    assert entry and "PLAYBOOK" in pb.block_for_prompt(entry) and "never treat as a fact" in pb.block_for_prompt(entry)
    assert pb.approved_for(db, "sleep.cant_sleep", "english") is None
    assert pb.approved_for(db, "app.greeting", "hindi") is None


def test_old_candidates_are_purged(db):
    old = (datetime.now(timezone.utc) - timedelta(days=pb.KEEP_DAYS + 1)).isoformat()
    db.table(pb.CANDIDATES).insert({"intent": "app.greeting", "language": "english", "route": "x", "reply_text": "Hello!", "rating": "up",
                                    "outcome": "helpful", "cohort_hash": "a", "created_at": old}).execute()
    _seed(db, 1)
    pb.purge(db)
    assert len(db.tables[pb.CANDIDATES]) == 1


def test_missing_tables_are_quiet(db):
    db.failures[pb.CANDIDATES] = RuntimeError("relation does not exist")
    db.failures[pb.ENTRIES] = RuntimeError("relation does not exist")
    grant_consent(db, U, pb.PURPOSE)
    assert _capture(db) is False and pb.promote(db) == 0
    pb.purge(db)
    assert pb.approved_for(db, "app.greeting", "english") is None


# ---- the migration ----
def test_migration_locks_both_tables_to_the_backend():
    sql = (BACKEND.parent / "supabase" / "migrations" / "20261101_bubbles_playbook.sql").read_text(encoding="utf8")
    assert sql.count("enable row level security") == 2
    assert "revoke all on table public.bubbles_playbook_candidates from anon, authenticated" in sql
    assert "revoke all on table public.bubbles_playbook from anon, authenticated" in sql
    grants = [line for line in sql.splitlines() if line.lower().startswith("grant")]
    assert grants and all("service_role" in line and "anon" not in line and "authenticated" not in line for line in grants)
    tables = sql.split("create table")[1:3]
    assert all("user_id" not in table for table in tables)
    undo = (BACKEND.parent / "supabase" / "undo" / "20261101_bubbles_playbook_undo.sql").read_text(encoding="utf8")
    assert "drop table if exists public.bubbles_playbook" in undo


def test_the_consent_purpose_exists_and_is_off_by_default(db):
    assert "improve_bubbles" in consent.PURPOSES
    assert not consent.is_granted(db, U, pb.PURPOSE)


def test_a_greeting_must_be_nearly_the_whole_message():
    assert pb.intent_of("hi bubbles") == "app.greeting"
    assert pb.intent_of("hello, my head hurts and I feel dizzy") is None


# ---- capture from a thumbs ----
def _chat(db, user_text, reply_text):
    db.table("chat_messages").insert({"id": "m1", "conversation_id": "c1", "user_id": U, "role": "user", "content": user_text, "created_at": "2026-10-24T10:00:00+00:00"}).execute()
    db.table("chat_messages").insert({"id": "m2", "conversation_id": "c1", "user_id": U, "role": "bubbles", "content": reply_text, "created_at": "2026-10-24T10:00:05+00:00"}).execute()


def test_a_thumbs_on_a_plain_app_question_is_captured_with_a_yes(db):
    grant_consent(db, U, pb.PURPOSE)
    _chat(db, "what can you do?", "I can help you log, notice patterns and talk things through.")
    assert pb.capture_from_feedback(db, U, "m2", "up") is True
    row = db.tables[pb.CANDIDATES][0]
    assert row["intent"] == "app.what_can_you_do" and row["outcome"] == "helpful" and "what can you do" not in repr(row).lower()


def test_a_thumbs_on_a_health_chat_is_never_captured(db):
    grant_consent(db, U, pb.PURPOSE)
    _chat(db, "my head hurts since last night and I feel dizzy", "Sorry to hear that. Rest and drink some water.")
    assert pb.capture_from_feedback(db, U, "m2", "up") is False
    assert not db.tables.get(pb.CANDIDATES)


def test_no_capture_without_the_yes_even_for_a_plain_question(db):
    _chat(db, "what can you do?", "I can help you log.")
    assert pb.capture_from_feedback(db, U, "m2", "up") is False
