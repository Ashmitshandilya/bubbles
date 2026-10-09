from datetime import datetime, timedelta, timezone
from health_state_engine import build_health_state
from learning_engine import build_learning_snapshot, reconcile_fact
from companion_engine import build_daily_companion

def _e(t, data, d, c=.9):
    return {"event_type":t,"extracted_data":data,"created_at":(datetime.now(timezone.utc)-timedelta(days=d)).isoformat(),"confidence":c,"id":f"{t}-{d}"}

def test_health_state_detects_recent_sleep_and_gap():
    rows=[_e("sleep",{"hours":5},1),_e("sleep",{"hours":6},2),_e("hydration",{"water_ml":1800},1)]
    s=build_health_state(rows,days=7)
    assert s["event_count"]==3
    assert "mood" in s["data_gaps"]

def test_learning_creates_candidate_for_recurrence():
    rows=[_e("symptom",{"symptom":"headache"},1),_e("symptom",{"symptom":"headache"},3),_e("symptom",{"symptom":"headache"},5)]
    l=build_learning_snapshot(rows)
    assert l["memory_candidates"]
    assert l["memory_candidates"][0]["memory_level"]=="L3"

def test_reconcile_conflict_preserves_uncertainty():
    r=reconcile_fact({"x":1},{"x":2})
    assert r["action"]=="review"

def test_companion_requests_missing_signals():
    s={"status":"limited","data_gaps":["sleep_hours","mood"],"deviations":{}}
    c=build_daily_companion(s,{})
    assert len(c["focus"])==2
