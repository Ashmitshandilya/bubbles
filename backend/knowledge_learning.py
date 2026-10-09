"""Batch 44: knowledge freshness and feedback governance."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

def knowledge_health(sources:list[dict[str,Any]])->dict[str,Any]:
    now=datetime.now(timezone.utc); stale=0
    for s in sources or []:
        if not s.get("publication_date") and not s.get("retrieved_at"): stale+=1
    return {"source_count":len(sources or []),"metadata_gaps":stale,"generated_at":now.isoformat(),
            "policy":"new evidence updates knowledge versions; it does not silently rewrite historical user records."}
