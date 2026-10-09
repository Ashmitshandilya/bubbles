"""Bubbles personal learning layer.

Builds evidence-backed pattern records and memory candidates without writing
directly to the database. Persistence remains under explicit application flows.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pattern_engine import analyze, normalize_events

def build_learning_snapshot(events, *, days=90):
    rows=normalize_events(events)
    analysis=analyze(rows,days=days)
    candidates=[]
    for p in analysis.get("patterns",[]):
        occ=p.get("occurrence_count",0)
        conf=p.get("average_confidence",0)
        if occ>=3 and conf>=0.6:
            candidates.append({
              "memory_level":"L3","kind":"recurring_pattern",
              "subject":p.get("subject"),"confidence":conf,
              "evidence_count":occ,"source_event_ids":p.get("source_event_ids",[])[:20],
              "status":"candidate","reason":"repeated and sufficiently confident observation"
            })
    for c in analysis.get("correlations",[])[:10]:
        if c.get("pair_count",0)>=3:
            candidates.append({
              "memory_level":"L3","kind":"temporal_association",
              "subject":f'{c.get("left_subject")} + {c.get("right_subject")}',
              "confidence":c.get("confidence",0),
              "evidence_count":c.get("pair_count",0),
              "source_event_ids":c.get("source_event_ids",[])[:20],
              "status":"candidate","reason":"repeated temporal co-occurrence; not causation"
            })
    return {
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "event_count":len(rows),"analysis":analysis,
      "memory_candidates":candidates[:20],
      "uncertainty":{
        "has_enough_data":len(rows)>=3,
        "message":"Bubbles will not promote or conclude a pattern when evidence is sparse or inconsistent."
      }
    }

def reconcile_fact(old_fact, new_fact):
    if old_fact == new_fact:
        return {"action":"retain","confidence":"stable"}
    return {
      "action":"review",
      "confidence":"uncertain",
      "reason":"New information differs from an existing fact; preserve provenance and ask for clarification."
    }
