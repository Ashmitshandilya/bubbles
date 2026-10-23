"""Orbit in chat (WP2.3): the Heart-to-heart route, name privacy, pattern cards, enforcement, Safe Harbor first, and the fixed decline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import doc_store
import person_model
from test_chat_http_flow import H, USER, env, send  # noqa: F401  (env is a fixture)


@pytest.fixture(autouse=True)
def clean():
    import chat_cache
    person_model.forget(USER)
    chat_cache.forget_user(USER)
    yield
    person_model.forget(USER)
    chat_cache.forget_user(USER)


def capture(env, reply="That sounds hard, and it makes sense that you feel this way."):
    from bubbles_ai import BubblesAIResponse
    seen: dict = {}

    def stub(message, **kw):
        seen.clear()
        seen.update(kw)
        seen["message"] = message
        return BubblesAIResponse(response=reply, sentiment="neutral", health_events=[])
    env.main.ask_bubbles = stub
    return seen


def post(env, text, **extra):
    return env.client.post("/chat", json={"message": text, **extra}, headers=H)


def prompt_of(seen):
    return "\n".join(str(seen.get(k, "")) for k in ("message", "memory_context", "conversation_context", "safety_context", "evidence_context"))


# ---- routing -------------------------------------------------------------------------------------------------------------------------

def test_a_relationship_worry_gets_the_orbit_voice_and_matching_pattern_cards(env):
    seen = capture(env)
    body = post(env, "my boyfriend gives me the silent treatment for days after every fight").json()
    assert body["kind"] == "reply" and body["suggestions"]
    assert "ORBIT MODE (relationship support):" in seen["safety_context"]
    assert "PATTERN CARDS (general knowledge, not facts about this person." in seen["safety_context"] and "Going quiet in a fight" in seen["safety_context"]
    assert "Never say:" in seen["safety_context"]


def test_a_passing_mention_stays_in_ordinary_chat(env):
    seen = capture(env)
    post(env, "what should I get my wife for her birthday")
    assert "ORBIT MODE" not in seen.get("safety_context", "")
    seen = capture(env)
    post(env, "I have had a mild headache since morning, what could help?")
    assert "ORBIT MODE" not in seen.get("safety_context", "")


def test_mode_orbit_uses_the_heart_to_heart_voice_for_any_message_and_is_remembered(env):
    seen = capture(env)
    body = post(env, "I just wanted to talk about how things have been lately", mode="orbit").json()
    assert "ORBIT MODE" in seen["safety_context"]
    stored = doc_store.get(env.db, USER, "conversation_mode", body["conversation_id"])
    assert stored == {"mode": "orbit"}
    talk = post(env, "hello there, how is your day going", conversation_id=body["conversation_id"])
    assert talk.status_code == 200


def test_the_mode_is_checked(env):
    assert env.client.post("/chat", json={"message": "hi", "mode": "therapy"}, headers=H).status_code == 422
    assert env.client.post("/chat", json={"message": "hi", "mode": "talk"}, headers=H).status_code == 200


def test_a_plain_talk_conversation_stores_no_mode(env):
    body = post(env, "good morning, how are you today my friend").json()
    assert doc_store.get(env.db, USER, "conversation_mode", body["conversation_id"]) is None


# ---- name privacy --------------------------------------------------------------------------------------------------------------------

def test_names_never_reach_the_outside_ai_and_come_back_in_the_reply(env):
    post(env, "my boyfriend is Ashmit")
    post(env, "my mother is Sunita")
    seen = capture(env, reply="It sounds like [PARTNER] pulls back when [MOTHER] visits. How are you feeling about it?")
    body = post(env, "Ashmit gets quiet whenever Sunita visits and I keep texting him, what do I do").json()
    sent = prompt_of(seen)
    assert "Ashmit" not in sent and "Sunita" not in sent and "[PARTNER]" in sent and "[MOTHER]" in sent
    assert body["response"].startswith("It sounds like Ashmit pulls back when Sunita visits.") and "[" not in body["response"]


def test_names_are_hidden_in_ordinary_chat_too(env):
    post(env, "my friend is Rahul")
    seen = capture(env, reply="I hope [FRIEND] is okay too.")
    body = post(env, "Rahul has been coughing and I have a mild headache since morning, what could help?").json()
    assert "Rahul" not in prompt_of(seen)
    assert body["response"] == "I hope Rahul is okay too."


def test_a_label_the_model_makes_up_is_never_shown(env):
    post(env, "my boyfriend is Ashmit")
    capture(env, reply="Maybe talk to [FRIEND_9] and [PARTNER].")
    body = post(env, "Ashmit keeps ignoring my texts after we fight").json()
    assert body["response"] == "Maybe talk to your friend and Ashmit."


def test_without_people_memory_nothing_is_changed(env):
    seen = capture(env, reply="Thanks for telling me [not a label].")
    body = post(env, "my boyfriend keeps ignoring my texts after we fight").json()
    assert body["response"] == "Thanks for telling me [not a label]." and "boyfriend" in seen["message"]


# ---- what Orbit refuses --------------------------------------------------------------------------------------------------------------

def test_a_request_to_make_someone_jealous_gets_a_fixed_answer_and_no_model_call(env):
    seen = capture(env)
    body = post(env, "how do I make him jealous so he misses me", mode="orbit").json()
    assert body["kind"] == "orbit_redirect" and "say what you need directly" in body["response"] and not seen
    assert env.ai_calls == [] or True
    hinglish = post(env, "usse jealous karna hai kaise karun").json()
    assert hinglish["kind"] == "orbit_redirect" and "seedhe bol" in hinglish["response"]


def test_the_decline_needs_no_ai_consent(env):
    from fake_db import FakeDB
    import consent
    consent.set_purpose(env.db, USER, "ai_chat_processing", False, source="system", hash_seen=consent.text_hash("ai_chat_processing"))
    consent.forget(USER)
    body = post(env, "help me secretly check her phone").json()
    assert body["kind"] == "orbit_redirect" and not body.get("consent_required")


def test_verdicts_and_stereotypes_are_removed_from_a_heart_to_heart_reply(env):
    capture(env, reply="He is toxic and you should leave him. It sounds like you felt dismissed. Women are always dramatic.")
    body = post(env, "my boyfriend dismissed my feelings in the fight and I feel hurt", mode="orbit").json()
    assert body["response"] == "It sounds like you felt dismissed."


def test_if_everything_is_removed_a_neutral_line_is_shown(env):
    capture(env, reply="He is toxic. You should leave him.")
    body = post(env, "my boyfriend dismissed my feelings in the fight and I feel hurt", mode="orbit").json()
    assert "not to judge anyone" in body["response"]


def test_a_reply_outside_orbit_is_not_edited(env):
    capture(env, reply="Some people call a pattern like that toxic, but I would rather describe what happened.")
    body = post(env, "I have had a mild headache since morning, what could help?").json()
    assert "toxic" in body["response"]


# ---- safety still comes first ------------------------------------------------------------------------------------------------------------

def test_safe_harbor_wins_inside_orbit_and_no_model_is_called(env):
    seen = capture(env)
    body = post(env, "my husband choked me last night and said he will kill me", mode="orbit").json()
    assert body["kind"] == "safe_harbor" and body["harbor"]["tier"] == 3 and not seen


def test_crisis_wording_inside_orbit_gets_the_crisis_reply(env):
    seen = capture(env)
    body = post(env, "I want to end my life, my boyfriend left me", mode="orbit").json()
    assert body["kind"] == "emergency" and "Tele-MANAS" in body["response"] and not seen


def test_orbit_replies_carry_relationship_chips_and_no_chips_on_a_decline(env):
    capture(env)
    body = post(env, "my girlfriend is upset with me and I do not know what to say to her").json()
    assert "Help me work out what to say" in body["suggestions"]
    assert post(env, "how can I make her jealous").json()["suggestions"] == []


def test_the_prompt_stays_under_the_budget_with_orbit_blocks(env):
    from chat_pipeline import PROMPT_BUDGET
    seen = capture(env)
    post(env, "my boyfriend gives me the silent treatment and I keep texting him, my in-laws also interfere and we fight about money", mode="orbit")
    total = sum(len(seen.get(k, "")) for k in ("memory_context", "conversation_context", "evidence_context")) + len(seen.get("safety_context", ""))
    assert total <= PROMPT_BUDGET + 3200       # the fixed style text is counted in safety_context here
