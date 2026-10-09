"""Bubbles daily companion planner.

Converts the health-state and learning outputs into a small, safe daily plan.
It never diagnoses and never presents correlations as causes.
"""
from __future__ import annotations
from datetime import datetime, timezone

def build_daily_companion(state, learning=None):
    actions=[]
    gaps=state.get("data_gaps") or []
    if isinstance(gaps, dict):  # normalized state wraps the list as {"gaps": [...]}
        gaps=gaps.get("gaps") or []
    deviations=state.get("deviations",{})
    if "sleep_hours" in gaps: actions.append({"kind":"check_in","area":"sleep","reason":"How did you sleep last night?"})
    if "water_ml" in gaps: actions.append({"kind":"check_in","area":"hydration","reason":"About how much water have you had today?"})
    if "mood" in gaps: actions.append({"kind":"check_in","area":"mood","reason":"How are you feeling today, emotionally?"})
    for name,d in (deviations or {}).items():
        if isinstance(d, dict) and d.get("percent") is not None and abs(d["percent"])>=20:
            actions.append({"kind":"observation","area":name,"reason":f"Your recent {name.replace('_',' ')} differs from your recent personal baseline."})
    for priority, action in enumerate(actions, start=1):
        action["priority"]=priority
    candidates=(learning or {}).get("memory_candidates",[])
    return {
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "headline":"Your Bubbles daily check-in",
      "state_status":state.get("status","limited"),
      "focus":actions[:5],
      "learning_signals":len(candidates),
      "data_gaps":list(gaps),
      "safety_note":"If symptoms are severe, rapidly worsening, or feel urgent, seek appropriate medical care rather than relying on Bubbles.",
      "disclaimer":"Daily guidance is based on logged data and is not a diagnosis or proof of causation."
    }
