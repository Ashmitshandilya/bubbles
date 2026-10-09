"""Batch 39: medication tracking and clinician-discussion support."""
from __future__ import annotations
from typing import Any

from event_filters import counts_as_observation

def medication_overview(events: list[dict[str,Any]]) -> dict[str,Any]:
    meds=[e for e in events or [] if isinstance(e,dict) and counts_as_observation(e) and str(e.get("event_type","")).lower() in {"medication","supplement"}]
    names=[]
    for e in meds:
        d=e.get("extracted_data") or {}
        n=d.get("name") or d.get("medication") or d.get("details")
        if n: names.append(str(n))
    return {"medications":list(dict.fromkeys(names)),"count":len(meds),
            "guardrails":["do not start/stop/change dose","interaction information requires verified drug knowledge and clinician/pharmacist confirmation"]}
