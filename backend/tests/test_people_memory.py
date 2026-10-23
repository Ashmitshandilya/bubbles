"""Bubbles remembers the people and pets a person tells it about, and says so: "my boyfriend's name is Ashmit" is saved, always reaches the model,
is answered instantly when asked back, and is confirmed warmly when told. Nothing here calls a model."""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SECRET_KEY", "x")

from memory_manager import extract_explicit_personal_facts  # noqa: E402
from people_memory import extract_people_facts, recall_reply, recall_target, remembered_reply  # noqa: E402
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
    assert "boyfriend is called [PARTNER]" in seen[-1] and "Ashmit" not in seen[-1]   # the saved name is in front of the model only as a label (name_privacy.py)


def test_one_persons_facts_never_reach_another(env):
    from test_chat_http_flow import H
    send(env, "my boyfriends name is ashmit")
    other = env.client.post("/chat", json={"message": "who is my boyfriend?"}, headers={"Authorization": "Bearer tok2"})
    assert "Ashmit" not in other.json()["response"]


# ------------------------------------------------------------------------------------------------ Hinglish and Hindi (WP0.2)

def people(text):
    """(name, relation) of every person or pet saved from the text, in a fixed order."""
    return sorted((f["value"], f["relation"]) for f in extract_explicit_personal_facts(text) if f.get("relation"))


@pytest.mark.parametrize("text,expected", [
    ("mera boyfriend Ashmit hai", [("Ashmit", "boyfriend")]),                       # the sentence that was not remembered before
    ("meri girlfriend ka naam riya hai", [("Riya", "girlfriend")]),                  # lower case is fine when "ka naam" says it is a name
    ("Ashmit mera boyfriend hai", [("Ashmit", "boyfriend")]),
    ("mere pati ka naam Rahul Sharma hai", [("Rahul Sharma", "husband")]),
    ("मेरे पति का नाम राहुल है", [("राहुल", "husband")]),
    ("राहुल मेरा दोस्त है", [("राहुल", "friend")]),
    ("mera boyfriend राहुल hai", [("राहुल", "boyfriend")]),                          # a Devanagari word inside a Latin sentence
    ("Hey Bubbles Ashmit mera boyfriend hai", [("Ashmit", "boyfriend")]),            # a greeting in front is not part of the name
    ("mera boyfriend Ashmit hai aur meri behen Priya hai", [("Ashmit", "boyfriend"), ("Priya", "sister")]),
    ("my dog is called Bruno, mera bhai Karan hai", [("Bruno", "dog"), ("Karan", "brother")]),
])
def test_hinglish_and_hindi_statements_are_saved(text, expected):
    assert people(text) == expected


@pytest.mark.parametrize("text", [
    "mera boyfriend kaun hai?", "mera boyfriend kaun hai", "kya mera boyfriend Ashmit hai", "mera boyfriend Ashmit hai kya", "meri behen ka naam kya hai",
    "mera koi boyfriend nahi hai", "mera boyfriend Ashmit nahi hai", "Ashmit mera boyfriend nahi hai", "mera boyfriend ka naam Ashmit nahi hai",
    "usne kaha mera boyfriend Ashmit hai", "Riya ne bola Ashmit mera boyfriend hai", "उसने कहा मेरे पति का नाम राहुल है", "मम्मी ने बताया राहुल मेरा दोस्त है",
    "agar mera boyfriend Ashmit hota", "shayad Ashmit mera boyfriend hai", "mere pati ka naam shayad Rahul hai", "शायद मेरे पति का नाम राहुल है",
    "मेरा बॉयफ्रेंड कौन है?", "मेरा कोई बॉयफ्रेंड नहीं है", "mera boyfriend Ashmit tha", "Riya ka boyfriend Ashmit hai", "uska boyfriend Ashmit hai",
])
def test_questions_negations_reports_and_maybes_save_nothing(text):
    assert people(text) == []
    assert extract_people_facts(text, lambda *_: False) == []   # the Hinglish hedges stand on their own, not on memory_manager's English ones


