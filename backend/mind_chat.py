"""How the companion behaves when someone says they are lonely, anxious, panicking, missing someone or low.

Pure and deterministic: it reads the facts the language layer already extracted, never the raw message. Nothing here labels a person
("you have an anxiety disorder"), gives medicine advice or diagnoses. The wording is kept short and friendly."""
from __future__ import annotations

from typing import Any, Iterable

#: concept -> (what the friend says first, the small step that names a real Mind tool)
TOPICS: dict[str, tuple[str, str]] = {
    "loneliness": ("That sounds lonely, and I'm glad you said it.",
                   "One small thing: send a short hello to one person you like, or write it down in your Mind journal."),
    "panic_attack": ("That sounds really frightening. You're not in trouble, and it will pass.",
                     "Try the slow-breathing exercise in Mind: in for 4, out for 6, a few rounds."),
    "separation_anxiety": ("Missing someone or being apart can feel heavy.",
                           "A short call or voice note can help. Mind also has a grounding exercise for the waiting part."),
    "anxiety": ("That sounds like a lot to carry right now.",
                "A one-minute breathing or grounding exercise in Mind can ease it a little."),
    "low_mood": ("I'm sorry it's feeling heavy.",
                 "A tiny step may help: water, a short walk, or a note in your Mind journal."),
}
_ORDER = ("panic_attack", "separation_anxiety", "loneliness", "anxiety", "low_mood")


def mind_topics(facts: Iterable[Any]) -> list[str]:
    """Mind concepts the person says apply to themselves now or lately, most pressing first."""
    found = {getattr(f, "concept", None) for f in facts
             if getattr(f, "experiencer", "self") == "self" and getattr(f, "assertion", "present") == "present"
             and getattr(f, "temporal", "current") in ("current", "recurring", "recent")}
    return [c for c in _ORDER if c in found]


def mind_support_block(facts: Iterable[Any]) -> str:
    """Extra guidance for the model, or "" when no Mind topic applies. Style only; safety rules always come first."""
    topics = mind_topics(facts)
    if not topics:
        return ""
    names = ", ".join(t.replace("_", " ") for t in topics[:2])
    return (
        f"MIND SUPPORT (the person mentioned {names}; style rules, safety rules above still win):\n"
        "- Reply like a kind friend, in two to four short sentences.\n"
        "- One line of acknowledgement first. Do not hurry to fix.\n"
        "- Offer exactly one small step and name the Bubbles Mind tool that fits (breathing, grounding, journal, check-in).\n"
        "- Ask one gentle question at the end.\n"
        "- Never name a condition or say they have one. No medicine or supplement advice. Do not diagnose.\n"
        "- If they seem to be in danger or say they might hurt themselves, the safety reply is used instead."
    )


def mind_fixed_reply(facts: Iterable[Any]) -> str:
    """A short fixed supportive reply used when no outside AI may be asked, or "" when no Mind topic applies."""
    topics = mind_topics(facts)
    if not topics:
        return ""
    ack, step = TOPICS[topics[0]]
    return f"{ack} {step}"
