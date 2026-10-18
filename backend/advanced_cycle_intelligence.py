"""Advanced cycle analytics using explicitly logged cycle events."""
from statistics import mean,pstdev
from cycle_intelligence import _data,_date,is_cycle_start
from event_filters import counts_as_observation
def analyze_advanced(events):
    starts=[]
    for e in events:
        if not isinstance(e,dict) or not counts_as_observation(e): continue
        d=_data(e); kind=str(e.get("event_type") or d.get("type") or "").lower()
        if ("period" in kind or "menstrual" in kind or "cycle" in kind) and is_cycle_start(d):
            x=_date(e,"start_date","period_start","cycle_start","date")
            if x: starts.append(x)
    starts=sorted(set(starts)); intervals=[(b-a).days for a,b in zip(starts,starts[1:]) if 1<=(b-a).days<=120]
    return {"period_starts":len(starts),"observed_intervals":intervals[-12:],
            "average_interval_days":round(mean(intervals),1) if intervals else None,
            "interval_variability_days":round(pstdev(intervals),1) if len(intervals)>=2 else None,
            "latest_start":starts[-1].isoformat() if starts else None,
            "forecast":None if not intervals else "Forecasting is withheld until enough consistent cycle-start data are available.",
            "data_quality":"At least 3 observed start-to-start intervals are preferred for a meaningful personal pattern.",
            "safety_note":"Cycle analytics are observations, not a diagnosis or fertility/medical prediction."}
