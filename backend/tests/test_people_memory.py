"""Bubbles remembers the people and pets a person tells it about, and says so: "my boyfriend's name is Ashmit" is saved, always reaches the model,
is answered instantly when asked back, and is confirmed warmly when told. Nothing here calls a model."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SECRET_KEY", "x")

from memory_manager import extract_explicit_personal_facts  # noqa: E402
from people_memory import recall_reply, recall_target, remembered_reply  # noqa: E402
from test_chat_http_flow import env, send  # noqa: E402,F401  (env is a fixture)


def got(text):
    return [(f["key"], f["value"]) for f in extract_explicit_personal_facts(text)]


@pytest.mark.parametrize("text,expected", [
    ("my boyfriends name is ashmit", [("partner", "Ashmit")]),                      # typed fast: no apostrophe, lower case
    ("My boyfriend's name is Ashmit.", [("partner", "Ashmit")]),
    ("my girlfriend is called Riya", [("partner", "Riya")]),
    ("my boyfriend is Ashmit", [("partner", "Ashmit")]),
    ("Ashmit is my boyfriend", [("partner", "Ashmit")]),
    ("I'm dating Rahul", [("partner", "Rahul")]),
    ("my husband's name is Dev Anand", [("partner", "Dev Anand")]),
    ("my mom's name is sunita", [("mother", "Sunita")]),
    ("I have a dog called Bruno", [("pet:dog:bruno", "Bruno")]),
    ("my dog is called bruno and my sister is Riya", [("pet:dog:bruno", "Bruno"), ("person:sister:riya", "Riya")]),
    # not a name, not about the person, not a plain statement: nothing is saved
    ("my boyfriend is tired today", []),
    ("my boyfriend is so sweet", []),
    ("He is my boyfriend", []),
    ("his boyfriend is Sam", []),
    ("my girlfriend isn't Priya", []),
    ("what if my boyfriend is Ashmit?", []),
    ("she said my boyfriend is Ashmit", []),
    ('he wrote "my boyfriend is Ashmit"', []),
    ("my boyfriend is Ashmit?", []),
    # alongside the older facts
    ("My name is Priya and my boyfriend is Ashmit", [("name", "Priya"), ("partner", "Ashmit")]),
])
def test_people_are_saved_only_when_plainly_stated(text, expected):
    assert got(text) == expected


def test_the_saved_fact_carries_the_relation_and_a_plain_sentence():
    fact = extract_explicit_personal_facts("my boyfriends name is ashmit")[0]
    assert fact["relation"] == "boyfriend" and fact["content"] == "The user's boyfriend is called Ashmit."


def test_a_new_partner_name_replaces_the_old_one_but_two_siblings_both_stay():
    assert got("my boyfriend is Ashmit")[0][0] == got("my boyfriend is Aman")[0][0] == "partner"   # one key: a new name is a correction
    assert got("my sister is Riya")[0][0] != got("my sister is Meera")[0][0]                       # two sisters can both be remembered


@pytest.mark.parametrize("text,target", [
    ("what's my boyfriend's name?", "partner"), ("whats my boyfriends name", "partner"), ("do you remember my boyfriend", "partner"),
    ("who is my girlfriend", "partner"), ("what's my dog's name", "dog"), ("do you remember my mom's name?", "mother"),
    ("what's my name", "name"), ("do you remember my name?", "name"), ("what do you call me", "name"), ("who am I?", "name"),
    # the same words inside another question or statement are not recall questions
    ("what is my mom's blood pressure", None), ("my boyfriend's name is Ashmit", None), ("who am I to judge", None),
    ("what is my sister's dosage of iron for her anaemia and how long should she take it", None),
])
def test_recall_questions_are_recognised_and_lookalikes_are_not(text, target):
    assert recall_target(text) == target


FACTS = [{"key": "partner", "value": "Ashmit", "relation": "boyfriend"}, {"key": "name", "value": "Riya", "relation": None}]


def test_recall_answers_from_saved_facts_and_admits_what_is_missing():
    assert recall_reply("partner", FACTS, account_name=None) == "Of course I remember: your boyfriend is Ashmit."
    assert recall_reply("name", FACTS, account_name="Sam") == "Of course: you're Riya."          # what they told Bubbles beats the sign-up name
    assert recall_reply("name", [], account_name="Sam") == "Of course: you're Sam."
    assert "don't have your" in recall_reply("dog", FACTS, account_name=None) and "Tell me" in recall_reply("dog", FACTS, account_name=None)
    assert "don't have your name yet" in recall_reply("name", [], account_name=None)


def test_the_remembered_reply_names_what_was_saved_and_follows_the_house_voice():
    text = remembered_reply(extract_explicit_personal_facts("my boyfriends name is ashmit"), seed="x")
    assert "Ashmit is your boyfriend" in text and "remember" in text and text.endswith("?")
    for line in (text, remembered_reply(extract_explicit_personal_facts("my name is Priya"), seed="y")):
        assert "—" not in line   # no em-dashes in visible text


# ------------------------------------------------------------------------------------------------ through the real chat route

def test_telling_bubbles_a_fact_saves_it_and_answers_instantly_without_a_model(env):
    res = send(env, "my boyfriends name is ashmit")
    body = res.json()
    assert res.status_code == 200 and "Ashmit is your boyfriend" in body["response"] and "remember" in body["response"]
    assert env.ai_calls == []
    saved = [r for r in env.db.rows("memory_items") if (r.get("structured_data") or {}).get("key") == "partner"]
    assert len(saved) == 1 and saved[0]["structured_data"]["value"] == "Ashmit" and saved[0]["structured_data"]["relation"] == "boyfriend"


def test_asking_back_in_a_new_chat_is_answered_from_memory_without_a_model(env):
    send(env, "my boyfriends name is ashmit")
    res = send(env, "do you remember my boyfriend's name?")    # no conversation id: a brand-new chat
    assert res.status_code == 200 and "Ashmit" in res.json()["response"]
    assert env.ai_calls == []


def test_a_missing_fact_is_admitted_and_never_invented(env):
    res = send(env, "what's my dog's name?")
    assert "don't have your dog" in res.json()["response"] and env.ai_calls == []


def test_a_message_with_a_health_fact_still_goes_to_the_model_but_the_fact_is_saved_and_in_front_of_it(env):
    seen = []
    original = env.main.ask_bubbles

    def spy(message, **kw):
        seen.append(kw.get("memory_context", ""))
        return original(message, **kw)
    env.main.ask_bubbles = spy
    send(env, "my boyfriends name is ashmit")
    res = send(env, "I slept badly and have a mild headache, any tips?")        # nothing in it shares a word with the saved fact
    assert res.status_code == 200 and env.ai_calls
    assert "boyfriend is called Ashmit" in seen[-1]


def test_one_persons_facts_never_reach_another(env):
    from test_chat_http_flow import H
    send(env, "my boyfriends name is ashmit")
    other = env.client.post("/chat", json={"message": "who is my boyfriend?"}, headers={"Authorization": "Bearer tok2"})
    assert "Ashmit" not in other.json()["response"]
