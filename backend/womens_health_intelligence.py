"""Batch 38: life-stage women's-health routing foundation."""
from __future__ import annotations
from typing import Any

from event_filters import clean_data, counts_as_observation

TOPICS=("cycle","fertility","pregnancy","contraception","sexual_health","perimenopause","menopause","reproductive_health")
def classify_womens_health(events: list[dict[str,Any]]) -> dict[str,Any]:
    counts={t:0 for t in TOPICS}
    for e in events or []:
        if not isinstance(e,dict) or not counts_as_observation(e): continue
        typ=str(e.get("event_type","")).lower()
        d=clean_data(e.get("extracted_data") if isinstance(e.get("extracted_data"),dict) else {})
        blob=(typ+" "+str(d)).lower()
        for t in TOPICS:
            if t.replace("_"," ") in blob or t in typ: counts[t]+=1
    return {"topics":counts,"limitations":["not diagnostic","life-stage conclusions require adequate history and, when appropriate, clinician confirmation"]}
