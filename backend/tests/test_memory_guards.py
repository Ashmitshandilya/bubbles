"""Memory, context and promotion guards: rejected/denied/hedged rows never become context or memory."""
from datetime import datetime, timedelta, timezone

import pytest

import context_engine
import memory_promotion
import memory_retrieval
from context_engine import build_user_context, format_user_context
from memory_manager import extract_explicit_personal_facts, memory_diagnostics
from memory_retrieval import format_memory_context, get_relevant_memories

NOW = datetime.now(timezone.utc)


def row(event_type, data, *, id, days_ago=0, status=None, confirmed=False, assertion=None, subject=None, message_id=None):
    d = dict(data)
    prov = {k: v for k, v in (("assertion", assertion), ("subject", subject)) if v}
    if prov:
        d["_prov"] = prov
    r = {"id": id, "event_type": event_type, "extracted_data": d, "confidence": 0.9,
         "created_at": (NOW - timedelta(days=days_ago)).isoformat(), "user_confirmed": confirmed,
         "message_id": message_id or f"msg-{id}"}
    if status:
        r["extraction_status"] = status
    return r


def screen(concepts, *, id, **kw):
    return row("wellness_checkin", {"pertinent_negatives": concepts, "screen": "symptom_screen"}, id=id, **kw)


class _Res:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.payload = db, table, [], None

    def select(self, cols="*", **_):
        self.db.selects.append((self.table, cols))
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.db.fail:
            raise RuntimeError("db unavailable")
        if self.payload is not None:
            self.db.inserts.append((self.table, self.payload))
            return _Res([{"id": f"new-{len(self.db.inserts)}", **self.payload}])
        return _Res([r for r in self.db.tables.get(self.table, []) if all(r.get(k, v) == v for k, v in self.filters)])


class FakeDB:
    def __init__(self, tables=None, fail=False):
        self.tables, self.fail = tables or {}, fail
        self.selects, self.inserts = [], []

    def table(self, name):
        return _Query(self, name)


def l1_rows():
    return [
        row("symptom", {"symptom": "headache", "severity": "mild"}, id="pending"),
        row("symptom", {"symptom": "headache"}, id="confirmed", confirmed=True, status="confirmed"),
        row("symptom", {"symptom": "headache"}, id="rejected", status="rejected"),
        row("symptom", {"symptom": "headache", "present": False}, id="negated"),
        row("symptom", {"symptom": "headache"}, id="hypothetical", assertion="hypothetical"),
        screen(["chest pain", "nausea"], id="screen"),
    ]


# ---------------------------------------------------------------- memory_retrieval

def test_retrieval_selects_status_and_keeps_only_live_rows_and_denials(monkeypatch):
    db = FakeDB({"extracted_health_events": l1_rows()})
    monkeypatch.setattr(memory_retrieval, "supabase", db)
    memories = get_relevant_memories("u", "headache chest pain")
    assert [e["id"] for e in memories["L1"]] == ["pending", "confirmed", "screen"]
    columns = next(cols for table, cols in db.selects if table == "extracted_health_events")
    assert "extraction_status" in columns and "user_confirmed" in columns


def test_retrieval_works_for_rows_without_status_keys(monkeypatch):
    legacy = [{"id": "x", "event_type": "symptom", "extracted_data": {"symptom": "headache"}, "created_at": NOW.isoformat()}]
    monkeypatch.setattr(memory_retrieval, "supabase", FakeDB({"extracted_health_events": legacy}))
    assert [e["id"] for e in get_relevant_memories("u", "headache")["L1"]] == ["x"]
    assert "(unconfirmed)" in format_memory_context({"L1": legacy, "L2": [], "L3": []})


def test_memory_context_labels_unconfirmed_and_renders_denials():
    rows = [r for r in l1_rows() if r["id"] in {"pending", "confirmed", "screen"}]
    text = format_memory_context({"L1": rows, "L2": [], "L3": []})
    lines = text.splitlines()
    assert any("Denied by user: chest pain, nausea" in line for line in lines)
    pending = next(line for line in lines if "severity=mild" in line)
    confirmed = next(line for line in lines if "symptom=headache" in line and "severity" not in line)
    assert pending.endswith("(unconfirmed)")
    assert "(unconfirmed)" not in confirmed
    assert "_prov" not in text and "assertion" not in text


def test_memory_context_never_renders_rejected_or_non_positive_rows():
    dead = [r for r in l1_rows() if r["id"] in {"rejected", "negated", "hypothetical"}]
    assert format_memory_context({"L1": dead, "L2": [], "L3": []}) == "No relevant personal health memory was found."
    rejected_screen = screen(["fever"], id="s2", status="rejected")
    assert "fever" not in format_memory_context({"L1": [rejected_screen], "L2": [], "L3": []})


