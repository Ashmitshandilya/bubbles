
"""Batch 19: deterministic sleep, recovery and stress intelligence.

This module deliberately reports signals and associations, not diagnoses or medical scores.
It consumes the existing extracted_health_events stream so the 20-table baseline is preserved.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from statistics import mean, pstdev
from typing import Any

def _dt(v: Any) -> datetime | None:
    if not v: return None
    try:
        s=str(v).replace("Z","+00:00")
        d=datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError): return None

def _num(d: dict, *keys: str) -> float | None:
    for k in keys:
        v=d.get(k)
        if isinstance(v,(int,float)): return float(v)
        try:
            if v not in (None,""): return float(v)
        except (TypeError,ValueError): pass
    return None

def analyze(events: list[dict], days: int=30) -> dict:
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(days,365)))
    sleep=[]; stress=[]; recovery=[]; activity=[]
    for e in events:
        dt=_dt(e.get("created_at"))
        if dt and dt < cutoff: continue
        d=e.get("extracted_data") or {}
        typ=str(e.get("event_type","")).lower()
        if "sleep" in typ:
            n=_num(d,"duration_hours","hours","sleep_hours","duration")
            if n is not None: sleep.append(n)
        if "stress" in typ:
            n=_num(d,"severity","score","level","intensity")
            if n is not None: stress.append(n)
        if any(x in typ for x in ("recovery","fatigue","energy")):
            n=_num(d,"score","severity","level","energy")
            if n is not None: recovery.append(n)
        if any(x in typ for x in ("exercise","workout","activity")):
            n=_num(d,"duration_minutes","minutes","duration")
            if n is not None: activity.append(n)
    avg_sleep=mean(sleep) if sleep else None
    sleep_var=pstdev(sleep) if len(sleep)>1 else 0.0 if sleep else None
    avg_stress=mean(stress) if stress else None
    avg_activity=mean(activity) if activity else None
    gaps=[]
    if not sleep: gaps.append("sleep duration data")
    if not stress: gaps.append("stress data")
    if not activity: gaps.append("activity data")
    signals=[]
    if avg_sleep is not None:
        signals.append({"signal":"average_sleep_hours","value":round(avg_sleep,2),"observations":len(sleep)})
    if sleep_var is not None:
        signals.append({"signal":"sleep_variability_hours","value":round(sleep_var,2)})
    if avg_stress is not None:
        signals.append({"signal":"average_stress_signal","value":round(avg_stress,2),"observations":len(stress)})
    return {
        "window_days": max(1,min(days,365)), "sleep": {"observations":len(sleep),"average_hours":avg_sleep,"variability_hours":sleep_var},
        "stress": {"observations":len(stress),"average_signal":avg_stress},
        "activity": {"observations":len(activity),"average_duration_minutes":avg_activity},
        "recovery": {"observations":len(recovery),"average_signal":mean(recovery) if recovery else None},
        "signals":signals,"data_gaps":gaps,
        "limitations":["Signals depend on what was logged.","Associations are not proof of causation.","This module does not diagnose sleep, stress, or other conditions."]
    }
