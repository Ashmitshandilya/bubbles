"""Batch 35: habit/adherence intelligence without punitive scoring."""
from __future__ import annotations
from collections import Counter
from typing import Any

def analyze_habits(events: list[dict[str, Any]], days: int = 30) -> dict[str, Any]:
    counts=Counter()
    for e in events or []:
        typ=str(e.get("event_type") or "").lower()
        if typ in {"sleep","hydration","exercise","activity","food","medication","mood","stress"}:
            counts[typ]+=1
    opportunities=[{"domain":k,"observations":v,"suggestion":"make the next action smaller and easier to repeat"} for k,v in counts.most_common()]
    return {"window_days":days,"domains":opportunities,"principles":["reduce friction","avoid shame","measure adherence from available logs","do not infer non-adherence from missing data"]}
