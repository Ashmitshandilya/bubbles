"""Bubbles nutrition intelligence: deterministic, explainable summaries from logged events.

This module intentionally reports logged data and associations; it does not diagnose or prescribe.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def _data(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("extracted_data") or event.get("data") or {}
    return value if isinstance(value, dict) else {}


def _number(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip().split()[0])
            except (ValueError, IndexError):
                pass
    return None


def analyze(events: list[dict[str, Any]]) -> dict[str, Any]:
    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    meals = water = calories = protein = 0.0
    dated = 0
    for event in events:
        data = _data(event)
        kind = str(event.get("event_type") or data.get("type") or "").lower()
        date = str(event.get("created_at") or data.get("date") or "")[:10]
        if not date:
            date = "unknown"
        c = _number(data, "calories", "kcal", "energy_kcal")
        p = _number(data, "protein_g", "protein", "protein_grams")
        w = _number(data, "water_ml", "water", "hydration_ml", "volume_ml")
        if c is not None or "meal" in kind or "food" in kind or "nutrition" in kind:
            meals += 1 if c is None else 0
            if c is not None:
                calories += c; daily[date]["calories"] += c
            if p is not None:
                protein += p; daily[date]["protein"] += p
        if w is not None or "water" in kind or "hydration" in kind:
            if w is not None:
                water += w; daily[date]["water_ml"] += w
        if date != "unknown":
            dated += 1

    days = max(len([d for d in daily if d != "unknown"]), 1)
    return {
        "summary": {
            "days_with_nutrition_signals": days if daily else 0,
            "logged_meals_without_calories": int(meals),
            "total_calories_logged": round(calories, 1),
            "average_daily_calories_logged": round(calories / days, 1) if calories else None,
            "total_protein_g_logged": round(protein, 1),
            "average_daily_protein_g_logged": round(protein / days, 1) if protein else None,
            "total_water_ml_logged": round(water, 1),
            "average_daily_water_ml_logged": round(water / days, 1) if water else None,
        },
        "data_quality": {
            "dated_event_count": dated,
            "note": "Missing nutrition values are not treated as zero. Bubbles only summarizes values that were actually logged."
        },
        "safety_note": "Nutrition summaries are informational and should not be used as a diagnosis or as a substitute for individualized clinical/dietetic care.",
    }


def analyze_flat(events: list[dict[str, Any]]) -> dict[str, Any]:
    """analyze() flattened to the schemas.NutritionSummaryData contract (summary fields at top level)."""
    result = analyze(events)
    return {**(result.get("summary") or {}), "data_quality": result.get("data_quality") or {}, "safety_note": result.get("safety_note")}
