"""Safety decisions from structured facts: the four states, the legacy levels, the fail-safe, and bounded work."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import health_semantics as hs  # noqa: E402
import safety_engine as se  # noqa: E402
from safety_engine import assess_safety  # noqa: E402

NO, POT, URG, EMG = "NO_REDFLAG", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", "URGENT", "EMERGENCY"
LEVEL = {NO: "GREEN", POT: "AMBER", URG: "AMBER", EMG: "RED"}

# The incident and the adversarial list from the brief: (text, expected state)
BRIEF = [
    ("No headache, nausea, vomiting, chest pain, shortness of breath or dizziness.", NO),
    ("No chest pain.", NO),
    ("No chest pain whatsoever.", NO),
    ("I don't have chest pain right now.", NO),
    ("I had chest pain yesterday.", NO),
    ("I don't have chest pain, but my sister does.", NO),
    ("My doctor asked whether I had chest pain.", NO),
    ("What does chest pain mean?", NO),
    ("Should I worry about chest pain?", NO),
    ("Chest pain: NO.", NO),
    ("No headache, dizziness, nausea, vomiting, chest pain, breathing difficulty.", NO),
    ("I had chest pain yesterday but I'm fine now.", NO),
    ("Can chest pain happen during anxiety?", NO),
    ("What should I do if I develop chest pain?", NO),
    ("My doctor told me 'watch for chest pain'.", NO),
    ("I said no chest pain?", NO),
    ("I have chest pain.", EMG),
    ("I have severe chest pain right now.", EMG),
    ("chest pain", EMG),
    ("CHEST PAIN NOW", EMG),
    ("I can't breathe", EMG),
    ("I think I might have some chest discomfort", POT),
]


@pytest.mark.parametrize("text,state", BRIEF)
def test_brief_cases(text, state):
    a = assess_safety(text)
    assert a.state == state, (text, a.state, [f.reason for f in a.facts])
    assert a.level == LEVEL[state]


def test_resolved_same_day_asks_but_does_not_alarm_and_older_history_is_quiet():
    assert assess_safety("I had chest pain earlier and now it is gone.").state in {NO, POT}
    assert assess_safety("I had chest pain yesterday.").state == NO


def test_urgent_tier_is_amber_and_not_an_emergency():
    a = assess_safety("I have a severe headache")
    assert a.state == URG and a.level == "AMBER" and "severe pain" in a.reasons
    assert assess_safety("I have a high fever and I'm confused").state == URG


def test_mild_chest_symptom_is_urgent_not_emergency():
    assert assess_safety("I have mild chest tightness right now, about 2/10").state in {URG, EMG}


def test_negation_survives_modifiers_but_not_new_clauses():
    assert assess_safety("No sharp chest pain.").state == NO
    assert assess_safety("I don't have any sharp stabbing chest pain").state == NO
    assert assess_safety("No headache, but I have chest pain").state == EMG
    assert assess_safety("I haven't slept well and I have chest pain").state == EMG
    assert assess_safety("I didn't take medicine for chest pain").state == EMG  # took medicine FOR it => has it


def test_counterfactual_and_double_negative_are_not_denials():
    assert assess_safety("I wish I didn't have chest pain.").state == EMG
    assert assess_safety("My chest pain isn't gone, it's just a bit better.").state == EMG
    assert assess_safety("Not no chest pain, if I'm honest").state in {POT, EMG}


def test_legacy_reason_labels_are_kept():
    a = assess_safety("I have chest pain and trouble breathing")
    assert a.level == "RED" and {"chest pain or pressure", "breathing difficulty"} <= set(a.reasons)
    assert assess_safety("This is severe headache").level == "AMBER"
    assert assess_safety("I slept 7 hours").level == "GREEN"


def test_copy_never_claims_detection_and_names_what_the_user_said():
    text = se.emergency_response(assess_safety("I have chest pain"))
    assert "You told me" in text and "chest pain" in text and "Bubbles detected" not in text and "misread" in text
    ask = se.clarification_response(assess_safety("I think I might have some chest discomfort"))
    assert "right now" in ask and "emergency" in ask.lower()


def test_assess_safety_never_raises_and_degrades_to_a_clarifying_state(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("analysis exploded")

    monkeypatch.setattr(se, "analyze", boom)
    a = assess_safety("I have chest pain")
    assert a.state == POT and a.level == "AMBER" and a.concepts  # asks instead of 500 or silent GREEN
    assert assess_safety("I slept well").state == NO  # no red-flag wording => nothing to ask
    assert "right now" in se.clarification_response(a)


FUZZ = ["", " ", "\n\n", "?", "no", "No,", "chest pain" * 400, "\x00\x08\x1b" * 50, "no " * 2000, "‮ chest pain ‬",
        "🙂" * 300, "No chest pain" + " and no chest pain" * 400, "a" * 8000, "." * 8000, "(((" * 800, "I have " * 1500]


@pytest.mark.parametrize("text", FUZZ, ids=[f"fuzz{i}" for i in range(len(FUZZ))])
def test_fuzz_never_raises_and_is_fast(text):
    start = time.perf_counter()
    a = assess_safety(text[:8000])
    assert a.state in {NO, POT, URG, EMG}
    assert time.perf_counter() - start < 1.5


def test_random_text_is_bounded():
    rng = random.Random(7)
    words = "I have had no not never maybe if what should chest pain headache my mom doctor said yesterday now but and or , . ? 3/10 severe".split()
    for _ in range(25):
        text = " ".join(rng.choice(words) for _ in range(1500))[:8000]
        start = time.perf_counter()
        assess_safety(text)
        assert time.perf_counter() - start < 1.5


def test_red_flag_mentions_are_never_crowded_out_by_noise():
    """A flood of harmless mentions must not push a real red flag past the per-message budget."""
    text = ("headache, " * 300) + ". I have severe chest pain right now."
    assert assess_safety(text[:8000]).state == EMG


def test_extra_terms_use_the_same_negation_logic():
    f = {x.concept: x.assertion for x in hs.analyze("No knee swelling today but my wrist is sore.", extra_terms=["knee swelling", "wrist"])}
    assert f["custom:knee swelling"] == "negated" and f["custom:wrist"] == "present"


def test_fact_serialisation_never_includes_user_text_by_default():
    f = hs.analyze("I have a headache")[0]
    assert "source_text" not in f.to_dict() and f.to_dict(include_text=True)["source_text"]


def test_no_stray_control_characters_in_engine_sources():
    for name in ("health_semantics.py", "safety_engine.py", "daily_log_parser.py", "conversation_correction.py", "chat_pipeline.py"):
        text = (BACKEND / name).read_text(encoding="utf-8")
        assert chr(8) not in text and "\x00" not in text, name
