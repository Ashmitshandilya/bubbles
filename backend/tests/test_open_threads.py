"""Open threads (plan C6): a concern worth following up, asked about once, never for safety topics."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import doc_store  # noqa: E402
import open_threads as ot  # noqa: E402
from fake_db import FakeDB, grant_consent  # noqa: E402
from health_semantics import analyze  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000dd"
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def allowed():
    db = FakeDB({})
    grant_consent(db, USER, "health_memory_from_chat")
    return db


def fact(**more):
    base = dict(concept="headache", experiencer="self", assertion="present", temporal="current", severity=6, tier=None)
    return SimpleNamespace(**{**base, **more})


def docs(db):
    return {d["key"]: d["payload"] for d in doc_store.list_docs(db, USER, ot.KIND)}


def test_a_strong_or_recurring_symptom_opens_a_thread_and_a_mild_one_does_not():
    assert ot.worth_opening(fact(severity=4))
    assert ot.worth_opening(fact(severity=2, temporal="recurring"))
    assert not ot.worth_opening(fact(severity=3))
    assert not ot.worth_opening(fact(severity=None))


def test_only_the_persons_own_active_non_safety_symptoms_count():
    assert not ot.worth_opening(fact(experiencer="other"))
    assert not ot.worth_opening(fact(assertion="negated"))
    assert not ot.worth_opening(fact(temporal="past"))
    assert not ot.worth_opening(fact(tier="red"))
    assert not ot.worth_opening(fact(concept="suicidal_ideation"))


def test_observe_opens_keeps_the_first_date_and_closes_on_better():
    db = allowed()
    assert ot.observe(db, USER, [fact()], "NO_REDFLAG", NOW) == ["headache"]
    first = docs(db)["headache"]["opened_at"]
    assert ot.observe(db, USER, [fact()], "NO_REDFLAG", NOW + timedelta(days=1)) == []      # already open: the date does not move
    assert docs(db)["headache"]["opened_at"] == first
    assert ot.observe(db, USER, [fact(assertion="negated")], "NO_REDFLAG", NOW + timedelta(days=2)) == ["headache"]
    assert docs(db)["headache"]["closed_at"]
    assert ot.load_due(db, USER, NOW + timedelta(days=2)) == []


def test_nothing_is_opened_while_the_turn_is_about_safety():
    db = allowed()
    for state in ("EMERGENCY", "URGENT", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION"):
        assert ot.observe(db, USER, [fact()], state, NOW) == []
    assert docs(db) == {}


def test_a_thread_that_turned_urgent_is_closed_and_never_asked_about_lightly():
    db = allowed()
    ot.observe(db, USER, [fact()], "NO_REDFLAG", NOW)
    assert len(ot.load_due(db, USER, NOW)) == 1
    assert ot.observe(db, USER, [fact(severity=9)], "URGENT", NOW + timedelta(hours=3)) == ["headache"]
    assert docs(db)["headache"]["closed_because"] == "safety"
    assert ot.load_due(db, USER, NOW + timedelta(days=2)) == []


def test_a_thread_ages_out_after_seven_days_and_is_asked_once_a_day():
    db = allowed()
    ot.observe(db, USER, [fact()], "NO_REDFLAG", NOW)
    assert len(ot.load_due(db, USER, NOW + timedelta(days=6))) == 1
    assert ot.load_due(db, USER, NOW + timedelta(days=8)) == []
    ot.mark_shown(db, USER, NOW + timedelta(days=1))
    assert ot.load_due(db, USER, NOW + timedelta(days=1, hours=5)) == []
    assert len(ot.load_due(db, USER, NOW + timedelta(days=2, hours=1))) == 1


def test_the_block_says_how_long_ago_never_what_they_wrote_and_caps_at_three():
    db = allowed()
    for name in ("headache", "back_pain", "fatigue", "nausea"):
        ot.observe(db, USER, [fact(concept=name)], "NO_REDFLAG", NOW)
    block = ot.prompt_block(db, USER, NOW + timedelta(days=2))
    assert block.startswith("OPEN THREADS") and block.count("\n- ") == 3 and "2 days ago" in block
    assert ot.prompt_block(allowed(), USER, NOW) == ""


def test_real_message_facts_work_end_to_end():
    db = allowed()
    facts = analyze("I have had a headache for 3 days, about 6 out of 10")
    ot.observe(db, USER, facts, "NO_REDFLAG", NOW)
    assert any("headache" in k for k in docs(db))
    assert "6 out of 10" not in repr(docs(db)), "the message is never stored"


def test_it_never_raises_on_a_broken_store():
    class Broken:
        def table(self, *_a, **_k):
            raise RuntimeError("down")
    assert ot.observe(Broken(), USER, [fact()], "NO_REDFLAG", NOW) == []
    assert ot.load_due(Broken(), USER, NOW) == [] and ot.prompt_block(Broken(), USER, NOW) == ""
    ot.mark_shown(Broken(), USER, NOW)


def test_without_the_yes_to_chat_details_nothing_is_opened_but_a_thread_can_still_close():
    db = FakeDB({})
    assert ot.observe(db, USER, [fact()], "NO_REDFLAG", NOW) == [] and docs(db) == {}
    yes = allowed()
    ot.observe(yes, USER, [fact()], "NO_REDFLAG", NOW)
    import consent
    consent.set_purpose(yes, USER, "health_memory_from_chat", False, source="system", hash_seen=consent.text_hash("health_memory_from_chat"))
    consent.forget(USER)
    assert ot.observe(yes, USER, [fact(assertion="negated")], "NO_REDFLAG", NOW + timedelta(days=1)) == ["headache"]
