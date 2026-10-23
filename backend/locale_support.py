"""Who can help, and where (pure data, no database and no model).

India is fully supported. Every other country, and a person who has not said where they are, gets plain words and no number:
"your local emergency number". A number is shipped only after the owner has checked it against an official source (plan Appendix B),
so no other country's number appears here on purpose.

Country and gender come from the setup (``experience.identity``). A person who never answered, which includes everyone who set up
before those questions existed, is passed as ``None``: that means India and an unknown gender, and gets the women's set: the Women Helpline serves women, and 112 is always shown beside it because the 181 line is not
run in every state (it is not run by the West Bengal government, per a Rajya Sabha reply of 11 December 2024).
"""
from __future__ import annotations

from typing import Any

#: The words used where a number cannot be given.
LOCAL_EMERGENCY = "your local emergency number"

_EMERGENCY = {"name": "Emergency services", "number": "112", "note": "Police, fire and ambulance. Free, open day and night."}
_WOMEN_HELPLINE = {"name": "Women Helpline", "number": "181", "note": "Free, open day and night. If it does not connect, call 112."}
_NCW = {"name": "NCW women helpline", "number": "14490", "note": "Free, open day and night, for women and girls 18 and over."}
_TELE_MANAS = {"name": "Tele-MANAS", "number": "14416", "note": "Free mental health support, open day and night."}
_CHILDLINE = {"name": "Childline", "number": "1098", "note": "For a child in danger. Free, open day and night."}
_TRUSTED = {"name": "A person you trust", "number": "", "note": "A friend or relative who will keep this private."}
_LOCAL = {"name": LOCAL_EMERGENCY, "number": "", "note": "Not shown as a number yet, because it has not been checked."}

_WOMAN = frozenset({"woman", "women", "female", "f", "girl", "lady"})
_MAN = frozenset({"man", "men", "male", "m", "boy", "gentleman"})
_NON_BINARY = frozenset({"non binary", "nonbinary", "nb", "enby", "genderqueer", "genderfluid", "agender"})   # "non-binary" and "non_binary" are folded to a space first
_INDIA = frozenset({"in", "ind", "india", "bharat", "भारत"})


#: One copy of the crisis wording for India. ``safety_engine.CRISIS_LINES`` is this text and must stay byte-identical (tests compare it).
_CRISIS_IN = (
    "In India, call 112 for emergency help, or Tele-MANAS, the free 24x7 mental health line, on 14416 or 1-800-891-4416. "
    "Outside India, call your local emergency number, or find a free local line at findahelpline.com."
)
_CRISIS_LOCAL = "Please call your local emergency number, or find a free local line at findahelpline.com."


def normalize_country(country: Any) -> str:
    """'IN' for India or not said, 'OTHER' for any other country."""
    text = str(country or "").strip().lower()
    return "IN" if not text or text in _INDIA else "OTHER"


def normalize_gender(gender: Any) -> str:
    """'woman', 'man', 'non-binary', or 'unknown' (which is treated like a woman: the wider set of helplines)."""
    text = str(gender or "").strip().lower().replace("-", " ").replace("_", " ")
    if text in _NON_BINARY:
        return "non-binary"
    if text in _MAN:
        return "man"
    return "woman" if text in _WOMAN else "unknown"


def resources_for(country: Any = None, gender: Any = None, child_at_risk: bool = False) -> list[dict[str, str]]:
    """The people to point to when someone is not safe at home: ``[{name, number, note}]`` (number is "" when there is none to dial).

    India, woman or gender unknown: 112, 181, 14490. India, man or non-binary: 112, Tele-MANAS 14416, a person they trust.
    A child at risk adds Childline 1098. Any other country: "your local emergency number" and nothing else."""
    if normalize_country(country) != "IN":
        return [dict(_LOCAL)]
    if normalize_gender(gender) in ("man", "non-binary"):
        out = [_EMERGENCY, _TELE_MANAS, _TRUSTED]
    else:
        out = [_EMERGENCY, _WOMEN_HELPLINE, _NCW]
    if child_at_risk:
        out = [*out[:-1], _CHILDLINE, out[-1]] if out[-1] is _TRUSTED else [*out, _CHILDLINE]
    return [dict(r) for r in out]


def self_help_resources(country: Any = None, child_at_risk: bool = False) -> list[dict[str, str]]:
    """For a person who says they hurt someone: 112 if anyone is in danger now, and Tele-MANAS for anger and stress.
    When the one hurt is a child, Childline 1098 is added (a child in danger, or a parent who wants help to stop)."""
    if normalize_country(country) != "IN":
        return [dict(_LOCAL)]
    return [dict(_EMERGENCY), dict(_TELE_MANAS), *([dict(_CHILDLINE)] if child_at_risk else [])]


def crisis_lines(country: Any = None) -> str:
    """The sentence after "reaching someone right now". India (or not said): the original wording. Any other country: no number."""
    return _CRISIS_IN if normalize_country(country) == "IN" else _CRISIS_LOCAL


def emergency_number(country: Any = None) -> str:
    """"112" for India (or not said), else "your local emergency number"."""
    return _EMERGENCY["number"] if normalize_country(country) == "IN" else LOCAL_EMERGENCY