def test_a_mood_or_a_job_is_not_a_name():
    for text in ("meri gf naraz hai", "mera boyfriend busy hai", "meri behen teacher hai", "mera bhai Delhi mein hai", "mera dost Monday ko aayega",
                 "mera dost Doctor hai", "Wo mera dost hai", "Yeh mera bhai hai", "वो मेरा दोस्त है", "मेरी बहन टीचर है", "मेरी बीवी नाराज़ है",
                 "meri behen ka naam hai"):
        assert people(text) == [], text


def test_hindi_relation_words_do_not_leak_into_english_sentences():
    for text in ("Ana is my beta tester", "Stripe is my saas", "my ma is Priya", "my dost is Rahul", "Rahul is my dost"):
        assert people(text) == [], text
    assert people("Neha is my sister-in-law") == [("Neha", "sister-in-law")]       # was read as "sister" before the in-laws were added


def test_a_sick_friend_is_saved_as_a_friend_and_the_saved_fact_says_nothing_about_illness():
    """This module only saves who Rahul is. Whether a friend's illness can leak into the user's own health record is health_semantics' job, see the route test."""
    facts = extract_explicit_personal_facts("mera dost Rahul bimar hai")
    assert [(f["key"], f["value"], f["relation"]) for f in facts] == [("person:friend:rahul", "Rahul", "friend")]
    assert facts[0]["content"] == "The user's friend is called Rahul."      # nothing about being ill, and nothing that sounds like the user's own health
    assert all(f["key"] not in {"symptom", "condition", "health"} for f in facts)


@pytest.mark.parametrize("name", ["Lucky", "Sunny", "Rose", "Will", "Mark", "Grace", "Tiger", "Moti"])
def test_names_that_are_also_common_words_are_still_names(name):
    assert people(f"mera dost {name} hai") == [(name, "friend")]
    assert people(f"mere kutte ka naam {name.lower()} hai") == [(name, "dog")]


def test_a_feeling_word_is_a_name_only_when_the_person_said_it_was_one():
    assert people("mera kutta ka naam Happy hai") == [("Happy", "dog")]
    assert people("mera dost Happy hai") == [] and people("my boyfriend is happy") == []        # a bare "Happy" is far more likely a mood


def test_lower_case_names_need_ka_naam_to_be_trusted():
    assert people("mera boyfriend ka naam ashmit hai") == [("Ashmit", "boyfriend")]
    assert people("mera boyfriend ashmit hai") == []        # same as English "my boyfriend is ashmit": "meri gf naraz hai" must not become a girlfriend called Naraz
    assert people("meri gf naraz hai") == []


def test_names_in_devanagari_are_kept_as_typed():
    assert got("मेरी बहन का नाम प्रिया है") == [("person:sister:प्रिया", "प्रिया")]
    assert got("मेरे पति का नाम राहुल शर्मा है") == [("partner", "राहुल शर्मा")]
    assert got("मेरे कुत्ते का नाम ब्रूनो है") == [("pet:dog:ब्रूनो", "ब्रूनो")]


def test_mera_mama_is_an_uncle_and_never_overwrites_the_mother():
    assert got("mera mama Rakesh hai") == [("person:uncle:rakesh", "Rakesh")]
    assert got("मेरे मामा का नाम राकेश है") == [("person:uncle:राकेश", "राकेश")]
    assert got("meri mama Sunita hai") == [("mother", "Sunita")] and got("my mama is Sunita") == [("mother", "Sunita")]


def test_in_laws_hold_one_person_each_so_a_new_name_is_a_correction():
    assert got("meri saas Kamla hai")[0][0] == got("meri saas Sheela hai")[0][0] == "mother-in-law"
    assert got("my father-in-law's name is Mohan") == [("father-in-law", "Mohan")]
    assert got("meri bhabhi Neha hai")[0][0] != got("meri bhabhi Sonal hai")[0][0]       # two sisters-in-law can both stay


def test_what_was_saved_in_hindi_is_confirmed_and_recalled_in_english_words():
    facts = extract_explicit_personal_facts("मेरे पति का नाम राहुल है")
    text = remembered_reply(facts, seed="x")
    assert "राहुल is your husband" in text and "—" not in text
    saved = [{"key": f["key"], "value": f["value"], "relation": f["relation"]} for f in facts]
    assert recall_reply(recall_target("what's my husband's name?"), saved, account_name=None) == "Of course I remember: your husband is राहुल."


