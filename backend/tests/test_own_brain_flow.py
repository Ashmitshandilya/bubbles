"""Bubbles' own brain through the real chat route: answered with no model call, from the person's own data, stored with what kind of answer it was,
never ahead of a safety route, and handed back to the model for a person it keeps missing for."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from test_chat_http_flow import H, USER, env, send  # noqa: F401  (stateful app, fake database, stub model)


def _sleep(env, hours_by_days_ago: dict[int, float]):
    today = date.today()
    for ago, hours in hours_by_days_ago.items():
        env.db.table("sleep_logs").insert({"user_id": USER, "sleep_date": (today - timedelta(days=ago)).isoformat(), "duration_minutes": int(hours * 60), "sleep_quality": 6}).execute()


def _reply(res) -> str:
    assert res.status_code == 200, res.text
    return res.json()["response"] if "response" in res.json() else res.json().get("reply", "")


def test_a_question_about_the_persons_own_sleep_is_answered_from_their_logs_with_no_model(env):
    _sleep(env, {1: 7.0, 2: 6.0, 3: 5.0, 4: 8.0})
    res = send(env, "how has my sleep been this week?")
    text = _reply(res)
    assert "4 nights" in text and "6 h 30 min" in text, text
    assert env.ai_calls == []
    stored = env.db.rows("chat_messages", role="bubbles")[-1]
    assert stored["metadata"]["brain"]["key"] == "own_data:sleep.summary"


def test_nothing_logged_is_said_plainly_and_still_needs_no_model(env):
    text = _reply(send(env, "how did I sleep last night?"))
    assert "don't see" in text.lower() or "don't have" in text.lower()
    assert env.ai_calls == []


def test_a_self_care_question_gets_a_reviewed_card_and_no_model(env):
    text = _reply(send(env, "how can I fall asleep faster?"))
    assert "- " in text and "clinician" in text
    assert env.ai_calls == []
    assert env.db.rows("chat_messages", role="bubbles")[-1]["metadata"]["brain"]["key"] == "knowledge:sleep_cant_sleep"


def test_a_feeling_gets_the_friend_voice_and_no_model(env):
    text = _reply(send(env, "I feel so alone today"))
    assert text.rstrip().endswith("?")
    assert env.ai_calls == []
    assert env.db.rows("chat_messages", role="bubbles")[-1]["metadata"]["brain"]["key"] == "companion:loneliness"


def test_it_works_without_the_yes_to_an_outside_model(env):
    import consent
    consent.set_purpose(env.db, USER, "ai_chat_processing", False)
    consent.forget(USER)
    res = send(env, "how can I fall asleep faster?")
    assert res.status_code == 200 and "consent" not in str(res.json().get("kind", "")).lower()
    assert "- " in _reply(res) and env.ai_calls == []


def test_a_crisis_is_never_answered_by_the_friend_voice(env):
    text = _reply(send(env, "I feel so alone and I want to end my life"))
    assert "112" in text or "Tele-MANAS" in text or "14416" in text or "988" in text or "help" in text.lower()
    assert env.db.rows("chat_messages", role="bubbles")[-1]["metadata"].get("brain") is None


def test_a_symptom_with_a_red_flag_is_left_to_safety_not_a_card(env):
    res = send(env, "tips for headache relief, it's the worst of my life and sudden")
    assert env.db.rows("chat_messages", role="bubbles")[-1]["metadata"].get("brain") is None


def test_open_ended_and_why_questions_still_go_to_the_model(env):
    for q in ("why am I so tired lately?", "what do you think about my week?", "can you explain how sleep works in detail"):
        send(env, q)
    assert len(env.ai_calls) == 3


def test_a_kind_that_keeps_missing_for_a_person_is_handed_to_the_model(env):
    import brain_stats
    for _ in range(2):
        assert brain_stats.record(env.db, USER, "companion:loneliness", "down")
    text = _reply(send(env, "I feel so alone today"))
    assert len(env.ai_calls) == 1, "after two thumbs down the model answers this kind for this person"
    # another kind is untouched
    send(env, "how can I fall asleep faster?")
    assert len(env.ai_calls) == 1


def test_a_thumbs_on_a_local_answer_is_counted(env):
    import brain_stats
    send(env, "how can I fall asleep faster?")
    mid = env.db.rows("chat_messages", role="bubbles")[-1]["id"]
    r = env.client.post("/chat/feedback", json={"message_id": mid, "rating": "down", "reason": "unclear"}, headers=H)
    assert r.status_code == 201
    assert brain_stats.summary(env.db, USER)["knowledge:sleep_cant_sleep"] == {"up": 0, "down": 1}


def test_the_reply_is_stable_when_the_same_message_is_retried(env):
    mid = "11111111-1111-4111-8111-111111111111"
    first = send(env, "I feel so alone today", mid=mid)
    conv = first.json()["conversation_id"]
    again = send(env, "I feel so alone today", mid=mid, conv=conv)
    assert again.status_code == 200 and _reply(first) == _reply(again)


def test_the_model_is_handed_the_numbers_bubbles_already_worked_out(env):
    from bubbles_ai import BubblesAIResponse
    seen = []

    def spy(message, **kw):
        seen.append(kw)
        return BubblesAIResponse(response="That sounds draining. Your sleep has been short lately.", sentiment="neutral", health_events=[])

    env.main.ask_bubbles = spy
    _sleep(env, {1: 5.0, 2: 5.5, 3: 6.0, 4: 5.0})
    send(env, "why am I so tired lately?")
    assert seen, "this still needs the model"
    context = seen[0]["memory_context"]
    assert "WHAT BUBBLES ALREADY KNOWS" in context and "- sleep: last night 5 h" in context
    assert "- water: nothing logged in the last 14 days" in context   # a gap is marked as one, never filled in
