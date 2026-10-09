"""Bubbles menstrual-cycle intelligence using logged cycle events only."""
from __future__ import annotations

from datetime import date, datetime
from statistics import mean
from typing import Any

from event_filters import counts_as_observation


def _data(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("extracted_data") or event.get("data") or {}
    return value if isinstance(value, dict) else {}


def _date(event: dict[str, Any], *keys: str) -> date | None:
    data = _data(event)
    for key in keys:
        raw = data.get(key) or event.get(key)
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    return date.fromisoformat(str(raw)[:10])
                except ValueError:
                    pass
    raw = event.get("created_at")
    if raw:
        try: return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except ValueError: return None
    return None


def _flag(value: Any) -> bool:
    """Real boolean for a stored flag: the string "false"/"no" must not be truthy.

    A date string is accepted as True because period_start/cycle_start may hold the start date itself.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "y", "t", "1", "on"}:
            return True
        try:
            date.fromisoformat(text[:10])
            return True
        except ValueError:
            return False
    return False


def is_cycle_start(data: dict[str, Any]) -> bool:
    return any(_flag(data.get(k)) for k in ("is_start", "period_start", "cycle_start"))


def analyze(events: list[dict[str, Any]]) -> dict[str, Any]:
    starts: list[date] = []
    lengths: list[float] = []
    symptoms: list[str] = []
    for event in events:
        if not isinstance(event, dict) or not counts_as_observation(event):
            continue
        data = _data(event)
        kind = str(event.get("event_type") or data.get("type") or "").lower()
        if "period" in kind or "menstrual" in kind or "cycle" in kind:
            if is_cycle_start(data):
                d = _date(event, "start_date", "period_start", "cycle_start", "date")
                if d: starts.append(d)
            length = data.get("cycle_length") or data.get("length_days")
            try:
                if length is not None: lengths.append(float(length))
            except (ValueError, TypeError): pass
            # cycle symptoms only: `name` is a symptom on a menstrual_symptom row, but just a label ("period") elsewhere
            symptom = data.get("symptom") or data.get("symptoms") or (data.get("name") if "symptom" in kind else None)
            if isinstance(symptom, str) and symptom.strip(): symptoms.append(symptom.strip())
            elif isinstance(symptom, list): symptoms.extend(str(x) for x in symptom if x)
    starts = sorted(set(starts))
    gaps = [(b-a).days for a,b in zip(starts, starts[1:]) if 1 <= (b-a).days <= 120]
    return {
        "cycle": {
            "period_start_count": len(starts),
            "observed_cycle_lengths": [round(x, 1) for x in lengths[-12:]],
            "average_observed_cycle_length": round(mean(lengths), 1) if lengths else None,
            "start_to_start_intervals": gaps[-12:],
            "latest_period_start": starts[-1].isoformat() if starts else None,
        },
        "symptoms": {"recent_unique": sorted(set(symptoms))[-20:]},
        "interpretation": "Bubbles describes logged cycle observations. Irregularity, symptoms, or changes may have many causes and are not diagnosed by this analysis.",
        "data_quality": "Cycle estimates become more useful as more complete period-start and symptom data are logged.",
    }
