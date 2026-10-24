"""What Bubbles saves on its own and what it asks about first (pure).

"auto": the person stated it plainly in their own words and Bubbles read it with a fixed rule (sleep hours, water, a walk, weight, a mood, a meal, a
normal reading). It is saved to their logs straight away and shown as saved, so a long message about their day does not become a list of buttons.
"ask": anything that needs a person's care or could change what is recorded about their health (a symptom, a fever, an injury, a medicine, a period,
a reading outside the usual range), anything the model proposed (never saved unseen), and anything Bubbles is not sure of. Asked once, with Save and Skip.
Both only ever happen for a person who agreed to save details noticed in chat.
"""
from __future__ import annotations

from typing import Any

AUTO_TYPES = frozenset({"sleep", "hydration", "activity", "exercise", "weight", "mood", "stress", "food", "lifestyle", "wellness_checkin"})
SURE = 0.8   # a fixed rule reads it with at least this confidence

# a reading in this range is a routine log; outside it Bubbles asks first
_NORMAL = {"temperature": (35.5, 37.7), "heart rate": (50, 110), "systolic": (91, 139), "diastolic": (61, 89), "spo2": (95, 100)}


def _extractor(event: dict[str, Any]) -> str:
    data = event.get("extracted_data") or {}
    prov = data.get("_prov") or event.get("provenance") or {}
    return str(prov.get("extractor") or "")


def decide(event: dict[str, Any]) -> tuple[str, str]:
    """("auto" | "ask", why). ``event`` is a rule-built event or a saved one: ``{event_type, extracted_data, confidence}``."""
    etype = str(event.get("event_type") or "")
    data = event.get("extracted_data") or {}
    try:
        confidence = float(event.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if _extractor(event) != "rules":
        return "ask", "proposed by the model, so it is checked with you first"
    if data.get("injury"):
        return "ask", "an injury"
    if etype == "vital_sign":
        name = str(data.get("name") or "").lower()
        low_high = _NORMAL.get(name)
        try:
            value = float(data.get("value"))
        except (TypeError, ValueError):
            return "ask", "an unclear reading"
        if low_high is None or not (low_high[0] <= value <= low_high[1]):
            return "ask", "a reading outside the usual range" if low_high else "a reading Bubbles does not know the usual range for"
        return "auto", "a routine reading"
    if etype not in AUTO_TYPES:
        return "ask", {"symptom": "a symptom", "menstrual_symptom": "your cycle", "medication": "a medicine", "supplement": "a supplement"}.get(etype, "something that needs your OK")
    if confidence < SURE:
        return "ask", "Bubbles is not sure it read this right"
    if etype == "mood" and not (data.get("name") or data.get("score")):
        return "ask", "an unclear mood"
    return "auto", "stated plainly"


def split(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(saved on their own, asked about), in the order they came."""
    auto, ask = [], []
    for e in events:
        (auto if decide(e)[0] == "auto" else ask).append(e)
    return auto, ask


_LABEL = {"sleep": "sleep", "hydration": "water", "activity": "your activity", "exercise": "your exercise", "weight": "your weight", "mood": "your mood",
          "stress": "your stress", "food": "your meals", "lifestyle": "a few daily habits", "wellness_checkin": "what you don't have", "vital_sign": "a reading"}
_ASK_LABEL = {"symptom": "a symptom", "menstrual_symptom": "your period", "medication": "a medicine", "supplement": "a supplement"}


def labels(events: list[dict[str, Any]], *, asking: bool = False) -> list[str]:
    """Short plain words for a list of events, each once, in order: "sleep", "water", "your meals". Used to tell the person what was saved or is waiting."""
    out: list[str] = []
    for e in events:
        data = e.get("extracted_data") or {}
        if asking:
            if data.get("injury"):
                word = f"your {data.get('body_part', 'injury')} injury"
            elif str(data.get("name") or "").lower() == "temperature" or str(data.get("symptom") or "").lower() == "fever":
                word = "the fever"
            elif e.get("event_type") == "vital_sign":
                word = "a reading"
            else:
                word = data.get("symptom") or data.get("name") or _ASK_LABEL.get(str(e.get("event_type")), "one more thing")
                word = f"the {word}" if e.get("event_type") in ("symptom",) else word
        else:
            word = _LABEL.get(str(e.get("event_type")), "a log")
        if word not in out:
            out.append(str(word))
    return out
