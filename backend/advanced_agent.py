"""Batch 43: bounded agent planning with explicit approval gates."""
from __future__ import annotations
from typing import Any

def plan_agent(twin:dict[str,Any], interventions:dict[str,Any], safety:str="GREEN", autonomy:str="suggest")->dict[str,Any]:
    if safety.upper()=="RED": return {"mode":"safety_override","actions":[],"requires_human":"urgent safety handling"}
    actions=[]
    for item in (interventions.get("recommendations") or [])[:3]:
        actions.append({"action":item,"approval_required":autonomy!="limited_auto","external_side_effect":False})
    return {"mode":"bounded_agent","autonomy":autonomy,"actions":actions,"guardrails":["no diagnosis","no medication changes","no external sharing without consent","user can revoke autonomy"]}
