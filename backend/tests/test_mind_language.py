"""A5 language: loneliness, panic_attack and separation_anxiety are ordinary concepts (never escalate alone); anxiety stays the parent."""
from __future__ import annotations

import pytest

import organ_map_engine as O
from health_semantics import CONCEPT_PARENT, DISPLAY, analyze, display_name
from safety_engine import assess_safety


def active(text: str) -> set[str]:
    return {f.concept for f in analyze(text) if f.experiencer == "self" and f.assertion == "present"}


HITS = [
    ("I feel so lonely", "loneliness"),
    ("I'm feeling lonely since I moved here", "loneliness"),
    ("I feel so alone these days", "loneliness"),
    ("nobody talks to me", "loneliness"),
    ("I have no friends here", "loneliness"),
    ("I feel left out at work", "loneliness"),
    ("mujhe bahut akela lagta hai", "loneliness"),
    ("main akeli hoon", "loneliness"),
    ("I had a panic attack on the train", "panic_attack"),
    ("I keep panicking in crowds", "panic_attack"),
    ("I feel panicky", "panic_attack"),
    ("I can't calm down", "panic_attack"),
    ("I miss my mom so much", "separation_anxiety"),
    ("I get anxious when I'm away from my kids", "separation_anxiety"),
    ("I can't stand being apart from him", "separation_anxiety"),
    ("I'm so homesick", "separation_anxiety"),
    ("mummy ki bahut yaad aa rahi hai", "separation_anxiety"),
    ("I am anxious about the exam", "anxiety"),
    ("mujhe bahut ghabrahat ho rahi hai", "anxiety"),
    ("mujhe bahut chinta hai", "anxiety"),
]

QUIET = [
    "I live alone and I like it",
    "leave me alone",
    "I want to be alone for a bit",
    "I did the whole project all alone",
    "I'm not lonely",
    "I don't feel lonely anymore",
    "Lonely Planet is a good guide",
    "there is no panic, don't panic",
    "my sister had a panic attack",           # someone else
    "I miss the bus every morning",
    "I miss my train",
    "akela hi ghoomna pasand hai",
    "chinta mat karo",
]


@pytest.mark.parametrize("text,concept", HITS)
def test_concepts_are_found(text, concept):
    assert concept in active(text), (text, active(text))


@pytest.mark.parametrize("text", QUIET)
def test_near_misses_do_not_become_facts(text):
    assert not (active(text) & {"loneliness", "panic_attack", "separation_anxiety", "anxiety"}), (text, active(text))


@pytest.mark.parametrize("text", [t for t, _ in HITS])
def test_none_of_them_escalates_alone(text):
    a = assess_safety(text)
    assert a.state == "NO_REDFLAG" and not a.crisis, text


def test_panic_is_no_longer_swallowed_by_anxiety():
    assert active("I had a panic attack") == {"panic_attack"}
    assert "anxiety" in active("I feel anxious") and "panic_attack" not in active("I feel anxious")


def test_anxiety_is_the_parent_and_everything_maps_to_the_brain():
    assert CONCEPT_PARENT == {"panic_attack": "anxiety", "separation_anxiety": "anxiety"}
    for c in ("loneliness", "panic_attack", "separation_anxiety"):
        assert O.CONCEPT_ORGANS[c] == ("brain",)
        assert c in DISPLAY and display_name(c)


def test_a_logged_symptom_reaches_the_brain_area():
    obs = O._symptom_obs({"id": "1", "date": None, "source": "tracker"}, "Panic attack", 7, None)
    assert "brain" in obs["organs"] and "panic_attack" in obs["concepts"]
