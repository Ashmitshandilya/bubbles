"""Batch 33: long-term Bubbles agent planning with explicit autonomy boundaries."""
from __future__ import annotations
from typing import Any

AUTONOMY_LEVELS=("off","suggest","confirm","limited_auto")

def plan_agent_actions(twin:dict[str,Any], safety_level:str="GREEN", autonomy:str="suggest") -> dict[str,Any]:
    autonomy=autonomy if autonomy in AUTONOMY_LEVELS else "suggest"
    if safety_level.upper()=="RED":
        return {"actions":[],"autonomy":autonomy,"mode":"safety_override","reason":"Safety escalation takes precedence over agent actions."}
    gaps=[k for k,v in (twin.get("domains") or {}).items() if v.get("status")=="insufficient_data"]
    actions=[]
    if gaps: actions.append({"type":"data_gap","action":"invite the user to log one missing high-value signal","domain":gaps[0],"requires_confirmation":True})
    actions.append({"type":"follow_up","action":"check whether the user wants to revisit the most recent health concern","requires_confirmation":True})
    return {"actions":actions[:2],"autonomy":autonomy,"mode":"user_controlled","guardrails":["no diagnosis","no emergency delay","no medication changes","no external disclosure without consent"]}
