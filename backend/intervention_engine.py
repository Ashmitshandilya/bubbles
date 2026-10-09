"""Batch 28: personalized just-in-time intervention selection."""
from __future__ import annotations
from typing import Any


def _clamp(v: float) -> float: return max(0.0,min(1.0,v))


def select_interventions(state: dict[str, Any], safety_level: str="GREEN", history: list[dict[str,Any]]|None=None) -> dict[str,Any]:
    if safety_level.upper()=="RED":
        return {"actions":[],"mode":"safety_only","reason":"Urgent safety routing takes precedence over lifestyle interventions."}
    history=history or []
    recent={str(x.get("type")):x for x in history[-20:]}
    actions=[]
    deviations=state.get("deviations",{}) if isinstance(state,dict) else {}
    sleep=deviations.get("sleep_hours") or {}
    water=deviations.get("water_ml") or {}
    activity=deviations.get("activity_minutes") or {}
    if sleep.get("percent") is not None and sleep["percent"] < -15:
        actions.append({"type":"sleep","action":"protect_a consistent sleep window tonight","reason":"recent sleep is below the user's observed baseline","burden":"low"})
    if water.get("percent") is not None and water["percent"] < -20:
        actions.append({"type":"hydration","action":"add one planned water break","reason":"recent logged hydration is below baseline","burden":"low"})
    if activity.get("current") is not None and activity.get("baseline") is not None and activity["current"] < activity["baseline"]*0.7:
        actions.append({"type":"movement","action":"choose a short comfortable movement session","reason":"recent activity is below personal baseline","burden":"low"})
    actions=[a for a in actions if a["type"] not in recent]
    if not actions:
        actions=[{"type":"check_in","action":"log one meaningful health signal today","reason":"Bubbles has no high-confidence intervention gap from the current state","burden":"low"}]
    return {"actions":actions[:3],"mode":"supportive","personalized":True,"safety_level":safety_level,"note":"Suggestions are optional and are not medical treatment."}