def test_telling_bubbles_in_hinglish_saves_it_and_answers_instantly_without_a_model(env):
    res = send(env, "mera boyfriend Ashmit hai")
    assert res.status_code == 200 and "Ashmit is your boyfriend" in res.json()["response"] and env.ai_calls == []
    saved = [r["structured_data"] for r in env.db.rows("memory_items") if (r.get("structured_data") or {}).get("key") == "partner"]
    assert len(saved) == 1 and saved[0]["value"] == "Ashmit" and saved[0]["relation"] == "boyfriend"


def test_a_name_next_to_a_hinglish_disclosure_is_neither_saved_nor_cheerfully_confirmed_on_the_real_route(env):
    for text in ("mera pati Rahul mujhe maar dalega", "mera boyfriend Ashmit mujhe maarta hai", "mera dost Rahul ne zeher kha liya hai"):
        res = send(env, text)
        assert res.status_code == 200 and "I'll remember that" not in res.json()["response"], text
    assert not [r for r in env.db.rows("memory_items") if (r.get("structured_data") or {}).get("relation")]


def test_asking_in_hinglish_saves_nothing(env):
    for text in ("mera boyfriend kaun hai?", "mera koi boyfriend nahi hai", "usne kaha mera boyfriend Ashmit hai"):
        assert send(env, text).status_code == 200
    assert not [r for r in env.db.rows("memory_items") if (r.get("structured_data") or {}).get("relation")]


def test_the_hinglish_word_bimar_next_to_a_friends_name_writes_no_health_row(env):
    """Narrow on purpose: today health_semantics does not know "bimar", so nothing is written for this sentence. It does NOT show that a friend's illness
    can never become the user's ("mera dost Rahul ko fever hai" still can: the existing experiencer gap in health_semantics, which WP0.2 does not own)."""
    res = send(env, "mera dost Rahul bimar hai")
    assert res.status_code == 200
    assert env.db.rows("extracted_health_events") == []
    stored = [r["structured_data"] for r in env.db.rows("memory_items")]
    assert [(d["key"], d["value"]) for d in stored] == [("person:friend:rahul", "Rahul")]


@pytest.mark.parametrize("text", [
    "mera pati Rahul mujhe maar dalega", "mera boyfriend Ashmit mujhe maarta hai", "mera pati Rahul mujhe peetta hai", "mera boyfriend Ashmit mujhe gala dabata hai",
    "mera dost Rahul ne zeher kha liya hai", "meri behen Priya ko uska pati maarta hai", "mere papa Suresh mujhe dhamkate hain",
])
def test_a_name_next_to_a_hinglish_disclosure_is_not_an_introduction(text):
    """The bare form needs "hai" (or a mood word and "hai", or the end of the message) after the name. Before that rule these were saved as people and,
    through chat_pipeline._only_tells_a_fact, answered with the cheerful remembered line and no model call."""
    import chat_pipeline
    assert people(text) == []
    assert chat_pipeline.route_turn(chat_pipeline.analyze_turn(text, [])) != "remembered"


@pytest.mark.xfail(strict=False, reason="Not this module's job: chat_pipeline._only_tells_a_fact treats any short message with a saved name as 'just telling me a fact', so an "
                   "introduction with a disclosure after it gets the cheerful remembered line unless something runs first. English has done this since the feature "
                   "shipped. Safe Harbor (WP0.1) routes these before 'remembered' and makes this XPASS; a stricter _only_tells_a_fact is the orchestrator's.")
@pytest.mark.parametrize("text", ["my boyfriend is Ashmit and he hits me", "mera pati Rahul hai aur wo mujhe maarta hai"])
def test_an_introduction_with_a_disclosure_after_it_is_never_answered_with_the_remembered_line(text):
    import chat_pipeline
    assert chat_pipeline.route_turn(chat_pipeline.analyze_turn(text, [])) != "remembered"


