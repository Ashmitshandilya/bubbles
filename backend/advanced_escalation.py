
"""Batch 23: layered safety/escalation policy."""
from __future__ import annotations
from safety_engine import assess_safety

def evaluate(message:str, context:dict|None=None)->dict:
    a=assess_safety(message)
    level=a.level
    action={"GREEN":"normal_support","AMBER":"timely_professional_review","RED":"urgent_or_emergency_assessment"}[level]
    if level=="RED":
        next_step="If this may be immediately life-threatening, contact local emergency services now."
    elif level=="AMBER":
        next_step="Consider timely medical assessment and seek urgent care if symptoms worsen or new red flags appear."
    else:
        next_step="Continue monitoring and seek professional care if symptoms are severe, persistent, or worsening."
    # `state` and `facts` expose what was understood (negated / hypothetical / past / ...) and why, for
    # development and audit. Facts carry reason codes only, never the user's text.
    return {"level":level,"state":a.state,"reasons":list(a.reasons),"action":action,"next_step":next_step,
            "facts":[f.to_dict() for f in a.facts][:40],
            "context_used":bool(context),"no_diagnosis":True,
            "limitations":["Deterministic screening can miss emergencies; absence of a trigger is not proof of safety."]}
