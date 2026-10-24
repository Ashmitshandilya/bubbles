"""The friend voice: answers feelings and good news itself, never anything that sounds like a crisis, a symptom or a request for information."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import companion_voice as cv  # noqa: E402


@pytest.mark.parametrize("text,concepts,want", [
    ("I feel so alone today", ["loneliness"], "loneliness"),
    ("I'm so anxious about tomorrow", ["anxiety"], "anxiety"),
    ("I'm having a panic attack right now", ["panic_attack"], "panic_attack"),
    ("I miss my mom so much", ["separation_anxiety"], "separation_anxiety"),
    ("feeling really low today", ["low_mood"], "low_mood"),
    ("I'm so stressed with work", [], "stress"),
    ("feeling overwhelmed with everything", [], "stress"),
    ("I'm so tired today", ["fatigue"], "tired"),
    ("exhausted after a long day", [], "tired"),
    ("I got the job!", [], "joy"),
    ("feeling great today", [], "joy"),
    ("I passed my exam", [], "joy"),
])
def test_feelings_and_good_news_are_recognised(text, concepts, want):
    assert cv.concept_of(text, concepts) == want


@pytest.mark.parametrize("text,concepts", [
    ("I feel hopeless", ["low_mood"]),                         # a heaviness the model path (with its safety lines) should meet
    ("I don't want to be here anymore", ["low_mood"]),
    ("I feel low and it's been like this for months", ["low_mood"]),
    ("I'm so stressed, how can I calm down?", []),             # asks for information: a card or the model
    ("feeling sad and I have a bad headache", ["low_mood", "headache"]),   # a symptom as well
    ("I'm anxious about my medicine", ["anxiety"]),
    ("I am pregnant and so stressed", []),
    ("my husband hits me and I feel alone", ["loneliness"]),
    ("why do I feel so lonely", ["loneliness"]),
    ("I slept 7 hours last night and I am tired", ["fatigue"]),   # it carries a log: the normal flow saves and answers it
    ("tell me a joke", []),
    ("", []),
])
def test_anything_heavier_or_different_is_left_alone(text, concepts):
    assert cv.concept_of(text, concepts) is None


def test_replies_are_warm_short_enough_and_end_with_a_caring_question():
    for concept in cv.FEEL_CONCEPTS:
        for seed in ("a", "b", "c", "d"):
            text = cv.reply(concept, name="Riya", seed=seed)
            assert text.strip() and "Riya" in text
            assert text.rstrip().endswith("?") or concept == "panic_attack"   # one question, always the last thing
            assert text.count("?") <= 1


def test_replies_vary_with_the_message_but_are_stable_for_the_same_message():
    a1, a2 = cv.reply("anxiety", seed="x"), cv.reply("anxiety", seed="x")
    assert a1 == a2
    assert len({cv.reply("loneliness", seed=s) for s in "abcdefghij"}) >= 3


def test_short_and_calm_preferences_are_respected():
    full = cv.reply("low_mood", seed="a", length="balanced")
    short = cv.reply("low_mood", seed="a", length="short")
    assert len(short) < len(full) and short.rstrip().endswith("?")
    assert "professional" in full and "professional" not in short
    calm = cv.reply("stress", seed="a", tone="calm_direct")
    assert ". " not in calm.split("\n\n")[0] or len(calm.split("\n\n")[0].split(". ")) <= 2


def test_hinglish_stays_hinglish():
    text = cv.reply("loneliness", language="hi-latn", seed="a", name="Riya")
    assert any(w in text for w in ("Ye sunke", "Main yahin", "Kisi", "Koi hai", "Aaj kya"))
    assert "That sounds" not in text


def test_panic_always_carries_a_way_to_get_help_and_the_breathing_step():
    for seed in "abcdef":
        t = cv.reply("panic_attack", seed=seed, length="short")
        assert "breathe" in t.lower() or "breath" in t.lower()
        assert "medical help" in t


def test_nothing_in_any_reply_diagnoses_or_advises_medicine():
    blob = " ".join(" ".join(p) for bank in (cv.EN, cv.HI) for tup in bank.values() for p in tup).lower()
    for banned in ("depress", "disorder", "diagnos", "medicine", "tablet", "therapy will", "you have "):
        assert banned not in blob, banned
