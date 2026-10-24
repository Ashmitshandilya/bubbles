"""Self-care knowledge answered by Bubbles itself: reviewed cards for common, low-risk lifestyle and comfort questions (data/knowledge_cards.json).

Pure. A card answers only when the message clearly asks for it, carries nothing that needs care (no doses or medicines, no severe or long-lasting
symptoms, no pregnancy, babies or injuries) and does not match two different topics equally. Anything else is left to the model with consent, as before.
Every card says when to see a clinician; none gives a dose or a diagnosis. The cards await clinician sign-off (docs/clinical packet).
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

CARDS_FILE = Path(__file__).with_name("data") / "knowledge_cards.json"

#: symptoms that may be present in the message and still be answered with comfort care (the card's own concepts are added to these)
COMFORT_CONCEPTS = frozenset({"headache", "cramps", "period", "back_pain", "muscle_pain", "bloating", "constipation", "cough", "sore_throat", "eye_strain",
                              "dry_eyes", "fatigue", "insomnia", "nausea", "anxiety", "loneliness", "low_mood", "separation_anxiety"})

_ASKS = re.compile(r"\?|\b(?:how|what|which|ways?\s+to|tips?|ideas?|help|helps|remedy|remedies|relief|relieve|ease|advice|suggest\w*|should|can i|kaise|kya|batao|bata do|karu|karun|best way)\b", re.I)
# anything that needs a clinician or a pharmacist, or a person who needs particular care, is not answered from a card
_NEEDS_CARE = re.compile(
    r"\b(?:mg|ml|tablets?|pills?|dose|doses|dosage|capsules?|syrup|injection|antibiotics?|painkillers?|paracetamol|ibuprofen|aspirin|crocin|dolo|combiflam|medicine|medication|"
    r"prescri\w+|insulin|steroids?|supplements?|vitamin\s+[a-z]\s+tablets?|"
    r"severe|unbearable|worst|sudden(?:ly)?|excruciating|emergency|bleeding|blood|faint\w*|chest|breath\w*|seizure|stroke|numb\w*|"
    r"for\s+(?:weeks|months|years|days)|since\s+(?:weeks|months|days|last\s+(?:week|month))|every\s+day|all\s+the\s+time|getting\s+worse|"
    r"pregnan\w+|trimester|baby|infant|newborn|toddler|child|kids?|elderly|diabet\w+|cancer|tumou?r|lump|hiv|surgery|injur\w+|fracture|broken|"
    r"heart|disease|hypertension|blood\s+pressure|bp|asthma|thyroid|kidney|liver|epilep\w+|copd|arthritis|anemi\w+|anaemi\w+|disorder|har\s+din|roz|lagatar|"
    r"which\s+(?:vitamins?|supplements?)|should\s+i\s+take|do\s+something\s+(?:stupid|drastic|crazy|rash)|"
    r"suicid\w+|self[- ]harm|kill|die|dying|hopeless|worthless)\b", re.I)
# a question about someone else ("my sister cannot sleep what should she do") is not answered from a card written for the person themselves
_OTHER_PERSON = re.compile(r"\b(?:my\s+(?:mother|mom|mum|father|dad|friend|brother|sister|husband|wife|boyfriend|girlfriend|partner|son|daughter|boss|colleague)|he|she|they|his|her|their)\b", re.I)
# a question tied to the person's own days ("how many glasses of water today") is about their data, not a general card
_ABOUT_THEIR_DAYS = re.compile(r"\b(?:today|yesterday|last\s+night|this\s+(?:week|month)|last\s+(?:week|month)|aaj|kal\s+raat|is\s+hafte|pichle\s+hafte)\b", re.I)


def _norm(text: str) -> str:
    t = str(text or "").lower().replace("’", "'")
    t = re.sub(r"can't", "cant", t)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9'\- ]+", " ", t)).strip()


@lru_cache(maxsize=1)
def cards() -> tuple[dict[str, Any], ...]:
    data = json.loads(CARDS_FILE.read_text(encoding="utf8"))
    out = []
    for c in data["cards"]:
        triggers = tuple(sorted({_norm(t) for t in c["triggers"]}, key=len, reverse=True))
        out.append({**c, "_triggers": triggers})
    return tuple(out)


def _score(text: str, card: dict[str, Any]) -> int:
    padded = f" {text} "
    best = 0
    for trigger in card["_triggers"]:
        if f" {trigger} " in padded:
            best = max(best, len(trigger.split()))
    return best


def match(text: str, active_concepts: Iterable[str] = ()) -> dict[str, Any] | None:
    """The one card that answers this message, or None (leave it to the model)."""
    t = _norm(text)
    if not t or len(t) > 200 or _NEEDS_CARE.search(t) or _OTHER_PERSON.search(t) or _ABOUT_THEIR_DAYS.search(t):
        return None
    scored = sorted(((_score(t, c), c) for c in cards()), key=lambda sc: -sc[0])
    top_score, top = scored[0]
    if top_score < 2:
        return None
    if len(scored) > 1 and scored[1][0] >= 2 and scored[1][1]["id"] != top["id"]:
        return None   # the message asks about two topics at once: do not pick one for the person
    concepts = {c for c in active_concepts}
    if not (_ASKS.search(text or "") or concepts & set(top.get("concepts", []))):
        return None   # a statement, not a question, and no matching symptom: not a request for guidance
    if concepts - COMFORT_CONCEPTS - set(top.get("concepts", [])):
        return None   # the message also reports something that is not comfort care
    return top


def _pick(seed: str, options: tuple[str, ...]) -> str:
    return options[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


OPENERS_EN = ("Happy to help with that.", "Good question, here's what usually helps.", "Sure, here's the gist.", "Let's make this easier.")
OPENERS_HI = ("Chalo, ye kaam aayega.", "Zaroor, ye dekho.", "Theek hai, seedhi baat ye hai.")


def reply(card: dict[str, Any], *, name: str | None = None, language: str = "en", length: str = "balanced", seed: str = "") -> str:
    """The card as a friendly message. ``length`` ("short", "balanced", "detailed") is the person's own preference from the Person Model."""
    seed = seed or card["id"]
    hi = language == "hi-latn"
    opener = _pick(seed, OPENERS_HI if hi else OPENERS_EN)
    if name:
        opener = f"{name}, {opener[0].lower()}{opener[1:]}"
    tips = card.get("tips", [])
    tips = tips[:3] if length == "short" else tips
    parts = [f"{opener} {card['answer']}"]
    if tips:
        parts.append("\n".join(f"- {t}" for t in tips))
    if card.get("clinician"):
        parts.append(card["clinician"])
    else:
        parts.append("This is general guidance, not a diagnosis.")
    if card.get("followup") and length != "short":
        parts.append(card["followup"])
    return "\n\n".join(parts)