# ------------------------------------------------------------------------------------------------ only a trusted shape saves a bare name

@pytest.mark.parametrize("text,expected", [
    ("mera dost Rahul bimar hai", [("Rahul", "friend")]),                  # a mood word and "hai" after the name
    ("meri behen Priya naraz hai", [("Priya", "sister")]), ("mera bhai Karan busy hai", [("Karan", "brother")]),
    ("mera dost Rahul theek hai", [("Rahul", "friend")]), ("मेरा दोस्त Rahul बीमार है", [("Rahul", "friend")]),
    ("mera boyfriend Ashmit", [("Ashmit", "boyfriend")]), ("mera boyfriend Ashmit.", [("Ashmit", "boyfriend")]),   # nothing after the name
    ("mera boyfriend Ashmit hai na", []),                                   # "na" is the tag question
])
def test_a_bare_name_is_trusted_only_before_hai_a_mood_word_and_hai_or_the_end(text, expected):
    assert people(text) == expected


@pytest.mark.parametrize("text", [
    # a script switch: the Devanagari word is a state, a place, a time or a job, never a name
    "mera dost बीमार hai", "meri behen नाराज़ hai", "mera boyfriend अभी ghar pe hai", "mera bhai दिल्ली me hai", "mera dost घर pe hai", "meri behen टीचर hai",
    "mera dost डॉक्टर hai", "mera bhai आज आ रहा hai", "mera boyfriend कल hai",
    # a capitalised Latin word that is a place, a state, a shop word or an adverb
    "mera bhai Goa gaya hai", "mera bhai Dubai gaya hai", "meri behen Pregnant hai", "meri behen Diabetic hai", "mera dost Depressed hai", "mera dost Bilkul theek hai",
    "meri behen Canada jaa rahi hai", "mera dost Instagram use karta hai", "meri mummy Hospital gayi hain", "mera boyfriend Office gaya hai",
    "mera bhai Dubai hai", "meri mummy Hospital mein hain", "mera dost Pregnant hai",
])
def test_a_place_a_state_a_time_or_a_job_is_not_a_name_even_after_a_script_switch(text):
    assert people(text) == []


def test_the_nukta_in_a_devanagari_stop_word_does_not_matter():
    nukta = "\N{DEVANAGARI SIGN NUKTA}"
    for word in (f"नाराज{nukta}", "नाराज", "बिज" + nukta + "ी", "बिजी", "\N{DEVANAGARI LETTER JA}\N{DEVANAGARI SIGN NUKTA}िंदा"):
        assert people(f"mera dost {word} hai") == [], word


def test_the_name_in_front_of_a_place_is_not_swallowed_into_the_name():
    assert people("mera bhai Rahul Dubai gaya hai") == []                  # not "Rahul Dubai": nothing after a bare name is trusted but hai
    assert people("mera bhai Rahul Dubai hai") == [("Rahul", "brother")]   # a place is dropped from a two-word name
    assert people("mera bhai Rahul Sharma hai") == [("Rahul Sharma", "brother")]


# ------------------------------------------------------------------------------------------------ the nearest real-world twins of the spec hedges

