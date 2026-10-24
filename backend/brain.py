"""Bubbles' own brain: decides when it can answer a message itself, and does.

``decide`` (pure) looks at a message that safety triage rated clear and returns the kind of local answer, or None to leave it to the model. ``respond``
builds the reply from the person's own data, a reviewed knowledge card, or the friend voice, in the person's own tone and length. The order of the
routes in chat_pipeline never changes: every safety route comes first and only a message with no safety concern ever reaches this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import companion_voice
import data_answers
import knowledge_cards
import safe_harbor

ROUTES = ("own_data", "knowledge", "companion")
DEFAULT_STYLE = {"tone": "gentle_warm", "length": "balanced", "language": "en"}


def decide(text: str, concepts: Iterable[str], *, mode: str = "talk", harbor_tier: int = 0, about_other: bool = False, relationship: bool = False) -> dict[str, Any] | None:
    """``{"route", "intent", "key", "detail"}`` or None. ``concepts`` are the symptom and feeling concepts found in the message (any assertion)."""
    if mode != "talk" or harbor_tier > 0 or about_other:
        return None
    language = safe_harbor.detect_language(text)
    if language == "hi":
        return None   # no reviewed Devanagari text yet: the model handles it, as before
    concepts = set(concepts)
    if not concepts:
        d = data_answers.detect(text)
        if d:
            intent = f"{d['topic']}.{d['kind']}"
            return {"route": "own_data", "intent": intent, "key": f"own_data:{intent}", "detail": d}
    card = knowledge_cards.match(text, concepts)
    if card:
        return {"route": "knowledge", "intent": card["id"], "key": f"knowledge:{card['id']}", "detail": {"card": card["id"]}}
    if not relationship:
        feeling = companion_voice.concept_of(text, concepts)
        if feeling:
            return {"route": "companion", "intent": feeling, "key": f"companion:{feeling}", "detail": {"concept": feeling}}
    return None


def style_for(db: Any, uid: str, now: datetime | None = None) -> dict[str, str]:
    """The person's own tone and reply length from the Person Model, when it is sure; the defaults otherwise. Never raises."""
    out = dict(DEFAULT_STYLE)
    try:
        import person_model as pm
        now = now or datetime.now(timezone.utc)
        model = pm.load(db, uid)
        for trait, field in (("tone", "tone"), ("reply_length", "length")):
            reading = pm.resolve(trait, model["traits"].get(trait), now)
            if reading and reading["used"] and reading["values"]:
                out[field] = reading["values"][0]
    except Exception:  # noqa: BLE001 - style is a nicety
        pass
    return out


def respond(db: Any, uid: str, brain: dict[str, Any], text: str, *, name: str | None = None) -> str:
    """The reply for a decided local route. Never raises: a failure here falls back to a calm line, never to a made-up answer."""
    try:
        language = "hi-latn" if safe_harbor.detect_language(text) == "hi-latn" else "en"
        style = style_for(db, uid)
        if brain["route"] == "own_data":
            import association_loader
            topic = brain["detail"]["topic"]
            series, today = association_loader.load_some(db, uid, {data_answers.TOPICS[topic]["series"]})
            return data_answers.answer(brain["detail"], series, today, name=name, language=language, seed=text)
        if brain["route"] == "knowledge":
            card = next(c for c in knowledge_cards.cards() if c["id"] == brain["detail"]["card"])
            return knowledge_cards.reply(card, name=name, language=language, length=style["length"], seed=text)
        return companion_voice.reply(brain["detail"]["concept"], name=name, language=language, tone=style["tone"], length=style["length"], seed=text)
    except Exception:  # noqa: BLE001
        from logging_util import logger
        logger.warning(component="BRAIN", operation="respond", error=None, user_id=uid, fallback_action="calm_line")
        return "I couldn't pull that up just now. Ask me again in a moment?"
