"""Batch 40: preventive-health checklist framework."""
from __future__ import annotations
from typing import Any

def preventive_snapshot(profile: dict[str,Any], events: list[dict[str,Any]]) -> dict[str,Any]:
    seen={str(e.get("event_type","")).lower() for e in events or []}
    return {"age":profile.get("age") or None,"signals_present":sorted(seen & {"vaccination","screening","doctor_visit","lab_result"}),
            "needs_context":"Preventive recommendations require age, sex, life-stage, history and geography; missing data must be surfaced rather than assumed."}
