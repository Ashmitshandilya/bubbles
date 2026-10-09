"""Batch 26: body-system intelligence over existing organ tracker signals."""
from __future__ import annotations
from typing import Any
from organ_tracker import assess_all
from event_filters import clean_data, counts_as_observation


def build_body_system_intelligence(events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    source_ids: dict[str, list[str]] = {}
    # oldest first so the newest value wins the snapshot (readers deliver newest-first)
    live = sorted((e for e in events or [] if isinstance(e, dict) and counts_as_observation(e)),
                  key=lambda e: str(e.get("created_at") or ""))
    for event in live:
        data = event.get("extracted_data") or {}
        if isinstance(data, dict):
            for key, value in clean_data(data).items():
                if value is not None:
                    snapshot[key] = value
                    source_ids.setdefault(key, []).append(str(event.get("id")))
    snapshot["source_ids"] = source_ids
    assessments = assess_all(snapshot)
    rows = []
    for item in assessments:
        row = item.__dict__.copy() if hasattr(item, "__dict__") else dict(item)
        row["signals"] = [s.__dict__ if hasattr(s, "__dict__") else s for s in row.get("signals", [])]
        rows.append(row)
    observed = sum(1 for r in rows if r.get("data_completeness", 0) > 0)
    return {
        "systems": rows,
        "systems_with_data": observed,
        "total_systems": len(rows),
        "interpretation": "Body-system signals organize available evidence; they do not diagnose disease or establish that an organ is healthy or damaged.",
    }
