
"""Batch 22: clinician-ready timeline and visit preparation."""
from __future__ import annotations
from collections import defaultdict

from event_filters import DEAD_STATUSES, clean_data, counts_as_observation, event_moment, pertinent_negatives


def build_timeline(events:list[dict],limit:int=300)->dict:
    """Live positive observations as `events`; explicit denials as a separate `pertinent_negatives` list."""
    rows=[]; negatives=[]; seen=set()
    for e in events:
        if not isinstance(e,dict): continue
        status=e.get("extraction_status") or "pending"
        if status in DEAD_STATUSES: continue
        for concept in pertinent_negatives(e):
            key=concept.strip().casefold()
            if key and key not in seen:
                seen.add(key); negatives.append(concept.strip())
        if not counts_as_observation(e): continue
        moment=event_moment(e)
        data=e.get("extracted_data") if isinstance(e.get("extracted_data"),dict) else {}
        rows.append({"id":e.get("id"),"date":moment.isoformat() if moment else e.get("created_at"),"recorded_at":e.get("created_at"),
                     "event_type":e.get("event_type"),"details":clean_data(data),"confidence":e.get("confidence"),
                     "extraction_status":status,"user_confirmed":bool(e.get("user_confirmed"))})
    rows.sort(key=lambda x:str(x.get("date") or ""),reverse=True)
    return {"events":rows[:max(1,min(limit,1000))],"count":len(rows),"pertinent_negatives":negatives}
def prepare_visit(events:list[dict],concern:str|None=None)->dict:
    timeline=build_timeline(events,200)
    types=defaultdict(int)
    for e in timeline["events"]: types[str(e["event_type"])] += 1
    questions=["What are the main possible explanations you are considering?","What tests or monitoring would help clarify this?","What symptoms or changes should prompt earlier review?","What should I track before the next appointment?"]
    return {"visit_summary":{"concern":concern or "user-selected concern","event_count":timeline["count"],"frequent_event_types":sorted(types.items(),key=lambda x:x[1],reverse=True)[:10]},
            "timeline":timeline,"questions":questions,
            "bring":["medication/supplement list","allergies","recent reports/labs","symptom and cycle dates where relevant"],
            "note":"This is preparation support, not a substitute for clinical assessment."}
