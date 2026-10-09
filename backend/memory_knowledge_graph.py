"""Bubbles memory intelligence and lightweight personal knowledge graph."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from pattern_engine import normalize_events

def build_knowledge_graph(events: list[dict[str, Any]], *, days: int = 180) -> dict[str, Any]:
    rows=normalize_events(events); nodes={}; edges={}
    for row in rows:
        kind=str(row.get("event_type") or "unknown").strip().lower()
        if not kind: continue
        nodes.setdefault(kind,{"id":kind,"type":"health_domain","event_count":0})["event_count"]+=1
        data=row.get("data") or {}
        if isinstance(data,dict):
            for key,value in data.items():
                if isinstance(value,(str,int,float,bool)) and value not in ("",None):
                    attr=f"{kind}:{key}"
                    nodes.setdefault(attr,{"id":attr,"type":"attribute","value_examples":[]})
                    ex=nodes[attr]["value_examples"]
                    if len(ex)<5 and str(value) not in ex: ex.append(str(value))
                    pair=(kind,attr)
                    edges.setdefault(pair,{"source":kind,"target":attr,"relation":"has_attribute","evidence_count":0})["evidence_count"]+=1
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"window_days":days,
            "nodes":list(nodes.values())[:200],"edges":list(edges.values())[:400],
            "node_count":len(nodes),"edge_count":len(edges),
            "note":"The graph represents logged observations and attributes; it is not a clinical knowledge graph and does not establish causation."}

def memory_candidates(events: list[dict[str,Any]]) -> list[dict[str,Any]]:
    counts=Counter(str(r.get("event_type") or "unknown").lower() for r in normalize_events(events))
    return [{"memory_level":"L3","kind":"recurring_domain","subject":k,"evidence_count":v,
             "confidence":round(min(.95,.5+v/20),2),"status":"candidate",
             "reason":"Repeated logged observations; retain source events and provenance."}
            for k,v in counts.most_common(20) if v>=3]
