"""Knowledge cards: the right card for a plain question, nothing for anything that needs care, and no dose or diagnosis in any card."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import knowledge_cards as kc  # noqa: E402


@pytest.mark.parametrize("text,card_id", [
    ("how can I fall asleep faster?", "sleep_cant_sleep"),
    ("I can't sleep, any tips?", "sleep_cant_sleep"),
    ("how much sleep do I need?", "sleep_how_much"),
    ("is coffee bad for sleep?", "caffeine"),
    ("how much water should I drink daily?", "water_how_much"),
    ("any tips to relieve period cramps?", "cramps_comfort"),
    ("tips for tired eyes from screens?", "eye_strain"),
    ("what are good iron rich foods?", "iron_foods"),
    ("how to get protein as a vegetarian?", "protein_veg"),
    ("how to calm down quickly?", "stress_breathing"),
    ("any exam stress tips?", "exam_stress"),
    ("what are some healthy snack ideas?", "healthy_snacks"),
    ("how to start exercising?", "exercise_motivation"),
    ("neend nahi aa rahi kya karu?", "sleep_cant_sleep"),
])
def test_the_right_card_for_a_plain_question(text, card_id):
    got = kc.match(text, active_concepts=())
    assert got and got["id"] == card_id, got and got["id"]


def test_a_matching_symptom_in_the_message_is_fine():
    assert kc.match("tips for headache relief?", active_concepts=["headache"])["id"] == "headache_comfort"
    assert kc.match("my back hurts from sitting all day, any posture tips?", active_concepts=["back_pain"])["id"] == "posture_back"


@pytest.mark.parametrize("text", [
    "how much paracetamol for headache relief?",         # a dose
    "tips for a sudden severe headache",                 # severity
    "headache relief, I've had it for weeks",            # duration
    "period cramps tips, I'm pregnant",                  # pregnancy
    "what helps my baby sleep faster?",                  # an infant
    "tips for headache relief and I coughed blood",      # a red flag word
    "how can I fall asleep, I feel hopeless",            # low mood words
    "I want to cut down on caffeine and I have diabetes",# a condition
    "hello there",
    "what is the meaning of life",
    "tell me a joke",
])
def test_anything_that_needs_care_is_left_to_the_model(text):
    assert kc.match(text, active_concepts=["headache"]) is None


def test_a_statement_with_no_matching_symptom_is_not_a_request():
    assert kc.match("I drink coffee in the morning", active_concepts=()) is None


def test_a_message_that_also_reports_something_else_is_left_alone():
    assert kc.match("any tips for period cramps?", active_concepts=["cramps", "chest_pain"]) is None
    assert kc.match("any tips for period cramps?", active_concepts=["cramps", "fatigue"])["id"] == "cramps_comfort"


def test_two_equally_good_topics_are_not_guessed():
    # "how much coffee ... how much sleep do I need": two cards tie at the same score
    assert kc.match("how much coffee is fine and how much sleep do i need", ()) is None


def test_the_reply_is_friendly_hedged_and_has_a_way_out():
    card = kc.match("how can I fall asleep faster?", ())
    text = kc.reply(card, name="Riya", seed="x")
    assert text.startswith("Riya,") and "- " in text and "clinician" in text
    short = kc.reply(card, length="short", seed="x")
    assert short.count("\n- ") == 3 and card["followup"] not in short and "clinician" in short   # the safety line is never dropped
    assert "Chalo" in kc.reply(card, language="hi-latn", seed="a") or "Zaroor" in kc.reply(card, language="hi-latn", seed="a") or "Theek" in kc.reply(card, language="hi-latn", seed="a")


def test_no_card_gives_a_dose_a_diagnosis_or_a_promise():
    text = " ".join(" ".join([c["answer"], *c.get("tips", []), c.get("clinician") or "", c.get("followup") or ""]) for c in kc.cards()).lower()
    for banned in (" mg ", "tablet", "dosage", "you are diagnosed", "you probably have", "cures", "guarantee", "will cure", "prescribe"):
        assert banned not in text, banned
    assert not re.search(r"\b\d+\s?(?:mg|mcg|iu|ml)\b", text)


def test_every_card_is_well_formed_and_names_a_way_out_or_is_clearly_harmless():
    ids = [c["id"] for c in kc.cards()]
    assert len(ids) == len(set(ids)) >= 25
    for c in kc.cards():
        assert c["answer"].strip() and c["tips"] and len(c["triggers"]) >= 3, c["id"]
        assert all(len(_t.split()) >= 2 for _t in c["triggers"]), c["id"]   # a trigger is a phrase, never a single common word
        assert c.get("clinician") or c["id"] in {"sleep_how_much", "protein_veg", "post_meal_walk", "screen_before_bed", "healthy_snacks"}, c["id"]


def test_no_trigger_of_one_card_swallows_another_cards_question():
    for c in kc.cards():
        for trigger in c["triggers"]:
            hit = kc.match(f"how to {trigger}?", ())
            assert hit is None or hit["id"] == c["id"], (c["id"], trigger, hit and hit["id"])
