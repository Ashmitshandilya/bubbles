"""Batch 37: social/relationship wellbeing context."""
from __future__ import annotations
from typing import Any

def analyze_social_context(events: list[dict[str, Any]]) -> dict[str, Any]:
    relevant=[e for e in events or [] if str(e.get("event_type","")).lower() in {"social","relationship","loneliness","support"}]
    return {"observations":len(relevant),"recent":relevant[-10:],"policy":"reflect user-reported context without inferring motives, diagnoses or relationship outcomes."}