@pytest.mark.parametrize("text", [
    # text-speak "no"
    "mera boyfriend Ashmit ni hai", "mera boyfriend Ashmit nai hai", "mera boyfriend Ashmit naa hai", "mera boyfriend Ashmit na hai",
    "mera boyfriend ka naam Ashmit ni hai", "mera boyfriend ka naam Ashmit nai hai", "mera boyfriend ka naam Ashmit naa hai", "mera boyfriend ka naam Ashmit na hai",
    "Ashmit mera boyfriend hai na",
    # somebody else said, thought, asked or worked it out
    "Riya keh rahi thi mera boyfriend Ashmit hai", "mummy bol rahi thi mera boyfriend Ashmit hai", "wo samajhta hai mera boyfriend Ashmit hai",
    "Riya ne puchha mera boyfriend Ashmit hai", "Riya ke hisaab se mera boyfriend Ashmit hai", "unka kehna hai mera boyfriend Ashmit hai",
    "uske anusaar mera boyfriend Ashmit hai", "Riya keh rahi thi Ashmit mera boyfriend hai", "mummy bol rahi thi mere pati ka naam Rahul hai",
    "Riya ke hisaab se mere pati ka naam Rahul hai", "उसके अनुसार राहुल मेरा दोस्त है", "उसने पूछा राहुल मेरा दोस्त है",
    # a wish, a dream, a maybe
    "kaash mera boyfriend Ashmit hota", "mera boyfriend Ashmit hota toh", "mera boyfriend Ashmit ho sakta hai", "mera boyfriend Ashmit ho jaye",
    "mera boyfriend Ashmit ban jayega", "like, mera boyfriend Ashmit hai, but only in my dreams", "kaash Ashmit mera boyfriend hota",
    "kaash mere pati ka naam Rahul hota", "mere pati ka naam Rahul ho sakta hai", "Ashmit mera boyfriend hai, but only in my dreams",
    "काश मेरे पति का नाम राहुल है", "मेरे पति का नाम राहुल हो सकता है",
])
def test_hinglish_hedge_twins_save_nothing(text):
    assert people(text) == []
    assert extract_people_facts(text, lambda *_: False) == []   # on their own, without memory_manager's English hedges


def test_a_name_that_spells_like_a_hedge_word_is_still_a_name_outside_the_hedge():
    assert people("mera dost Bola hai") == [("Bola", "friend")] and people("mera dost Kehar hai") == [("Kehar", "friend")]


# ------------------------------------------------------------------------------------------------ English is exactly what it was

# The stop list the English patterns used before Hinglish existed. It must not grow: a name that spells like a Hindi word stays a name in English.
OLD_ENGLISH_NOT_NAMES = """a an the my your his her their our not no so very really quite too just also still always never now here there who what why how when where
he she it they we you i this that these those someone somebody anyone nobody something nothing everyone also doing fine ok okay good bad sad happy angry upset
tired sick ill unwell away home late early busy gone back coming leaving going getting being feeling mine yours his hers ours theirs one two three""".split()
HINDI_LOOKING_NAMES = ["Mai", "Han", "Ye", "Bro", "Ji", "Kon", "Hae", "Ho", "Tu", "Hi", "Kab", "Naam", "Aap", "Bhai", "Yaar", "Ab", "Ek", "Jab", "Kal", "Me"]


def test_the_english_patterns_use_the_old_stop_list_and_nothing_more():
    import people_memory
    extra = {"muslim", "hindu", "violent", "abusive", "alcoholic", "drunk", "toxic"}               # religions and traits are never names (added with Hinglish memory)
    assert frozenset(OLD_ENGLISH_NOT_NAMES) <= people_memory._NOT_NAMES_EN and extra <= people_memory._NOT_NAMES_EN
    for word in OLD_ENGLISH_NOT_NAMES:                              # every old stop word is still refused in English...
        assert got(f"my friend is {word.capitalize()}") == [], word
    for name in HINDI_LOOKING_NAMES:                                # ...and no Hindi word is
        assert got(f"my friend is called {name}") == [("person:friend:" + name.lower(), name)], name
        assert got(f"my sister is {name}") == [("person:sister:" + name.lower(), name)], name
        assert got(f"{name} is my friend") == [("person:friend:" + name.lower(), name)], name
    assert got("my dog is called Bro") == [("pet:dog:bro", "Bro")]


def test_the_hinglish_hedges_never_run_on_english_sentences():
    assert got("my boyfriend is Ashmit and he got a flu jab") == [("partner", "Ashmit")]              # "jab" is a Hinglish doubt word
    assert got("my boyfriend is Ashmit, kaash") == [("partner", "Ashmit")] and got("my sister is Riya, she is in my dreams") == [("person:sister:riya", "Riya")]
    assert got("she said my sister is Riya") == []                                                     # the English said-words still hedge an English match


# ------------------------------------------------------------------------------------------------ cost

