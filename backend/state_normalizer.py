"""Single serialization layer for health state transformation.

Consolidates all inline transformations previously scattered across main.py
into one canonical function. Ensures consistent API contract between
engine output and Pydantic response schemas.
"""
from __future__ import annotations
from typing import Any


def normalize_health_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize health state dict to match Pydantic HealthStateData schema.

    Transforms engine output (flat lists) to API contract (wrapped objects):
    - data_gaps: List[str] -> {"gaps": List[str]}
    - correlations: List[CorrelationItem] -> {"items": List[CorrelationItem]}

    Args:
        state: Raw state dict from build_health_state() or None

    Returns:
        Normalized state dict ready for HealthStateData(**state)
    """
    if not state:
        return {
            "window_days": 0,
            "event_count": 0,
            "signal_counts": {"sleep": 0, "hrv": 0, "resting_hr": 0, "stress": 0, "steps": 0},
            "baseline": {},
            "deviations": {},
            "data_gaps": {"gaps": []},
            "correlations": {"items": []},
            "status": "limited",
            "interpretation": "No health events available for analysis.",
        }

    # Create a shallow copy to avoid mutating the original
    normalized = dict(state)

    # Transform data_gaps: List[str] -> {"gaps": List[str]}
    raw_gaps = normalized.get("data_gaps")
    if isinstance(raw_gaps, list):
        normalized["data_gaps"] = {"gaps": [str(g) for g in raw_gaps]}
    elif isinstance(raw_gaps, dict) and "gaps" in raw_gaps:
        # Already normalized - ensure gaps is a list of strings
        normalized["data_gaps"]["gaps"] = [str(g) for g in raw_gaps.get("gaps", [])]
    else:
        normalized["data_gaps"] = {"gaps": []}

    # Transform correlations: List[dict] -> {"items": List[dict]}
    raw_correlations = normalized.get("correlations")
    if isinstance(raw_correlations, list):
        normalized["correlations"] = {"items": raw_correlations}
    elif isinstance(raw_correlations, dict) and "items" in raw_correlations:
        # Already normalized
        pass
    else:
        normalized["correlations"] = {"items": []}

    # Ensure deviations is a dict with proper structure
    deviations = normalized.get("deviations")
    if not isinstance(deviations, dict):
        normalized["deviations"] = {}

    # Ensure signal_counts has all required keys
    signal_counts = normalized.get("signal_counts")
    if not isinstance(signal_counts, dict):
        normalized["signal_counts"] = {"sleep": 0, "hrv": 0, "resting_hr": 0, "stress": 0, "steps": 0}
    else:
        for key in ["sleep", "hrv", "resting_hr", "stress", "steps"]:
            if key not in signal_counts:
                signal_counts[key] = 0

    # Ensure required scalar fields exist with defaults
    normalized.setdefault("window_days", 0)
    normalized.setdefault("event_count", 0)
    normalized.setdefault("baseline", {})
    normalized.setdefault("status", "limited")
    normalized.setdefault("interpretation", "")

    return normalized


def normalize_living_signal_map(map_data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize living signal map data to match LivingSignalMapData schema.

    Args:
        map_data: Raw map dict from build_living_signal_map() or None

    Returns:
        Normalized map dict ready for LivingSignalMapData(**map_data)
    """
    if not map_data:
        return {
            "status": "limited",
            "observed_signal_count": 0,
            "baseline_change_count": 0,
            "data_gap_count": 0,
            "signals": [],
            "data_gaps": [],
            "coverage": "observed",
            "interpretation_policy": "Observed signals describe what was logged. Repeated co-occurrence is exploratory and does not establish causation.",
        }

    normalized = dict(map_data)

    # Ensure data_gaps is a list of strings
    gaps = normalized.get("data_gaps")
    if isinstance(gaps, list):
        normalized["data_gaps"] = [str(g) for g in gaps]
    else:
        normalized["data_gaps"] = []

    # Ensure signals is a list
    signals = normalized.get("signals")
    if not isinstance(signals, list):
        normalized["signals"] = []

    # Ensure scalar fields with defaults
    normalized.setdefault("status", "limited")
    normalized.setdefault("observed_signal_count", 0)
    normalized.setdefault("baseline_change_count", 0)
    normalized.setdefault("data_gap_count", len(normalized["data_gaps"]))
    normalized.setdefault("coverage", "observed")
    normalized.setdefault(
        "interpretation_policy",
        "Observed signals describe what was logged. Repeated co-occurrence is exploratory and does not establish causation.",
    )

    return normalized