def test_retrieval_failure_logs_query_length_not_the_query(monkeypatch, capsys):
    monkeypatch.setattr(memory_retrieval, "supabase", FakeDB(fail=True))
    secret = "my chest hurts when I climb stairs"
    assert get_relevant_memories("u", secret) == {"L1": [], "L2": [], "L3": []}
    err = capsys.readouterr().err
    assert secret not in err and "chest hurts" not in err
    assert f'"query_length": {len(secret)}' in err


# ---------------------------------------------------------------- context_engine

def test_user_context_has_live_events_denials_and_labels(monkeypatch):
    db = FakeDB({"extracted_health_events": l1_rows()})
    monkeypatch.setattr(memory_retrieval, "supabase", db)
    monkeypatch.setattr(context_engine, "_get_supabase", lambda: db)
    context = build_user_context("u", "headache")
    assert [e["id"] for e in context["recent_events"]] == ["pending", "confirmed"]
    assert context["recent_events"][1]["extraction_status"] == "confirmed"
    assert context["pertinent_negatives"][0]["concepts"] == ["chest pain", "nausea"]
    text = format_user_context(context)
    assert "Denied by user: chest pain, nausea" in text
    assert "_prov" not in text
    recent = text.split("RECENT HEALTH EVENTS:")[1].split("EXPLICIT DENIALS")[0].splitlines()
    assert next(l for l in recent if "severity=mild" in l).endswith("(unconfirmed)")
    assert "(unconfirmed)" not in next(l for l in recent if "confidence" in l and "severity" not in l)


def test_format_user_context_handles_legacy_compact_events():
    text = format_user_context({"recent_events": [{"type": "sleep", "data": {"duration": "5h", "_prov": {"key": "k"}}, "confidence": 0.9, "created_at": "x"}]})
    assert "duration=5h" in text and "(unconfirmed)" in text and "_prov" not in text


# ---------------------------------------------------------------- memory_promotion

def pattern_rows():
    def ev(id, message_id, **kw):
        return {**row("symptom", {"symptom": "Headache"}, id=id, message_id=message_id, confirmed=kw.pop("confirmed", True), **kw)}
    return [
        ev("e1", "m1"),
        ev("e2", "m1"),  # second row from the same message (retry / duplicate)
        ev("e3", "m2"),
        ev("e4", "m3"),
        ev("e5", "m4", confirmed=False),
        ev("e6", "m5", status="rejected"),
        row("symptom", {"symptom": "headache", "present": False}, id="e7", message_id="m6", confirmed=True),
    ]


def test_matching_l1_events_are_live_confirmed_and_one_per_message(monkeypatch):
    db = FakeDB({"extracted_health_events": pattern_rows()})
    monkeypatch.setattr(memory_promotion, "supabase", db)
    found = memory_promotion.get_matching_l1_events("u", "symptom", "symptom:headache")
    assert [e["id"] for e in found] == ["e1", "e3", "e4"]
    columns = next(cols for table, cols in db.selects if table == "extracted_health_events")
    assert all(name in columns for name in ("extraction_status", "user_confirmed", "message_id"))


def test_l3_promotion_requires_confirmation_and_distinct_messages(monkeypatch):
    db = FakeDB({"extracted_health_events": pattern_rows()})
    monkeypatch.setattr(memory_promotion, "supabase", db)
    base = dict(user_id="u", event_id="e1", event_type="symptom", extracted_data={"symptom": "Headache"}, confidence=0.9)
    assert memory_promotion.promote_health_event(**base)["reason"] == "confirmation_required"
    result = memory_promotion.promote_health_event(**base, user_confirmed=True)
    assert result["promoted"] is True and result["level"] == "L3"
    structured = db.inserts[0][1]["structured_data"]
    assert structured["occurrence_count"] == 3
    assert structured["source_event_ids"] == ["e1", "e3", "e4"]


def test_duplicate_rows_from_one_message_do_not_reach_the_threshold(monkeypatch):
    rows = [row("symptom", {"symptom": "Headache"}, id=f"d{i}", message_id="same", confirmed=True) for i in range(3)]
    db = FakeDB({"extracted_health_events": rows})
    monkeypatch.setattr(memory_promotion, "supabase", db)
    result = memory_promotion.promote_health_event("u", "d0", "symptom", {"symptom": "Headache"}, 0.9, user_confirmed=True)
    assert result["reason"] == "not_enough_occurrences" and result["occurrences"] == 1
    assert db.inserts == []


def test_wellness_checkin_is_not_a_promotable_pattern(monkeypatch):
    monkeypatch.setattr(memory_promotion, "supabase", FakeDB())
    assert "wellness_checkin" not in memory_promotion.L3_TYPES
    result = memory_promotion.promote_health_event("u", "s1", "wellness_checkin", {"pertinent_negatives": ["headache"]}, 0.95, user_confirmed=True)
    assert result["reason"] == "event_type_not_promotable"


