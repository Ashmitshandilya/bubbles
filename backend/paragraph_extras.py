"""What a long message holds that the symptom and daily-log engines do not read: injuries, and a conflict with someone close.

Pure. An injury ("twisted my ankle playing football", "my knee is swollen after I fell") becomes a symptom-type event that is always ASKED about, never
saved on its own (it needs a person's care, so Bubbles checks once and says when to get it looked at). A conflict with a partner ("had a big fight with my
boyfriend") is not stored as a health fact; it only marks the day as a tension day for the person's own patterns (sleep after a hard day), the same marker
Orbit's "After a fight" tool writes. Nothing here diagnoses or predicts.
"""
from __future__ import annotations

import re
from typing import Any

PARTS = ("ankle", "knee", "wrist", "elbow", "shoulder", "neck", "back", "hip", "foot", "toe", "finger", "thumb", "hand", "leg", "arm", "head", "ribs", "rib", "jaw",
         "calf", "thigh", "heel", "shin", "forehead", "chin", "lip", "nose", "eye", "tooth", "teeth", "palm", "knuckle", "groin", "hamstring", "quad")
_VERBS = r"twisted|sprained|strained|pulled|hurt|injured|fractured|broke|banged|bumped|bruised|cut|burned|burnt|jammed|dislocated|scraped|tore|torn"
_PART_RE = "|".join(sorted(PARTS, key=len, reverse=True))
_SIDE = r"(?:left\s+|right\s+)?"
_DID = re.compile(rf"\b(?:{_VERBS})\s+(?:my|the)\s+{_SIDE}({_PART_RE})\b", re.I)
_STATE = re.compile(rf"\b(?:my\s+)?{_SIDE}({_PART_RE})\s+(?:is|was|got|feels?|looks?)\s+(?:\w+\s+)?(swollen|bruised|sore|fractured|sprained|twisted)\b", re.I)
_FELL = re.compile(r"\b(?:i\s+)?(?:fell|slipped|tripped)\s+(?:down|off|over|on|from|while)\b", re.I)
_SWOLLEN = re.compile(r"\bswol+en|swelling\b|\bpuffed\s+up\b", re.I)
_PARTNER = r"(?:boyfriend|girlfriend|husband|wife|partner|bf|gf|fianc\w+|spouse|my\s+ex)"
_FIGHT = r"(?:fight|fought|argu(?:ed|ment|ing)|quarrel\w*|big\s+fight|blow-?up|had\s+words|not\s+talking|stopped\s+talking|silent\s+treatment)"
_CONFLICT = re.compile(rf"\b{_FIGHT}\b[^.!?\n]{{0,50}}\b{_PARTNER}\b|\b{_PARTNER}\b[^.!?\n]{{0,50}}\b{_FIGHT}\b", re.I)
# anything that is about being hurt by the other person is Safe Harbor's, not a "tension day"
_HARM = re.compile(r"\b(?:hit|hits|hitting|slap\w*|punch\w*|kick\w*|beat\w*|choke\w*|threat\w*|force\w*|afraid|scared\s+of|abus\w*)\b", re.I)


def injuries(text: str) -> list[dict[str, Any]]:
    """The injuries the person says they have (one per body part): ``{"part", "what", "swollen"}``. Past stories with no part named are not read."""
    t = str(text or "")
    found: dict[str, dict[str, Any]] = {}
    for m in _DID.finditer(t):
        part = m.group(1).lower()
        verb = re.match(r"\w+", m.group(0)).group(0).lower()
        found.setdefault(part, {"part": part, "what": verb, "swollen": False})
    for m in _STATE.finditer(t):
        part, state = m.group(1).lower(), m.group(2).lower()
        entry = found.setdefault(part, {"part": part, "what": state, "swollen": False})
        if state == "swollen":
            entry["swollen"] = True
    if found and _SWOLLEN.search(t):
        for entry in found.values():
            entry["swollen"] = True
    return list(found.values())


def fell(text: str) -> bool:
    return bool(_FELL.search(str(text or "")))


def injury_event(info: dict[str, Any]) -> dict[str, Any]:
    """The data of one symptom-type event for an injury. The name stays plain ("ankle injury"); how it happened is kept as a detail."""
    part = info["part"]
    words = {"twisted": "twisted", "sprained": "sprained", "strained": "strained", "pulled": "pulled", "broke": "possibly broken", "fractured": "possibly broken",
             "tore": "torn", "torn": "torn"}.get(info["what"], info["what"])
    details = words + (", swollen" if info.get("swollen") else "")
    return {"symptom": f"{part} injury", "name": f"{part} injury", "details": details, "injury": True, "body_part": part}


def conflict_with_partner(text: str) -> bool:
    """True when the person says they had a fight or argument with a partner, and nothing about being hurt or afraid of them."""
    t = str(text or "")
    return bool(_CONFLICT.search(t)) and not _HARM.search(t)


GUIDANCE = ("Injuries can need a proper look. If it's very swollen, you can't put weight on it or move it, it looks out of shape, or you feel numbness or "
            "severe pain, please get it checked today.")
