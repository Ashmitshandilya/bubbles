"""Batch 41: consent-aware sharing contracts, no automatic disclosure."""
from __future__ import annotations
from typing import Any

SCOPES=("profile","health_events","labs","medications","reports","timeline","insights")
def build_share_plan(requested_scopes:list[str], consent:dict[str,bool]|None=None)->dict[str,Any]:
    consent=consent or {}; allowed=[s for s in requested_scopes if s in SCOPES and consent.get(s) is True]
    denied=[s for s in requested_scopes if s not in allowed]
    return {"allowed":allowed,"denied":denied,"requires_explicit_consent":True,"expires":True,"default":"deny"}
