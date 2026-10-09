"""Bubbles personal health-state engine.

Deterministic, evidence-aware aggregation over explicitly logged health events.
It reports observations and deviations from the user's own recent baseline.
It does not diagnose or infer causation.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any
from pattern_engine import normalize_events, temporal_correlations

def _num(data: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        v=data.get(k)
        try:
            if isinstance(v,bool) or v is None: continue
            x=float(v)
            if x == x and abs(x) != float("inf"): return x
        except (TypeError,ValueError): pass
    return None

def _values(rows, event_types, keys):
    out=[]
    for r in rows:
        if r["event_type"] not in event_types: continue
        x=_num(r["data"],*keys)
        if x is not None: out.append((r["created_at"],x))
    return out

def _avg(v): return round(sum(x for _,x in v)/len(v),2) if v else None

def build_health_state(events, *, days=14):
    # Defensive: ensure events is iterable list-like, not string
    if isinstance(events, str):
        from logging_util import logger
        logger.warning(
            component="HEALTH_STATE_ENGINE",
            operation="build_health_state",
            message=f"Received string instead of list: {events[:100]}",
            context={"received_type": "str", "input_length": len(events)},
            fallback_action="using_empty_events",
        )
        events = []
    if not isinstance(events, (list, tuple)):
        from logging_util import logger
        logger.warning(
            component="HEALTH_STATE_ENGINE",
            operation="build_health_state",
            message=f"Received non-list type: {type(events)}",
            context={"received_type": type(events).__name__},
            fallback_action="using_empty_events",
        )
        events = []
    rows=normalize_events(events)
    now=datetime.now(timezone.utc)
    cutoff=now-timedelta(days=max(1,days))
    recent=[r for r in rows if r["created_at"]>=cutoff]
    previous=[r for r in rows if cutoff-timedelta(days=days)<=r["created_at"]<cutoff]
    metrics={
      "sleep_hours": _values(recent,{"sleep","sleep_log","sleep_logs"},{"hours","duration_hours","sleep_hours","duration"}),
      "water_ml": _values(recent,{"hydration","hydration_log","hydration_logs"},{"water_ml","amount_ml","volume_ml","ml"}),
      "activity_minutes": _values(recent,{"activity","activity_log","exercise","exercise_log","exercise_logs"},{"minutes","duration_minutes","active_minutes"}),
      "weight_kg": _values(recent,{"weight","weight_log","weight_logs"},{"weight_kg","kg","weight"}),
      "mood": _values(recent,{"mood","mood_log","mood_logs"},{"score","mood_score","rating"}),
    }
    baseline={}
    deviations={}
    for name, vals in metrics.items():
        baseline_vals=[]
        for r in previous:
            if r["event_type"] in {"sleep","sleep_log","sleep_logs"} and name=="sleep_hours":
                x=_num(r["data"],"hours","duration_hours","sleep_hours","duration")
            elif r["event_type"] in {"hydration","hydration_log","hydration_logs"} and name=="water_ml":
                x=_num(r["data"],"water_ml","amount_ml","volume_ml","ml")
            elif r["event_type"] in {"activity","activity_log","exercise","exercise_log","exercise_logs"} and name=="activity_minutes":
                x=_num(r["data"],"minutes","duration_minutes","active_minutes")
            elif r["event_type"] in {"weight","weight_log","weight_logs"} and name=="weight_kg":
                x=_num(r["data"],"weight_kg","kg","weight")
            elif r["event_type"] in {"mood","mood_log","mood_logs"} and name=="mood":
                x=_num(r["data"],"score","mood_score","rating")
            else: x=None
            if x is not None: baseline_vals.append(x)
        if baseline_vals:
            baseline[name]=round(sum(baseline_vals)/len(baseline_vals),2)
            cur=_avg(vals)
            if cur is not None:
                delta=round(cur-baseline[name],2)
                pct=round(delta/baseline[name]*100,1) if baseline[name] else None
                deviations[name]={"current":cur,"baseline":baseline[name],"delta":delta,"percent":pct}
    signal_counts=defaultdict(int)
    for r in recent: signal_counts[r["event_type"]]+=1
    data_gaps=[name for name,vals in metrics.items() if not vals]
    return {
      "window_days":days,"event_count":len(recent),
      "signal_counts":dict(signal_counts),"baseline":baseline,
      "deviations":deviations,"data_gaps":data_gaps,
      "correlations":temporal_correlations(recent,window_days=2,min_pairs=3)[:8],
      "status":"limited" if len(recent)<3 else "active",
      "interpretation":"Personal baseline comparisons are observational and depend on the quality and amount of logged data."
    }
