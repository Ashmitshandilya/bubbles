import pytest

import chat_pipeline as cp
from safety_engine import assess_safety


def test_red_chest_pain():
    result = assess_safety("I have chest pain and trouble breathing")
    assert result.level == "RED"
    assert "chest pain or pressure" in result.reasons
    assert "breathing difficulty" in result.reasons


def test_amber_severe_pain():
    result = assess_safety("This is severe headache")
    assert result.level == "AMBER"


def test_green_normal_wellness():
    result = assess_safety("I slept 7 hours")
    assert result.level == "GREEN"


# ---- crisis replies name India's lines first (112, Tele-MANAS 14416), never the US-only 988


def _india_first(reply: str) -> None:
    assert "112" in reply and "14416" in reply and "1-800-891-4416" in reply and "findahelpline.com" in reply, reply
    assert "988" not in reply and "\u2014" not in reply, reply
    assert reply.index("112") < reply.index("14416") < reply.index("Outside India"), reply


@pytest.mark.parametrize("text", ["I want to kill myself", "I want to end my life", "mujhe marna hai", "khud ko khatam kar lunga"])
def test_crisis_reply_names_india_lines(text):
    turn = cp.analyze_turn(text, [])
    assert turn.route == "emergency" and turn.safety.crisis, text
    _india_first(cp.deterministic_reply(turn, name=None, saved_events=0))


def test_crisis_clarification_names_india_lines():
    turn = cp.analyze_turn("I wanted to kill myself earlier today but I am okay now", [])
    assert turn.route == "clarification" and turn.safety.crisis
    _india_first(cp.deterministic_reply(turn, name=None, saved_events=0))


def test_small_talk_after_a_crisis_reply_names_india_lines():
    crisis = cp.analyze_turn("mujhe marna hai", [])
    history = [{"role": "user", "content": "..."},
               {"role": "bubbles", "content": "...", "metadata": {"kind": "emergency", "safety": {
                   "state": crisis.safety.state, "concepts": list(crisis.safety.concepts), "retracted": False}}}]
    turn = cp.analyze_turn("ok", history)
    assert turn.route == "safety_followup"
    _india_first(cp.deterministic_reply(turn, name="Asha", saved_events=0))
