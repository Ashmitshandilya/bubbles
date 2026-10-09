"""One shared definition of "this stored event is a real, current, positive observation".

Every reader of ``extracted_health_events`` (analytics, memory, doctor timeline,
FHIR export, LLM context) must agree on which rows count. Rows do NOT count if
they were rejected/superseded/retracted, if they record an explicit denial
("pertinent negative"), if they are about someone else, or if they were
extracted from a hedged/hypothetical/quoted statement.

Provenance and assertion live under the namespaced ``_prov`` key inside the
existing ``extracted_data`` JSON, so no schema change is needed:

    extracted_data["_prov"] = {
        "source": "user_message", "message_id": "...", "extractor": "rules|llm",
        "assertion": "present|possible|...", "temporal": "current|...",
        "subject": "self|other", "recorded_at": "...", "key": "<dedupe key>",
    }

Keys starting with ``_`` are metadata, never clinical values: readers that flatten
``extracted_data`` must skip them (see :func:`clean_data`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

#: statuses that mean the user (or a correction) said this row is wrong or replaced.
DEAD_STATUSES = frozenset({"rejected", "superseded", "retracted"})
#: event types that record symptom screens / pertinent negatives, not observations.
SCREEN_TYPES = frozenset({"wellness_checkin"})


def _data(row: dict[str, Any]) -> dict[str, Any]:
    d = row.get("extracted_data")
    if d is None:
        d = row.get("data")
    return d if isinstance(d, dict) else {}


def provenance(row: dict[str, Any]) -> dict[str, Any]:
    p = _data(row).get("_prov")
    return p if isinstance(p, dict) else {}


def is_live_positive(row: dict[str, Any]) -> bool:
    """True when the row asserts something the user currently/recently reports about themselves."""
    if not isinstance(row, dict):
        return False
    if (row.get("extraction_status") or "pending") in DEAD_STATUSES:
        return False
    data = _data(row)
    if data.get("present") is False:
        return False
    prov = provenance(row)
    if prov.get("assertion", "present") != "present":
        return False
    if prov.get("subject", "self") != "self":
        return False
    return True


def is_screen(row: dict[str, Any]) -> bool:
    return str(row.get("event_type") or "").lower() in SCREEN_TYPES


def counts_as_observation(row: dict[str, Any]) -> bool:
    """Live positive AND not a symptom-screen record."""
    return is_live_positive(row) and not is_screen(row)


def pertinent_negatives(row: dict[str, Any]) -> list[str]:
    """Explicitly denied concepts recorded on a screen row (empty for everything else)."""
    if not is_screen(row) or (row.get("extraction_status") or "pending") in DEAD_STATUSES:
        return []
    items = _data(row).get("pertinent_negatives")
    return [str(i) for i in items if isinstance(i, str)] if isinstance(items, list) else []


def clean_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """`extracted_data` without metadata keys (those starting with an underscore)."""
    return {k: v for k, v in (data or {}).items() if not str(k).startswith("_")}


def parse_moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def event_moment(row: dict[str, Any]) -> datetime | None:
    """When the thing happened: the event's own date(/time) if given, else when it was recorded."""
    data = _data(row)
    day = data.get("date") or data.get("occurred_at")
    if day:
        text = str(day)
        if len(text) == 10:  # date only: noon UTC avoids flipping the day in other time zones
            text = f"{text}T12:00:00+00:00"
        moment = parse_moment(text)
        if moment:
            return moment
    return parse_moment(row.get("created_at"))
