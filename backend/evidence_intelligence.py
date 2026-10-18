"""Batch 27: evidence registry, grounding and source-quality primitives."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class EvidenceItem:
    source_id: str
    title: str
    source_type: str
    relevance: float = 0.0
    freshness: float = 1.0
    authority: float = 0.5
    excerpt: str = ""
    url: str | None = None


def rank_evidence(items: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    ranked=[]
    for raw in items:
        item=dict(raw)
        score=(float(item.get("relevance",0))*0.45 + float(item.get("authority",0.5))*0.35 + float(item.get("freshness",1))*0.20)
        item["evidence_score"]=round(max(0.0,min(1.0,score)),3)
        ranked.append(item)
    return sorted(ranked,key=lambda x:x["evidence_score"],reverse=True)[:max(1,min(limit,50))]


def build_grounding_packet(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    ranked=rank_evidence(evidence)
    return {
        "question": question,
        "sources": ranked,
        "source_count": len(ranked),
        "grounded": bool(ranked),
        "rules":["prefer primary/clinical sources when available","do not invent citations","separate evidence from inference","state uncertainty when evidence is incomplete"],
    }


def source_quality(source_type: str) -> float:
    return {"guideline":1.0,"systematic_review":0.95,"meta_analysis":0.95,"primary_study":0.85,"government":0.9,"clinical_reference":0.9,"educational":0.65,"unknown":0.4}.get(str(source_type).lower(),0.4)

