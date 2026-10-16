"""The deterministic crisis check for free text, shared by every route that stores something a person typed.

It lives apart from ``mind_checkins`` so ``health_logs`` can use it without a circular import."""
from __future__ import annotations

from typing import Any

from safety_engine import assess_safety, emergency_response, urgent_fallback_response

#: body fields of a tracker entry that carry something the person typed
FREE_TEXT_FIELDS = ("notes", "description", "reason", "text", "title", "name", "trigger", "details", "activity")


def safety_gate(*texts: str | None) -> dict[str, Any] | None:
    """Run every non-empty free-text field through the safety engine. Returns the safety response to send back (and the caller must
    stop, storing nothing) when any text is URGENT / EMERGENCY or carries crisis wording; None when it is safe to continue."""
    for t in texts:
        if not t:
            continue
        a = assess_safety(t)
        if a.state in ("URGENT", "EMERGENCY") or a.crisis:
            msg = emergency_response(a) if a.state == "EMERGENCY" or a.crisis else urgent_fallback_response(a)
            return {"status": "safety", "state": a.state, "level": a.level, "crisis": a.crisis, "message": msg,
                    "saved": False, "note": "Nothing was saved from this message."}
    return None


def gate_body(body: dict) -> dict[str, Any] | None:
    """The safety response for a tracker request body, looking only at its free-text fields."""
    return safety_gate(*(body.get(k) for k in FREE_TEXT_FIELDS if isinstance(body.get(k), str)))
