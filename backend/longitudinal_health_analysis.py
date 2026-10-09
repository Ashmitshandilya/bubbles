"""Longitudinal health state, trajectories and non-causal temporal associations."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean

from event_filters import counts_as_observation

DOMAINS={
 "sleep":("sleep",),"stress":("stress",),"mood":("mood",),"weight":("weight",),
 "hydration":("water","hydration"),"exercise":("exercise","workout","activity"),
 "symptom":("symptom","pain"),"cycle":("period","menstrual","cycle"),
 "nutrition":("food","nutrition","meal")
}
EXPECTED_DOMAINS=list(DOMAINS.keys())

def _dt(x):
    try:
        d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _value(d):
    for k in ("value","score","severity","duration_hours","hours","amount","weight_kg","minutes"):
        v=d.get(k)
        if isinstance(v,(int,float)) and not isinstance(v,bool):
            return float(v)
    return None

def analyze(events:list[dict],days:int=180)->dict:
    # Defensive: ensure events is list[dict], not string or other type
    if isinstance(events, str):
        from logging_util import logger
        logger.warning(
            component="LONGITUDINAL_ANALYSIS",
            operation="analyze",
            message=f"Received string instead of list: {events[:100]}",
            context={"received_type": "str", "input_length": len(events)},
            fallback_action="using_empty_events",
        )
        events = []
    if not isinstance(events, (list, tuple)):
        from logging_util import logger
        logger.warning(
            component="LONGITUDINAL_ANALYSIS",
            operation="analyze",
            message=f"Received non-list type: {type(events)}",
            context={"received_type": type(events).__name__},
            fallback_action="using_empty_events",
        )
        events = []
    days=max(7,min(days,730)); cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    by=defaultdict(list); timeline=[]
    for e in events:
        if not isinstance(e, dict) or not counts_as_observation(e):
            continue
        dt=_dt(e.get("created_at"))
        if not dt or dt<cutoff: continue
        typ=str(e.get("event_type","" )).lower(); d=e.get("extracted_data") or {}
        domain=next((k for k,terms in DOMAINS.items() if any(t in typ for t in terms)),"other")
        val=_value(d); by[domain].append((dt,val))
        timeline.append({"date":dt.date().isoformat(),"domain":domain,"event_type":e.get("event_type"),"value":val})

    summaries={}
    for domain in EXPECTED_DOMAINS:
        rows=by.get(domain,[]); vals=[v for _,v in rows if v is not None]
        ordered=sorted(rows,key=lambda x:x[0]); first=vals[0] if vals else None; last=vals[-1] if vals else None
        observed_days=len({dt.date() for dt,_ in rows})
        sparse_threshold=max(2,days//14)
        summaries[domain]={
            "observations":len(rows),"numeric_observations":len(vals),"observed_days":observed_days,
            "coverage_status":"missing" if not rows else ("sparse" if observed_days < sparse_threshold else "observed"),
            "average":round(mean(vals),3) if vals else None,"first_numeric":first,"latest_numeric":last,
            "delta":(last-first) if first is not None and last is not None else None,
        }
    if by.get("other"):
        rows=by["other"]; vals=[v for _,v in rows if v is not None]
        summaries["other"]={"observations":len(rows),"numeric_observations":len(vals),"observed_days":len({dt.date() for dt,_ in rows}),"coverage_status":"observed","average":round(mean(vals),3) if vals else None}

    associations=[]
    present=[d for d in EXPECTED_DOMAINS if by.get(d)]
    for i,a in enumerate(present):
        for b in present[i+1:]:
            days_a={x[0].date() for x in by[a]}; days_b={x[0].date() for x in by[b]}; common=days_a & days_b
            if len(common)>=3:
                denominator=max(1,min(len(days_a),len(days_b)))
                associations.append({"domains":[a,b],"shared_days":len(common),"overlap_ratio":round(len(common)/denominator,3),"interpretation":"temporal co-occurrence only; not causal"})
    return {
        "window_days":days,"domains":summaries,"timeline":sorted(timeline,key=lambda x:x["date"],reverse=True)[:500],"temporal_associations":associations,
        "data_quality":{
            "events_used":len(timeline),"domains_present":len(present),"expected_domains":EXPECTED_DOMAINS,
            "minimum_association_days":3,"missing_data_policy":"unlogged domains remain missing; they are never treated as normal",
        },
        "limitations":["Trend estimates depend on logging frequency and event semantics.","Co-occurrence does not establish causation.","Missing data can distort apparent trends."]
    }
