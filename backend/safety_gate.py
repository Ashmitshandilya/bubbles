"""One gate for free text that is about to be stored (check-in notes, journal, tracker notes, ...).

Every free-text field is passed to ``safety_engine.assess_safety``. On URGENT / EMERGENCY or crisis wording the caller must stop,
store nothing and return the dict this returns (the same ``status: "safety"`` shape the wellness routes already use). The wording is
the engine's own deterministic copy (India-first crisis lines); this module adds none. No model is ever called.
"""
from __future__ import annotations

from typing import Any

from safety_engine import assess_safety, emergency_response, urgent_fallback_response


def safety_gate(*texts: str | None, crisis_only: bool = False) -> dict[str, Any] | None:
    """The safety response to send back (and the caller must stop) when any text is URGENT / EMERGENCY or carries crisis wording;
    None when it is safe to continue. ``crisis_only`` blocks only crisis wording: used for fields that name a symptom ("chest pain"),
    where the symptom itself is the thing being logged."""
    for t in texts:
        if not t or not isinstance(t, str):
            continue
        a = assess_safety(t)
        if a.crisis or (not crisis_only and a.state in ("URGENT", "EMERGENCY")):
            msg = emergency_response(a) if a.state == "EMERGENCY" or a.crisis else urgent_fallback_response(a)
            return {"status": "safety", "state": a.state, "level": a.level, "crisis": a.crisis, "message": msg,
                    "saved": False, "note": "Nothing was saved from this message."}
    return None
