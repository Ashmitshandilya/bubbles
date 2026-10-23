"""Batch 34: deterministic personalization signals.

Personalization changes tone, timing and prioritization; it must never override
clinical safety policy or fabricate facts.
"""
from __future__ import annotations
from typing import Any

def build_personalization(profile: dict[str, Any] | None, preferences: dict[str, Any] | None,
                          recent_events: list[dict[str, Any]] | None) -> dict[str, Any]:
    profile, preferences, recent_events = profile or {}, preferences or {}, recent_events or []
    signals=[]
    if profile.get("full_name"): signals.append({"kind":"identity","value":"known_name"})
    if preferences.get("communication_style"): signals.append({"kind":"communication","value":preferences["communication_style"]})
    if preferences.get("language"): signals.append({"kind":"language","value":preferences["language"]})
    return {
        "signals": signals,
        "style": preferences.get("communication_style","warm_friendly"),
        "detail_level": preferences.get("response_detail","balanced"),
        "topics_recently_active": list(dict.fromkeys(str(e.get("event_type")) for e in recent_events if e.get("event_type")))[:8],
        "policy":"personalization may adapt presentation and prioritization, never safety thresholds or clinical facts."
    }
