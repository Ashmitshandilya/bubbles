"""What a message is about, from fixed word lists (English and Hinglish): ``relationship``, ``mind``, ``body``, ``fitness``, ``cycle``, ``care``.

Pure and cheap. A tag is only a hint for which follow-up chips to offer and which blocks matter; it never decides anything about safety
(safety_engine and safe_harbor do that on their own) and it is never shown to the person or stored with the message.
"""
from __future__ import annotations

import re

#: tag -> words. Matched as whole words (or word starts for the stems ending in ``*``), case-insensitive.
_WORDS: dict[str, str] = {
    "relationship": (
        r"boyfriend|girlfriend|bf|gf|husband|wife|hubby|wifey|partner|spouse|fianc[eé]e?|dating|relationship|breakup|break up|broke up|marriage|married|"
        r"in-?laws?|mother-in-law|ex|crush|pati|patni|biwi|shaadi|shadi|rishta|saas|sasur|naraz|jhagda|jhagde|jhagra|pyaar|pyar|mohabbat|"
        r"boyfriend ka|meri gf|mera bf|meri wife|mera husband|situationship|long distance"),
    "mind": (
        r"anxious|anxiety|stress\w*|depress\w*|sad|lonely|loneliness|panic|overwhelm\w*|worried|worry|mood|crying|cry|tension|burnout|burnt out|"
        r"low|empty|numb|udaas|ghabrahat|ghabra\w*|akela|akeli|pareshan|dar lag\w*|rona|mann nahi|uneasy|irritable|angry|gussa"),
    "body": (
        r"pain|ache|aches|headache|migraine|fever|cough|cold|nausea|vomit\w*|dizzy|dizziness|rash|swelling|swollen|sore|cramp|cramps|itch\w*|bloat\w*|"
        r"acidity|constipation|diarrh\w*|dard|bukhar|khansi|chakkar|pet dard|sar dard|gala|throat|tired|fatigue|weak|weakness"),
    "fitness": (
        r"workout|gym|exercise|exercising|running|run|jogging|steps|protein|calories|calorie|weight|diet|yoga|walk|walking|cardio|strength|lifting|"
        r"gain muscle|lose weight|fat loss|bulk|cut|reps|sets|vyayam|dieting"),
    "cycle": (
        r"period|periods|cycle|pms|cramps|ovulation|ovulating|pregnan\w*|menstru\w*|mahwari|masik|spotting|late period|missed period|fertile|trying to conceive"),
    "care": (
        r"doctor|appointment|prescription|medicine|medicines|medication|medications|lab|labs|report|reports|checkup|check-up|blood test|scan|"
        r"dawai|dawa|dawaai|clinic|hospital|specialist|referral|test results"),
}
_RX = {tag: re.compile(rf"(?<![\w])(?:{words})(?![\w])", re.IGNORECASE) for tag, words in _WORDS.items()}

TAGS = tuple(_WORDS)


def tags(text: str) -> tuple[str, ...]:
    """The tags that apply, in a fixed order. An empty message has none."""
    text = str(text or "")[:2000]
    return tuple(tag for tag in TAGS if _RX[tag].search(text))
