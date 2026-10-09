"""Deterministic longitudinal signal synthesis for Bubbles.

Turns existing health-state, gaps, deviations and correlations into a compact
"living signal map". It never diagnoses and never treats correlation as causation.
"""
from __future__ import annotations
from typing import Any


def build_living_signal_map(state: dict[str, Any] | None, *, correlations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    state = state or {}
    deviations = state.get("deviations") or {}
    gaps = [str(x) for x in (state.get("data_gaps") or [])]
    correlations = correlations or []
    signals = []
    for key, item in list(deviations.items())[:8]:
        if not isinstance(item, dict):
            continue
        signals.append({
            "kind": "baseline_change",
            "label": str(key).replace("_", " "),
            "direction": "up" if float(item.get("delta", 0) or 0) > 0 else "down" if float(item.get("delta", 0) or 0) < 0 else "stable",
            "confidence": "moderate",
            "evidence": "observed personal-baseline deviation",
        })
    for corr in correlations[:6]:
        if isinstance(corr, dict):
            signals.append({
                "kind": "repeated_cooccurrence",
                "label": corr.get("pair") or corr.get("label") or "Repeated signals",
                "direction": "context",
                "confidence": corr.get("confidence", "exploratory"),
                "evidence": "repeated temporal co-occurrence; not proof of causation",
            })
    return {
        "status": state.get("status", "limited"),
        "observed_signal_count": int(state.get("event_count", 0) or 0),
        "baseline_change_count": len(deviations),
        "data_gap_count": len(gaps),
        "signals": signals[:12],
        "data_gaps": gaps[:10],
        "coverage": "sparse" if len(gaps) >= 3 else "partial" if gaps else "observed",
        "interpretation_policy": "Observed signals describe what was logged. Repeated co-occurrence is exploratory and does not establish causation.",
    }
