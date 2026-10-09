"""Batch 36: mental-wellness support layer; no diagnosis."""
from __future__ import annotations
from typing import Any

def assess_wellbeing(events: list[dict[str, Any]]) -> dict[str, Any]:
    moods=[]; stress=[]; flags=[]
    for e in events or []:
        typ=str(e.get("event_type") or "").lower(); d=e.get("extracted_data") or {}
        if typ=="mood" and d.get("severity") is not None: moods.append(d.get("severity"))
        if typ=="stress" and d.get("severity") is not None: stress.append(d.get("severity"))
        if typ in {"self_harm","suicidal_ideation"}: flags.append("urgent_safety_signal")
    return {"mood_observations":moods[-10:],"stress_observations":stress[-10:],"safety_flags":flags,
            "scope":"wellbeing support, not diagnosis","missing_data_is_not_normal":True}
