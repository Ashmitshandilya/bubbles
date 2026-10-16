"""Mind behaviour in chat (pure): a short instruction block for the model and a fixed supportive reply for loneliness.

Facts come from ``health_semantics``; a block is produced only for the person's OWN, current / recent / recurring loneliness, anxiety,
panic, separation anxiety or low mood. Nothing here calls a model, labels a person or touches a medicine. The Mind tools it names
exist in the app (Mind > Loneliness check-in, Breathe and ground, Missing someone / apart, Anxiety check-in, Check in).
"""
from __future__ import annotations

from typing import Any, Iterable

from consent import consent_needed_reply

#: Most specific first: a panic attack is also "anxiety" (CONCEPT_PARENT), and the specific tool is the better step.
ORDER = ("panic_attack", "separation_anxiety", "loneliness", "anxiety", "low_mood")

#: concept -> (what the model may say it noticed, the one small step, the Mind tool to name)
TOPICS: dict[str, tuple[str, str, str]] = {
    "panic_attack": ("panic", "slow breathing with a longer breath out", "Breathe and ground in the Mind section"),
    "separation_anxiety": ("missing someone or being apart", "a small ritual for the time apart, like a voice note or a set time to talk", "Missing someone / apart in the Mind section"),
    "loneliness": ("feeling lonely", "one low-pressure reach-out, like a short message to one person", "Loneliness check-in in the Mind section"),
    "anxiety": ("feeling anxious", "a few slow breaths with the breath out longer than the breath in", "Anxiety check-in in the Mind section"),
    "low_mood": ("a low mood", "one small kind thing for today, like a short walk or a glass of water", "Check in in the Mind section"),
}


def mind_topics(facts: Iterable[Any]) -> list[str]:
    """Mind concepts the person reports about themselves right now, most pressing first (accepts a turn or its facts)."""
    facts = getattr(facts, "facts", facts) or ()
    active = {f.concept for f in facts if f.active}
    return [c for c in ORDER if c in active]


def mind_concept(turn: Any) -> str | None:
    """The most specific Mind concept the person reports about themselves right now, or None."""
    return next(iter(mind_topics(turn)), None)


def mind_support_block(turn: Any) -> str:
    """Appended to the safety context. Empty when the turn is not about one of these."""
    concept = mind_concept(turn)
    if not concept:
        return ""
    noticed, step, tool = TOPICS[concept]
    return (
        "MIND SUPPORT (the person mentioned " + noticed + "):\n"
        "- Reply like a close friend: one warm line that shows you heard them, then one small step, then at most one question.\n"
        f"- The small step: {step}. Name this tool in the app: {tool}.\n"
        "- Never name or label a condition (no 'you have an anxiety disorder'). Never name a condition as theirs, never say it is nothing, never promise it will pass.\n"
        "- No medicine or supplement advice. If they mention not coping or feeling unsafe, stay gentle and point to a person they trust.")


LONELY_REPLY = (
    "I'm really glad you said that{name}. Feeling lonely is more common than people admit, and it doesn't mean something is wrong with you. "
    "One small thing that often helps is a short message to one person you like. "
    "The Loneliness check-in in the Mind section is there whenever you want it.")


def loneliness_no_consent_reply(turn: Any, name: str | None = None) -> str | None:
    """Loneliness is answerable without the AI yes: a fixed supportive reply, then the usual ask (the consent card shows with it)."""
    if mind_concept(turn) != "loneliness":
        return None
    return LONELY_REPLY.format(name=f", {name}" if name else "") + "\n\n" + consent_needed_reply(name)


def mind_fixed_reply(facts: Iterable[Any]) -> str:
    """A short fixed supportive reply for when no outside AI may be asked, or "" when no Mind topic applies."""
    concept = mind_concept(facts)
    if not concept:
        return ""
    noticed, step, tool = TOPICS[concept]
    return f"Thank you for telling me about {noticed}. One small step that often helps: {step}. You'll find it under {tool}."
