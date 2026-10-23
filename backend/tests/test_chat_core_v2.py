"""Phase 1 through the real /chat route: person model in the prompt, open threads once, chips on every reply, country in the crisis text."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import doc_store
import open_threads
import person_model
from test_chat_http_flow import H, USER, env, send  # noqa: F401  (env is a fixture)

AI_MESSAGE = "I have had a mild headache since morning, what could help?"
NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def clean():
    person_model.forget(USER)
    import chat_cache
    chat_cache.forget_user(USER)
    yield
    person_model.forget(USER)
    chat_cache.forget_user(USER)


def spy(env):
    seen: dict = {}
    original = env.main.ask_bubbles

    def wrapper(message, **kw):
        seen.update(kw)
        return original(message, **kw)
    env.main.ask_bubbles = wrapper
    return seen


def test_the_person_model_reaches_the_prompt_and_nothing_else_about_it_does(env):
    person_model.observe_setup(env.db, USER, {"reply_length": "short", "tone": "calm_direct"})
    seen = spy(env)
    assert send(env, AI_MESSAGE).status_code == 200
    assert "PERSON MODEL (how this person tends to be; use quietly, never recite):" in seen["memory_context"]
    assert "prefers short replies" in seen["memory_context"] and "calm and direct" in seen["memory_context"]


def test_a_person_with_no_model_gets_no_block(env):
    seen = spy(env)
    send(env, AI_MESSAGE)
    assert "PERSON MODEL" not in seen["memory_context"]


def test_a_rejected_trait_never_reaches_the_prompt(env):
    person_model.observe_setup(env.db, USER, {"reply_length": "short"})
    model = person_model.load(env.db, USER, fresh=True)
    person_model.reject(model, "reply_length")
    person_model.save(env.db, USER, model)
    seen = spy(env)
    send(env, AI_MESSAGE)
    assert "short replies" not in seen["memory_context"]


def test_an_open_thread_is_offered_at_the_start_of_a_conversation_once(env):
    open_threads.observe(env.db, USER, [type("F", (), dict(concept="headache", experiencer="self", assertion="present", temporal="current", severity=6, tier=None))()],
                         "NO_REDFLAG", NOW)
    seen = spy(env)
    first = send(env, "good morning, how are you today my friend")
    assert first.status_code == 200
    conv = first.json()["conversation_id"]
    send(env, AI_MESSAGE, conv=conv)
    assert "OPEN THREADS" not in seen.get("memory_context", ""), "only when the conversation starts"
    seen.clear()
    # a new conversation a moment later: the same thread was just asked about, so it waits a day
    send(env, "hello again, what do you think about sleep routines")
    assert "OPEN THREADS" not in seen.get("memory_context", "")


def test_the_open_thread_text_is_in_the_prompt_the_first_time(env):
    open_threads.observe(env.db, USER, [type("F", (), dict(concept="headache", experiencer="self", assertion="present", temporal="current", severity=6, tier=None))()],
                         "NO_REDFLAG", NOW)
    seen = spy(env)
    send(env, "I am wondering whether my sleep routine matters for how I feel")
    assert "OPEN THREADS" in seen["memory_context"] and "headache" in seen["memory_context"]
    stored = doc_store.get(env.db, USER, open_threads.KIND, "headache")
    assert stored.get("asked_at"), "marked as asked after it was offered"


def test_every_calm_reply_carries_up_to_three_chips_and_a_retry_replays_them(env):
    body = send(env, AI_MESSAGE, mid="11111111-1111-4111-8111-111111111111").json()
    assert 1 <= len(body["suggestions"]) <= 3 and all(isinstance(s, str) for s in body["suggestions"])
    again = send(env, AI_MESSAGE, conv=body["conversation_id"], mid="11111111-1111-4111-8111-111111111111").json()
    assert again.get("replayed") and again["suggestions"] == body["suggestions"]


def test_a_relationship_message_gets_relationship_chips(env):
    body = send(env, "my girlfriend is upset with me and I do not know what to say to her").json()
    assert "Help me work out what to say" in body["suggestions"]


def test_safety_replies_carry_an_empty_list(env):
    body = send(env, "I have crushing chest pain and cannot breathe right now").json()
    assert body["kind"] == "emergency" and body["suggestions"] == []


def test_the_budget_holds_on_a_big_context(env):
    from chat_pipeline import PROMPT_BUDGET
    seen = spy(env)
    big = ("I told you a lot about my life. " * 40)
    for _ in range(3):
        send(env, "my sleep has been poor and I feel tired every day " + big[:200])
    send(env, AI_MESSAGE)
    total = sum(len(seen.get(k, "")) for k in ("memory_context", "conversation_context", "evidence_context"))
    assert total <= PROMPT_BUDGET + 200


def test_the_crisis_text_follows_the_country_from_the_setup(env):
    text = "I want to end my life tonight"
    india = send(env, text).json()["response"]
    assert "Tele-MANAS" in india and "112" in india
    doc_store.put(env.db, USER, "experience", "main", {"identity": {"country": "other", "gender": None}})
    import chat_cache
    chat_cache.forget_user(USER)
    elsewhere = send(env, text).json()["response"]
    assert "your local emergency number" in elsewhere and "Tele-MANAS" not in elsewhere and "112" not in elsewhere


def test_an_existing_user_with_no_identity_still_gets_the_india_text(env):
    doc_store.put(env.db, USER, "experience", "main", {"version": "2026-10b", "companion": {"tone": "gentle_warm"}})
    body = send(env, "I want to end my life tonight").json()
    assert "Tele-MANAS" in body["response"]