@pytest.mark.parametrize("event_type,data,status", [
    ("medical_condition", {"name": "diabetes", "present": False}, None),
    ("allergy", {"name": "penicillin", "_prov": {"assertion": "negated"}}, None),
    ("medical_condition", {"name": "diabetes", "_prov": {"subject": "other"}}, None),
    ("symptom", {"symptom": "headache", "_prov": {"assertion": "hypothetical"}}, None),
    ("medical_condition", {"name": "diabetes"}, "rejected"),
])
def test_non_present_or_non_self_rows_are_refused(monkeypatch, event_type, data, status):
    db = FakeDB()
    monkeypatch.setattr(memory_promotion, "supabase", db)
    result = memory_promotion.promote_health_event("u", "x1", event_type, data, 0.99, user_confirmed=True, extraction_status=status)
    assert result == {"promoted": False, "level": None, "reason": "not_a_live_present_observation"}
    assert db.selects == [] and db.inserts == []


def test_family_history_has_its_own_template_and_canonical_keys_win(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(memory_promotion, "supabase", db)
    data = {"name": "diabetes", "relative": "mother", "confirmed": False, "source_event_ids": ["fake"],
            "_prov": {"subject": "other", "assertion": "present", "key": "k"}}
    result = memory_promotion.promote_health_event("u", "fh1", "family_medical_history", data, 0.9, user_confirmed=True)
    assert result["promoted"] is True and result["level"] == "L2"
    payload = db.inserts[0][1]
    assert payload["content"] == "Family history: mother: diabetes."
    assert "User has reported" not in payload["content"]
    assert payload["structured_data"]["confirmed"] is True
    assert payload["structured_data"]["source_event_ids"] == ["fh1"]
    assert "_prov" not in payload["structured_data"]


def test_family_history_without_relative_and_negated_family_history(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(memory_promotion, "supabase", db)
    memory_promotion.promote_health_event("u", "fh2", "family_medical_history", {"name": "asthma"}, 0.9, user_confirmed=True)
    assert db.inserts[0][1]["content"] == "Family history: asthma."
    refused = memory_promotion.promote_health_event("u", "fh3", "family_medical_history", {"name": "asthma", "present": False}, 0.9, user_confirmed=True)
    assert refused["reason"] == "not_a_live_present_observation"


def test_own_condition_keeps_the_first_person_template(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(memory_promotion, "supabase", db)
    memory_promotion.promote_health_event("u", "c1", "medical_condition", {"name": "diabetes"}, 0.9, user_confirmed=True)
    assert db.inserts[0][1]["content"] == "User has reported diabetes."


# ---------------------------------------------------------------- memory_manager

@pytest.mark.parametrize("text,expected", [
    ("Don't call me Sir", []),
    ("Do not call me Sir", []),
    ("Please don't call me Ash, call me Asha", []),
    ("My name is Priya and I have a headache. No chest pain", [("name", "Priya")]),
    ("What if my name is Bob?", []),
    ("Suppose my name is Bob", []),
    ("If I live in a hot climate should I drink more water?", []),
    ('He said "my name is Bob"', []),
    ("I never said my name is Bob", []),
    ("I live in Delhi, I work as a nurse", [("location", "Delhi"), ("occupation", "nurse")]),
    ("I live in Chennai and I work as a student.", [("location", "Chennai"), ("occupation", "student")]),
    ("My name is Ashmit.", [("name", "Ashmit")]),
    ("I don't smoke. My name is Priya", [("name", "Priya")]),
    ("Hi, my name is Priya, can you help me sleep better?", [("name", "Priya")]),
    ("Call me back later", []),
    ("call me Asha", [("name", "Asha")]),
    ("I’m studying computer science and biology", [("study", "computer science")]),
])
def test_explicit_fact_extraction_is_bounded_and_not_fooled_by_hedges(text, expected):
    assert [(f["key"], f["value"]) for f in extract_explicit_personal_facts(text)] == expected


def test_explicit_fact_capture_is_at_most_four_words():
    facts = extract_explicit_personal_facts("I live in the old town of Jaipur right now")
    assert len(facts[0]["value"].split()) <= 4


def test_memory_diagnostics_count_live_events_only(monkeypatch):
    rows = [
        row("symptom", {"symptom": "headache"}, id="a", confirmed=True),
        row("symptom", {"symptom": "cough"}, id="b"),
        row("symptom", {"symptom": "chest pain"}, id="c", status="rejected"),
        row("symptom", {"symptom": "chest pain", "present": False}, id="d"),
        screen(["fever"], id="e"),
    ]
    db = FakeDB({"extracted_health_events": rows, "memory_items": [{"memory_type": "L2", "structured_data": {"key": "name", "value": "Priya"}}]})
    monkeypatch.setattr("supabase_client.supabase", db)
    out = memory_diagnostics("u")
    assert (out["L1"], out["L1_confirmed"], out["L1_pending"]) == (2, 1, 1)
    assert [r["id"] for r in out["recent"]] == ["a", "b"]
    assert out["L2"] == 1 and out["name"] == "Priya"
