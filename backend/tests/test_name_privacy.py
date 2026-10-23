"""Name privacy (plan C11): the provider sees labels, the person sees names."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import name_privacy as np_  # noqa: E402

FACTS = [
    {"key": "partner", "value": "Ashmit", "relation": "boyfriend"},
    {"key": "mother", "value": "Sunita", "relation": "mother"},
    {"key": "person:friend:rahul", "value": "Rahul", "relation": "friend"},
    {"key": "person:friend:neha", "value": "Neha", "relation": "friend"},
    {"key": "pet:dog:bruno", "value": "Bruno", "relation": "dog"},
    {"key": "name", "value": "Riya", "relation": None},
]


def test_roles_and_numbering():
    m = np_.build_map(FACTS)
    assert m == {"Ashmit": "[PARTNER]", "Sunita": "[MOTHER]", "Rahul": "[FRIEND]", "Neha": "[FRIEND_2]", "Bruno": "[PET]"}
    assert "Riya" not in m, "the person's own name is not a person in their life"


def test_mask_and_unmask_round_trip_in_english_and_hinglish():
    m = np_.build_map(FACTS)
    text = "Ashmit said Sunita's cooking is great, and mera dost Rahul bhi aaya. Neha called."
    masked = np_.mask(text, m)
    assert masked == "[PARTNER] said [MOTHER]'s cooking is great, and mera dost [FRIEND] bhi aaya. [FRIEND_2] called."
    assert np_.leaked(masked, m) == []
    assert np_.unmask(masked, m) == text


def test_devanagari_names():
    m = np_.build_map([{"key": "partner", "value": "राहुल"}])
    assert np_.mask("मेरे पति राहुल आज देर से आए", m) == "मेरे पति [PARTNER] आज देर से आए"
    assert np_.unmask("क्या [PARTNER] ठीक है?", m) == "क्या राहुल ठीक है?"


def test_only_whole_words_and_exact_case_are_masked():
    m = np_.build_map([{"key": "person:friend:will", "value": "Will"}, {"key": "person:friend:an", "value": "An"}])
    assert np_.mask("I will see Will tomorrow, Williams too, and an apple", m) == "I will see [FRIEND] tomorrow, Williams too, and an apple"


def test_longer_names_first():
    m = np_.build_map([{"key": "person:friend:anil", "value": "Anil"}, {"key": "person:friend:anil kumar", "value": "Anil Kumar"}])
    assert np_.mask("Anil Kumar and Anil", m) == "[FRIEND_2] and [FRIEND]"


def test_a_label_the_model_invents_never_reaches_the_person():
    m = np_.build_map(FACTS)
    assert np_.unmask("How is [PARTNER]? And [FRIEND_3]? And [MOTHER_IN_LAW]? And [partner]?", m) == "How is Ashmit? And your friend? And your mother-in-law? And Ashmit?"
    assert np_.unmask("[SOMETHING_ELSE] is fine", m) == "[SOMETHING_ELSE] is fine", "an unknown bracket is left alone, it may be the person's own text"
    assert np_.unmask("no labels here", m) == "no labels here" and np_.unmask("", m) == ""


def test_empty_maps_and_bad_facts_are_safe():
    assert np_.build_map([]) == {} and np_.build_map(None) == {}
    assert np_.build_map([{"key": "", "value": "X"}, {"value": None}, {"key": "partner", "value": " "}]) == {}
    assert np_.mask("hello Ashmit", {}) == "hello Ashmit" and np_.mask("", {"A": "[X]"}) == ""


def test_the_same_name_twice_in_the_facts_is_one_label():
    m = np_.build_map([{"key": "partner", "value": "Ashmit"}, {"key": "person:friend:ashmit", "value": "Ashmit"}])
    assert list(m.values()) == ["[PARTNER]"]
