"""Fitness and recovery intelligence from logged activity/exercise events."""
from datetime import datetime,timezone,timedelta
from collections import defaultdict
def _num(d,*keys):
    for k in keys:
        v=d.get(k)
        try:
            if isinstance(v,bool) or v is None: continue
            return float(v)
        except (TypeError,ValueError): pass
    return None
def analyze_fitness(events,days=30):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,days)); minutes=0.; sessions=0; intensity=[]; types=defaultdict(int)
    for e in events:
        try: dt=datetime.fromisoformat(str(e.get("created_at")).replace("Z","+00:00"))
        except Exception: continue
        if dt<cutoff: continue
        d=e.get("extracted_data") or e.get("data") or {}
        if not isinstance(d,dict): continue
        kind=str(e.get("event_type") or d.get("type") or "").lower()
        if any(x in kind for x in ("exercise","activity","workout","fitness")):
            sessions+=1; m=_num(d,"minutes","duration_minutes","active_minutes","duration")
            if m is not None: minutes+=m
            i=_num(d,"intensity","intensity_score","rpe")
            if i is not None:intensity.append(i)
            types[str(d.get("activity") or d.get("exercise") or kind)]+=1
    return {"window_days":days,"sessions":sessions,"total_minutes":round(minutes,1),
            "average_session_minutes":round(minutes/sessions,1) if sessions else None,
            "average_intensity":round(sum(intensity)/len(intensity),2) if intensity else None,
            "activity_types":dict(types),"data_gaps":[] if sessions else ["exercise/activity"],
            "interpretation":"Fitness summaries describe logged activity. Training advice should account for recovery, symptoms, medications, and clinician guidance when relevant."}
