"""A long message about a whole day: what is understood, what is saved on its own, and what is asked about once.

The policy is pure and tested directly; the flow runs through the real chat route with the in-memory database.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_pipeline as cp  # noqa: E402
import event_policy as ep  # noqa: E402
import paragraph_extras as px  # noqa: E402
from test_chat_http_flow import H, USER, env, send  # noqa: E402,F401

PARAGRAPH = ("Yesterday I slept around 6 hours and woke up twice. Had 2 cups of coffee in the morning, skipped breakfast, lunch was dal chawal and a salad, "
             "dinner was paneer and 2 rotis. I had a headache in the afternoon, about a 5 out of 10. Mood was low because I had a fight with my boyfriend. "
             "I walked for 30 minutes in the evening and drank about 2 litres of water. My weight is 62 kg today. I twisted my ankle playing football and it's swollen, "
             "and I had a fever of 100.4 at night. Took a paracetamol. Also my period started 3 days ago and cramps are bad.")


# ---- extraction ----
@pytest.mark.parametrize("text,part,swollen", [
    ("I twisted my ankle playing football and it's swollen", "ankle", True),
    ("my knee is swollen after I fell", "knee", True),
    ("I hurt my back lifting boxes", "back", False),
    ("I cut my finger while cooking", "finger", False),
    ("I bumped my head on the shelf", "head", False),
])
def test_injuries_are_found(text, part, swollen):
    got = px.injuries(text)
    assert got and got[0]["part"] == part and got[0]["swollen"] is swollen


@pytest.mark.parametrize("text", ["I broke my phone", "my phone fell on the floor", "I cut the vegetables", "the hurt in my heart"])
def test_things_that_are_not_injuries_are_left_alone(text):
    assert px.injuries(text) == []


def test_a_fight_with_a_partner_is_a_tension_day_but_being_hurt_is_not():
    assert px.conflict_with_partner("had a big fight with my boyfriend yesterday")
    assert px.conflict_with_partner("my wife and I argued about money")
    assert not px.conflict_with_partner("my husband hit me during our fight")
    assert not px.conflict_with_partner("I had a fight with my boss")


def test_the_paragraph_is_read_into_the_right_events():
    turn = cp.analyze_turn(PARAGRAPH, [])
    assert turn.route == "daily_log"
    by_type: dict[str, list[dict]] = {}
    for e in cp.build_rule_events(turn, "m1"):
        by_type.setdefault(e["event_type"], []).append(e["extracted_data"])
    assert by_type["sleep"][0]["hours"] == 6.0 and by_type["sleep"][0]["awakenings"] == 2
    assert by_type["hydration"][0]["amount_ml"] == 2000
    assert by_type["exercise"][0]["name"] == "walking" and by_type["exercise"][0]["duration_minutes"] == 30
    assert by_type["weight"][0]["weight_kg"] == 62.0
    assert by_type["vital_sign"][0]["name"] == "temperature" and by_type["vital_sign"][0]["value"] == 38.0   # 100.4 F
    assert {f["meal"] for f in by_type["food"]} == {"lunch", "dinner", "breakfast"} and any(f.get("skipped") for f in by_type["food"])
    assert any(s.get("injury") and s["body_part"] == "ankle" for s in by_type["symptom"])
    assert not any(s.get("name") == "swelling" for s in by_type["symptom"])      # the swelling belongs to the injury, asked about once
    assert by_type["medication"][0]["name"] == "paracetamol"


# ---- the policy ----
def _event(etype, **data):
    return {"event_type": etype, "extracted_data": {"_prov": {"extractor": "rules"}, **data}, "confidence": 0.9}


@pytest.mark.parametrize("event,want", [
    (_event("sleep", hours=6), "auto"), (_event("hydration", amount_ml=2000), "auto"), (_event("exercise", name="walking"), "auto"),
    (_event("weight", weight_kg=62), "auto"), (_event("food", name="dal chawal"), "auto"), (_event("mood", name="low"), "auto"),
    (_event("lifestyle", name="coffee"), "auto"), (_event("vital_sign", name="temperature", value=36.8), "auto"), (_event("vital_sign", name="heart rate", value=72), "auto"),
    (_event("vital_sign", name="temperature", value=38.0), "ask"), (_event("vital_sign", name="systolic", value=150), "ask"), (_event("vital_sign", name="spo2", value=92), "ask"),
    (_event("symptom", name="headache"), "ask"), (_event("symptom", name="ankle injury", injury=True), "ask"), (_event("menstrual_symptom", name="period"), "ask"),
    (_event("medication", name="paracetamol"), "ask"), (_event("supplement", name="iron"), "ask"), (_event("medical_condition", name="asthma"), "ask"),
])
def test_what_is_saved_and_what_is_asked(event, want):
    assert ep.decide(event)[0] == want


def test_a_model_proposal_is_never_saved_unseen_and_a_shaky_reading_is_asked():
    proposed = {"event_type": "sleep", "extracted_data": {"_prov": {"extractor": "ai"}, "hours": 6}, "confidence": 0.99}
    assert ep.decide(proposed)[0] == "ask"
    shaky = _event("sleep", hours=6)
    shaky["confidence"] = 0.5
    assert ep.decide(shaky)[0] == "ask"


def test_labels_are_plain_words():
    assert ep.labels([_event("sleep"), _event("hydration"), _event("food"), _event("food")]) == ["sleep", "water", "your meals"]
    asked = ep.labels([_event("symptom", name="ankle injury", injury=True, body_part="ankle"), _event("vital_sign", name="temperature", value=38.0)], asking=True)
    assert asked == ["your ankle injury", "the fever"]


# ---- the whole flow ----
def _statuses(env):
    rows = env.db.rows("extracted_health_events", user_id=USER)
    return {(r["event_type"], r["extracted_data"].get("name")): r["extraction_status"] for r in rows}


def test_a_long_paragraph_saves_what_was_stated_and_asks_about_what_needs_care(env):
    res = send(env, PARAGRAPH)
    assert res.status_code == 200, res.text
    body = res.json()
    text = body["response"]
    assert env.ai_calls == []
    st = _statuses(env)
    for key in (("sleep", "sleep"), ("hydration", "water"), ("exercise", "walking"), ("weight", "weight"), ("mood", "low"), ("lifestyle", "coffee")):
        assert st[key] == "confirmed", (key, st)
    for key in (("symptom", "headache"), ("symptom", "ankle injury"), ("vital_sign", "temperature"), ("medication", "paracetamol"), ("symptom", "fever")):
        assert st[key] == "pending", (key, st)
    assert "I've saved" in text and "sleep" in text and "your OK" in text and "Save or Skip" in text
    assert "swollen" in text.lower() and "checked today" in text and "fever" in text.lower()
    shown = {e["event_type"]: e["status"] for e in body["health_events"]}
    assert shown["sleep"] == "confirmed" and shown["medication"] == "pending"


def test_the_same_day_is_not_saved_twice_it_is_asked(env):
    send(env, "I slept 6 hours last night")
    again = send(env, "I slept 7 hours last night", conv=None).json()
    sleeps = [e for e in env.db.rows("extracted_health_events", user_id=USER) if e["event_type"] == "sleep"]
    assert sorted(e["extraction_status"] for e in sleeps) == ["confirmed", "pending"]
    shown = [e for e in again["health_events"] if e["event_type"] == "sleep"]
    assert shown and shown[0]["status"] == "pending"      # the card asks: the person decides whether this replaces the first


def test_a_fight_with_a_partner_marks_a_tension_day_and_keeps_no_words(env):
    import doc_store
    send(env, "Slept 6 hours. Had a big fight with my boyfriend today and I'm exhausted.")
    docs = doc_store.list_docs(env.db, USER, "orbit_tension", 10)
    assert docs and docs[0]["payload"] == {"marked": True, "from": "chat"}
    assert "boyfriend" not in repr(docs)


def test_nothing_is_saved_without_the_persons_yes_and_they_are_told_once(env):
    import consent
    consent.set_purpose(env.db, USER, "health_memory_from_chat", False)
    consent.forget(USER)
    first = send(env, "I slept 6 hours and drank 2 litres of water").json()["response"]
    assert env.db.rows("extracted_health_events", user_id=USER) == []
    assert "saving details from chat is off" in first
    second = send(env, "I walked for 30 minutes today").json()["response"]
    assert "saving details from chat is off" not in second     # said once, not nagged


def test_a_red_flag_message_saves_nothing_on_its_own(env):
    send(env, "I slept 6 hours and I have severe chest pain and can't breathe")
    assert all(r["extraction_status"] != "confirmed" for r in env.db.rows("extracted_health_events", user_id=USER))
