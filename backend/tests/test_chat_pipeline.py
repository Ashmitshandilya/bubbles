"""Unit tests for chat_pipeline: routing, context assembly, rule-built events, AI-event reconciliation, persistence."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import chat_pipeline as cp  # noqa: E402
from fake_db import FakeAPIError, FakeDB  # noqa: E402
from health_semantics import analyze  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
UID = "u-1"
DAY1 = (
    "Cycle day 3, my period is active with moderate flow. Slept 6h 42m. Breakfast: oats and banana. I had rice and dal for lunch. "
    "Drank about 1.8 L of water. Walked 6,420 steps. Cramps 4/10, pelvic discomfort 2/10, bloating 2/10. Mood was stable. "
    "No headache, nausea, vomiting, chest pain, shortness of breath or dizziness. Took my iron supplement."
)


def turn(text, history=()):
    return cp.analyze_turn(text, list(history), now=NOW)


# ------------------------------------------------------------------ routing
def test_routes():
    assert turn("I have chest pain").route == "emergency"
    assert turn("I think I might have some chest discomfort").route == "clarification"
    assert turn(DAY1).route == "daily_log"
    assert turn("Can chest pain happen during anxiety?").route == "ai"
    assert turn("I had chest pain yesterday but I'm fine now.").route == "ai"
    assert turn("hello").route == "ai"


def test_emergency_beats_correction_and_daily_log():
    history = [{"id": "c1", "role": "bubbles", "content": "x", "metadata": {"safety": {"concepts": ["headache"]}}}]
    t = turn("I said no headache but I have severe chest pain right now. " + DAY1, history)
    assert t.route == "emergency"


def test_correction_route_needs_a_prior_wrong_claim():
    history = [
        {"id": "u1", "role": "user", "content": "No headache, nausea, vomiting, chest pain, shortness of breath or dizziness."},
        {"id": "c1", "role": "bubbles", "content": "Bubbles detected chest pain or pressure.", "metadata": {"safety": {"level": "RED", "concepts": ["chest_pain"]}}},
    ]
    t = turn("I said no chest pain?", history)
    assert t.route == "correction" and t.correction.concepts == ("chest_pain",) and t.correction.retract_message_id == "c1"
    assert turn("I said no chest pain?", []).route != "correction"


# ------------------------------------------------------------------ rate limiter
def test_rate_limiter_window():
    clock = SimpleNamespace(t=0.0)
    rl = cp.RateLimiter(limit=2, window=10, clock=lambda: clock.t)
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    assert rl.allow("b")  # per user
    clock.t = 11
    assert rl.allow("a")


def test_rate_limiter_drops_stale_keys_so_memory_stays_bounded():
    clock = SimpleNamespace(t=0.0)
    rl = cp.RateLimiter(limit=2, window=10, clock=lambda: clock.t)
    for i in range(1200):
        rl.allow(f"ip{i}")
    clock.t = 100
    for _ in range(cp.RateLimiter.SWEEP_EVERY):  # a sweep runs within this many calls, whatever the table size
        rl.allow("fresh")
    assert "fresh" in rl._hits and len(rl._hits) <= 2


def test_rate_limiter_has_a_hard_ceiling_on_keys(monkeypatch):
    monkeypatch.setattr(cp.RateLimiter, "MAX_KEYS", 50)
    rl = cp.RateLimiter(limit=5, window=60, clock=lambda: 0.0)
    allowed = [rl.allow(f"k{i}") for i in range(80)]
    assert allowed.count(True) == 50 and len(rl._hits) == 50   # made-up keys cannot grow the table past the ceiling
    assert rl.allow("k0")  # a key already in the table keeps working


def test_rate_limiter_over_and_record_count_events_without_checking():
    clock = SimpleNamespace(t=0.0)
    rl = cp.RateLimiter(limit=3, window=10, clock=lambda: clock.t)
    assert not rl.over("ip")
    for _ in range(3):
        rl.record("ip")
    assert rl.over("ip")
    assert not rl.over("someone-else")
    clock.t = 11
    assert not rl.over("ip")


# ------------------------------------------------------------------ context
def test_conversation_block_hides_retracted_warning_and_is_bounded():
    history = [
        {"role": "user", "content": "hello " * 200},
        {"role": "bubbles", "content": "### Please get urgent medical help", "metadata": {"safety": {"retracted": True}}},
    ]
    block = cp.conversation_block(history)
    assert "withdrawn" in block and "urgent medical help" not in block
    assert max(len(line) for line in block.splitlines()) <= 380
    assert len(cp.conversation_block([{"role": "user", "content": "x" * 300}] * 30)) <= 2400


def test_state_block_lists_denied_present_and_past_separately():
    cur = analyze("No chest pain. I have a headache 5/10. I had a fever last week.")
    block = cp.state_block(cur, [])
    assert "Denied by the user" in block and "chest pain" in block.split("Denied by the user")[1].splitlines()[0]
    assert "headache (5/10)" in block
    assert "Past or resolved" in block and "fever" in block
    assert cp.state_block(analyze("hello"), []) == ""


def test_state_block_later_statement_wins():
    hist = analyze("I have a headache.")
    cur = analyze("No headache now.")
    assert "Denied by the user (never say they have these): headache" in cp.state_block(cur, hist)


def test_evidence_query_never_searches_denied_or_other_peoples_symptoms():
    assert cp.evidence_query(analyze("No chest pain, my sister has a headache."), "No chest pain, my sister has a headache. " + "x " * 200) == ""
    assert cp.evidence_query(analyze("Can chest pain happen during anxiety?"), "Can chest pain happen during anxiety?") == "chest pain anxiety"
    assert cp.evidence_query(analyze("How much water should I drink?"), "How much water should I drink?")== "much water drink?"
    assert cp.evidence_query([], "kya mujhe bukhar hai?") == "bukhar"


# ------------------------------------------------------------------ rule-built events
def test_rule_events_for_day1():
    t = turn(DAY1)
    events = cp.build_rule_events(t, "m1", now=NOW)
    types = [e["event_type"] for e in events]
    assert {"sleep", "hydration", "activity", "food", "mood", "supplement", "wellness_checkin", "menstrual_symptom", "symptom"} <= set(types)
    screen = [e for e in events if e["event_type"] == "wellness_checkin"]
    assert len(screen) == 1 and {"chest pain", "headache", "dizziness"} <= set(screen[0]["extracted_data"]["pertinent_negatives"])
    assert "symptom" not in screen[0]["extracted_data"] and "name" not in screen[0]["extracted_data"]
    positives = {e["extracted_data"].get("symptom") for e in events if e["event_type"] in {"symptom", "menstrual_symptom"}}
    assert "chest pain" not in positives and "headache" not in positives and "cramps" in positives
    period = [e for e in events if e["extracted_data"].get("name") == "period"][0]["extracted_data"]
    assert period["is_start"] is True and period["cycle_day"] == 3 and period["start_date"] == "2026-10-05" and period["flow"] == "moderate"
    for e in events:
        prov = e["extracted_data"]["_prov"]
        assert prov["extractor"] == "rules" and prov["message_id"] == "m1" and prov["subject"] == "self" and prov["assertion"] == "present"
        sev = e["extracted_data"].get("severity")
        assert sev is None or 1 <= sev <= 10
    sleep = [e for e in events if e["event_type"] == "sleep"][0]["extracted_data"]
    assert sleep["duration_minutes"] == 402 and sleep["hours"] == 6.7 and sleep["unit"] == "hours"
    food = {e["extracted_data"]["meal"]: e["extracted_data"] for e in events if e["event_type"] == "food"}
    assert food["lunch"]["calories"] == 330 and food["breakfast"]["calories"] == 255  # estimates only for foods in the (now larger) reference table


def test_rule_event_keys_are_deterministic_and_unique():
    a = [e["extracted_data"]["_prov"]["key"] for e in cp.build_rule_events(turn(DAY1), "m1", now=NOW)]
    b = [e["extracted_data"]["_prov"]["key"] for e in cp.build_rule_events(turn(DAY1), "m1", now=NOW)]
    assert a == b and len(a) == len(set(a))
    assert a != [e["extracted_data"]["_prov"]["key"] for e in cp.build_rule_events(turn(DAY1), "m2", now=NOW)]


def test_no_invented_values():
    events = cp.build_rule_events(turn("I felt a bit tired today."), "m1", now=NOW)
    assert [e["event_type"] for e in events] == ["symptom"]
    assert not any(e["event_type"] in {"sleep", "hydration", "weight", "vital_sign"} for e in events)
    assert cp.build_rule_events(turn("Can chest pain happen during anxiety?"), "m1", now=NOW) == []
    assert cp.build_rule_events(turn("hello"), "m1", now=NOW) == []


# ------------------------------------------------------------------ AI event reconciliation
def _ev(event_type, name, conf=0.9, **extra):
    from bubbles_ai import ExtractedHealthData, HealthEvent
    return HealthEvent(event_type=event_type, extracted_data=ExtractedHealthData(symptom=name, name=name, **extra), confidence=conf)


def _kept(text, events, rules=()):
    return cp.reconcile_ai_events(events, turn(text), list(rules), "m1", now=NOW)


def test_reconcile_drops_denied_hypothetical_question_quoted_and_other_person():
    cases = [
        ("No chest pain today.", "chest pain"),
        ("What if I get a headache?", "headache"),
        ("Can dizziness happen in the first days of a period?", "dizziness"),
        ("My doctor told me to watch for chest pain.", "chest pain"),
        ("My sister has chest pain.", "chest pain"),
        ("I think I might have a fever.", "fever"),
        ("I had a seizure when I was ten.", "seizure"),  # past: kept as history elsewhere, not as a live symptom event
    ]
    for text, name in cases:
        got = _kept(text, [_ev("symptom", name)])
        if "seizure" in text:
            assert all(e["extracted_data"]["_prov"]["temporal"] == "past" for e in got), text
        else:
            assert got == [], text


def test_reconcile_keeps_present_symptoms_and_attaches_provenance():
    got = _kept("I have a headache and my knee swelling is worse today.", [_ev("symptom", "headache"), _ev("symptom", "knee swelling")])
    names = {e["extracted_data"]["symptom"] for e in got}
    assert names == {"headache", "knee swelling"}
    prov = got[0]["extracted_data"]["_prov"]
    assert prov["extractor"] == "llm" and prov["message_id"] == "m1" and prov["assertion"] == "present"


def test_reconcile_unknown_term_negated_is_dropped():
    assert _kept("No knee swelling today.", [_ev("symptom", "knee swelling")]) == []


def test_reconcile_drops_ungrounded_events_and_bad_evidence_spans():
    assert _kept("I slept well.", [_ev("symptom", "migraine")]) == []
    assert _kept("I have a headache.", [_ev("symptom", "headache", evidence_span="severe chest pain")]) == []
    assert len(_kept("I have a headache.", [_ev("symptom", "headache", evidence_span="have a headache")])) == 1


def test_reconcile_does_not_duplicate_rule_events():
    t = turn("I slept 7 hours and I have cramps 4/10.")
    rules = cp.build_rule_events(t, "m1", now=NOW)
    got = cp.reconcile_ai_events([_ev("symptom", "cramps"), _ev("sleep", "sleep")], t, rules, "m1", now=NOW)
    assert got == []


def test_reconcile_strips_grounding_fields_and_caps_confidence():
    got = _kept("I have a headache.", [_ev("symptom", "headache", conf=1.0, assertion="present", subject="self")])
    data = got[0]["extracted_data"]
    assert "assertion" not in data and "subject" not in data and "evidence_span" not in data
    assert got[0]["confidence"] <= 0.9


# ------------------------------------------------------------------ persistence
def test_persist_events_batches_and_returns_ui_events():
    db = FakeDB()
    events = cp.build_rule_events(turn(DAY1), "m1", now=NOW)
    saved = cp.persist_events(db, UID, "m1", events)
    assert len(saved) == len(events) == len(db.rows("extracted_health_events"))
    assert all(s["id"] and s["status"] == "pending" for s in saved)
    assert all(not any(k.startswith("_") for k in s["extracted_data"]) for s in saved)
    row = db.rows("extracted_health_events")[0]
    assert row["extraction_status"] == "pending" and row["user_confirmed"] is False and row["message_id"] == "m1"


def test_persist_events_is_idempotent_per_message():
    db = FakeDB()
    events = cp.build_rule_events(turn(DAY1), "m1", now=NOW)
    cp.persist_events(db, UID, "m1", events)
    again = cp.persist_events(db, UID, "m1", events)
    assert again == [] and len(db.rows("extracted_health_events")) == len(events)


def test_persist_events_falls_back_to_rows_and_marks_failures_with_none_ids():
    class Flaky(FakeDB):
        def __init__(self):
            super().__init__()
            self.inserts = 0

        def table(self, name):
            q = super().table(name)
            if name == "extracted_health_events":
                real = q.insert

                def insert(payload):
                    self.inserts += 1
                    if isinstance(payload, list):
                        raise FakeAPIError("batch boom")
                    if payload["event_type"] == "hydration":
                        raise FakeAPIError("row boom")
                    return real(payload)
                q.insert = insert
            return q

    db = Flaky()
    events = cp.build_rule_events(turn("I slept 7 hours and drank 1.5 L of water."), "m9", now=NOW)
    saved = cp.persist_events(db, UID, "m9", events)
    by = {s["event_type"]: s["id"] for s in saved}
    assert by["sleep"] is not None and by["hydration"] is None  # ids stay aligned with their events


def test_persist_events_never_raises_when_the_table_is_denied():
    db = FakeDB()
    from fake_db import permission_denied
    db.failures["extracted_health_events"] = permission_denied("extracted_health_events")
    saved = cp.persist_events(db, UID, "m1", cp.build_rule_events(turn("I slept 7 hours."), "m1", now=NOW))
    assert saved and all(s["id"] is None for s in saved)


# ------------------------------------------------------------------ history helpers
def test_load_history_is_owner_scoped_oldest_first_and_never_raises():
    db = FakeDB()
    for i, (uid, role) in enumerate([("u-1", "user"), ("u-2", "user"), ("u-1", "bubbles")]):
        db.table("chat_messages").insert({"user_id": uid, "conversation_id": "c1", "role": role, "content": f"m{i}", "created_at": f"2026-10-07T10:0{i}:00+00:00"}).execute()
    assert [r["content"] for r in cp.load_history(db, "u-1", "c1")] == ["m0", "m2"]
    db.failures["chat_messages"] = FakeAPIError("down")
    assert cp.load_history(db, "u-1", "c1") == []


def test_stored_metadata_and_safety_payload_shapes():
    t = turn("I have chest pain")
    sp = cp.safety_payload(t.safety)
    assert sp["state"] == "EMERGENCY" and sp["level"] == "RED" and sp["retracted"] is False and "chest pain or pressure" in sp["reasons"]
    meta = cp.stored_metadata(kind="emergency", user_message_id="m1", safety=sp, events=[], evidence_ids=[], conflicts=[], trace=cp.semantic_trace(t))
    assert meta["user_message_id"] == "m1" and meta["kind"] == "emergency"
    assert all("source_text" not in row for row in meta["semantic_trace"])  # diagnostics never include the user's words


# ------------------------------------------------------------------ one-line event summaries for the UI
def test_event_summaries_are_human_readable_and_never_dump_keys():
    saved = cp.persist_events(FakeDB(), UID, "m1", cp.build_rule_events(turn(DAY1), "m1", now=NOW))
    lines = {s["summary"] for s in saved}
    assert "Slept 6h 42m" in lines and "Water: 1.8 L" in lines and "6,420 steps" in lines
    assert "Cramps 4/10" in lines and "Period: cycle day 3, moderate flow" in lines and "Took iron" in lines
    assert any(l.startswith("Not present:") and "chest pain" in l for l in lines)
    assert not any("duration_minutes" in l or "amount_ml" in l or "_" in l for l in lines)
