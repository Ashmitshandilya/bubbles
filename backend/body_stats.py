"""Plain statements of the person's own height or weight, saved at once.

"my height is 6'1", "I am 185 cm tall", "I weigh 110 kg" are clear, numeric, about the speaker and checked against a
plausible range, so they are saved without a Save tap: weight goes into the weight log (through the same confirm path the
Save button uses), height into the profile. Anything unclear, negated, a question or about someone else is left alone; weight
statements the parser already staged still wait for the person unless they are this plain.

Height is a profile figure, not a health event, so there is no pending state for it. Both stores that show it are written:
``profiles.height_cm`` (the Profile screen) and the body profile document (fitness targets).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import clinical_constants as K

_APOS = r"(?:'|’|′|ft\.?|feet|foot)"
_INCH = r"(?:\"|”|″|''|in\.?|inch(?:es)?)"
_FT_IN = rf"(?P<ft>\d)\s*{_APOS}\s*(?:(?P<inch>\d{{1,2}}(?:\.\d)?)\s*{_INCH}?)?"
_CM = r"(?P<cm>\d{3}(?:\.\d)?)\s*(?:cm|centimet(?:er|re)s?)\b"
_VALUE = rf"(?:{_FT_IN}|{_CM})"
# "my height is 6'1", "height: 185 cm", "I am 6'1 tall", "I'm 185cm"
_HEIGHT_NOUN = re.compile(rf"\bmy\s+height\s*(?:is|was|=|:|of)?\s*(?:about\s+|around\s+|roughly\s+)?{_VALUE}", re.I)
_I_AM = re.compile(rf"\bi\s*(?:am|'m|’m)\s+(?:about\s+|around\s+|roughly\s+)?{_VALUE}(?P<tail>\s+(?:tall|in height))?(?![\w'’])", re.I)
_NOT_HEIGHT_TAIL = re.compile(r"^\s*(?:away|from|long|deep|wide|ahead|behind|above|below|under|over)\b", re.I)
_NEGATED = re.compile(r"\b(?:not|n't|never|wasn't|isn't|if|when i was|used to be)\b", re.I)


def _cm_from(match: re.Match[str]) -> float | None:
    if match.group("cm"):
        cm = float(match.group("cm"))
    else:
        feet = int(match.group("ft"))
        inches = float(match.group("inch") or 0)
        if inches >= 12:
            return None
        cm = round((feet * 12 + inches) * 2.54, 1)
    lo, hi = K.MIN_PLAUSIBLE["height_cm"]
    return cm if lo <= cm <= hi else None


def parse_height_cm(text: str) -> float | None:
    """The height the person states about themselves, in cm, or None. Questions, negations and other people never count."""
    for sentence in re.split(r"(?<=[.!?\n])\s+", text or ""):
        if "?" in sentence:
            continue
        for rx in (_HEIGHT_NOUN, _I_AM):
            m = rx.search(sentence)
            if not m:
                continue
            if _NEGATED.search(sentence[: m.start()]):
                continue
            if rx is _I_AM:
                rest = sentence[m.end():]
                if _NOT_HEIGHT_TAIL.match(rest):
                    continue
                # "I am 185 cm" is a height; "I am 5 feet" only with a height cue or an ordinary end of sentence
                if not m.group("tail") and rest.strip(" .!,") and not m.group("cm") and m.group("inch") is None:
                    continue
            cm = _cm_from(m)
            if cm is not None:
                return cm
    return None


def feet_inches(cm: float) -> str:
    total = round(cm / 2.54)
    return f"{total // 12}'{total % 12}\""


def save_height(db: Any, user_id: str, cm: float) -> bool:
    """Write both homes of the figure. True when at least the profile row took it. Never raises."""
    from logging_util import logger
    ok = False
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.table("profiles").update({"height_cm": cm, "updated_at": now}).eq("id", user_id).execute()
        ok = True
    except Exception as error:  # noqa: BLE001
        logger.warning(component="CHAT", operation="save_height_profile", error=error, user_id=user_id, fallback_action="not_saved")
    try:
        import doc_store
        body = doc_store.get(db, user_id, "profile", "me") or {}
        doc_store.put(db, user_id, "profile", "me", {**body, "height_cm": round(cm, 1)})
        ok = True
    except Exception as error:  # noqa: BLE001
        logger.warning(component="CHAT", operation="save_height_doc", error=error, user_id=user_id, fallback_action="profile_row_only")
    return ok


def auto_confirm_weight(db: Any, user_id: str, events: list[dict[str, Any]]) -> list[float]:
    """Confirm the weight events of this turn that are plain (about the speaker, present tense, high confidence). Returns the kg saved."""
    from health_event_confirm import Decision, decide, project_and_remember
    picked = [e for e in events if e.get("event_type") == "weight" and e.get("id") and e.get("status") == "pending"
              and (e.get("assertion") or "present") == "present" and float(e.get("confidence") or 0) >= 0.9]
    if not picked:
        return []
    answers, to_project, _updated = decide(db, user_id, [Decision(id=str(e["id"]), confirmed=True) for e in picked])
    project_and_remember(db, user_id, to_project)   # now, not after the reply: the screens refetch the moment the reply lands
    saved: list[float] = []
    for event, answer in zip(picked, answers):
        if answer.get("status") == "confirmed":
            event["status"] = "confirmed"
            value = (event.get("extracted_data") or {}).get("weight_kg")
            if isinstance(value, (int, float)):
                saved.append(float(value))
    return saved


def auto_save_body_stats(db: Any, user_id: str, message: str, events: list[dict[str, Any]]) -> list[str]:
    """Save what was plainly stated. Returns short sentences to add to the reply (empty when nothing was saved). Never raises."""
    notes: list[str] = []
    try:
        for kg in auto_confirm_weight(db, user_id, events):
            notes.append(f"Saved your weight: {kg:g} kg.")
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        logger.warning(component="CHAT", operation="auto_confirm_weight", error=error, user_id=user_id, fallback_action="left_pending")
    cm = parse_height_cm(message)
    if cm is not None and save_height(db, user_id, cm):
        notes.append(f"Updated your height to {cm:g} cm ({feet_inches(cm)}).")
    return notes
