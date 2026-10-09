"""Batch 32: structured personal health state (digital twin), not a health score."""
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone

DOMAINS=("sleep","recovery","cycle","fitness","nutrition","hydration","mood","stress","medications","conditions","symptoms")

def build_digital_twin(state:dict[str,Any], longitudinal:dict[str,Any], memory:dict[str,Any]|None=None) -> dict[str,Any]:
    gaps=list(state.get("data_gaps",[]))
    return {
      "version":"1.0",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "domains":{d:{"available":d not in gaps,"status":"observed" if d not in gaps else "insufficient_data"} for d in DOMAINS},
      "recent_state":state,
      "longitudinal_summary":longitudinal,
      "memory_summary":memory or {},
      "confidence_policy":"confidence reflects data availability and evidence quality; missing data is not interpreted as normal.",
      "causality_policy":"temporal associations are not treated as causal relationships.",
    }