def test_a_very_long_message_stays_cheap_and_stops_at_four_people(monkeypatch):
    import time
    import people_memory
    calls = []
    real = people_memory._doubtful
    monkeypatch.setattr(people_memory, "_doubtful", lambda text, m: calls.append(1) or real(text, m))
    repeated = "mera boyfriend Ashmit hai " * 300                                                   # 7,800 characters, one person said 300 times
    assert people(repeated) == [("Ashmit", "boyfriend")] and len(calls) == 1                        # the repeats are not even checked
    started = time.perf_counter()
    for text in ("mera dost Rahul " * 500, "mera boyfriend Ashmit hai kya " * 270, "mera boyfriend Ashmit hai " * 300 + "mera bhai Karan hai"):
        people(text)
    assert time.perf_counter() - started < 0.5                                                      # about 40 ms here; the three took about 1.2 s before the window
    many = " ".join(f"mera dost {n} hai" for n in ("Aman", "Bela", "Charu", "Dev", "Esha", "Farah"))
    assert len(extract_people_facts(many, lambda *_: False)) == 4


# ------------------------------------------------------------------------------------------------ the Hinglish eval set

EVAL = Path(__file__).parent / "eval" / "people_memory_hinglish.jsonl"


def test_hinglish_eval_is_perfect_on_statements_and_saves_nothing_on_everything_else(capsys):
    """tests/eval/people_memory_hinglish.jsonl: every statement is saved exactly, every question, negation, report, hedge and non-name saves nothing.
    The note of each line starts with its kind ("statement: ...", "question: ...")."""
    cases = [json.loads(line) for line in EVAL.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) >= 80
    right, wrong, saved_when_it_should_not = Counter(), [], Counter()
    for case in cases:
        kind = case["note"].split(":")[0]
        got_people = people(case["text"])
        want = sorted((e["name"], e["relation"]) for e in case["expect"])
        if got_people == want:
            right[kind] += 1
        else:
            wrong.append((case["text"], got_people, want))
            if not want:
                saved_when_it_should_not[kind] += 1
    total = Counter(case["note"].split(":")[0] for case in cases)
    with capsys.disabled():
        print("\npeople_memory_hinglish: " + ", ".join(f"{kind} {right[kind]}/{total[kind]}" for kind in sorted(total))
              + f" | {sum(right.values())}/{len(cases)} right, wrong saves {sum(saved_when_it_should_not.values())}")
    assert not wrong, wrong
    assert total["statement"] >= 40 and total["question"] >= 10 and total["negation"] >= 8 and total["report"] >= 6 and total["hedge"] >= 8
    assert total["no name"] >= 25 and total["disclosure"] >= 5 and total["unsure"] >= 3   # mixed-script and capitalised non-names, and names next to a disclosure


# ------------------------------------------------------------------------------------------------ final fix round

@pytest.mark.parametrize("text,expected", [
    ("my mother in law's name is Kamla", [("Kamla", "mother-in-law")]),
    ("my father in law is called Ramesh", [("Ramesh", "father-in-law")]),
    ("mere bete ka naam Aarav hai", [("Aarav", "son")]),
    ("mera boyfriend Tanmay hai lekin shayad hum breakup kar lein", [("Tanmay", "boyfriend")]),      # the maybe belongs to the next clause
    ("mere husband ka naam Aman nahi balki Arman hai", [("Arman", "husband")]),                      # a correction keeps the new name
])
def test_final_round_statements_that_were_missed_are_saved(text, expected):
    assert people(text) == expected


@pytest.mark.parametrize("text", [
    "I wish my husband was Shah Rukh", "maybe my best friend is Sana", "perhaps my boyfriend is Karan", "if only my husband was Ranbir",
    "mera pati Mohit hai ya Rohit, yaad nahi aa raha", "pata nahi mera pati Mohit hai ya Rohit",
    "mere husband ka naam Aman nahi balki Arman hai kya", "kaash mere husband ka naam Aman nahi balki Arman hota",
])
def test_final_round_a_wish_a_maybe_or_a_forgotten_name_saves_nothing(text):
    assert people(text) == []


def test_final_round_a_recall_question_knows_a_mother_in_law_typed_with_spaces():
    assert recall_target("what's my mother in law's name?") == "mother-in-law"
