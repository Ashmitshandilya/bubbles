
from sleep_recovery_intelligence import analyze as sleep
from longitudinal_health_analysis import analyze as longitudinal
from medical_records_intelligence import summarize, extract_questions
from doctor_timeline import build_timeline, prepare_visit
from advanced_escalation import evaluate
from ai_orchestrator import route, build_budget
from privacy_security import redact, consent_policy, minimize_payload

def events():
    return [
      {"id":"1","event_type":"sleep","created_at":"2099-01-01T00:00:00Z","extracted_data":{"duration_hours":7.5},"confidence":.9},
      {"id":"2","event_type":"stress","created_at":"2099-01-02T00:00:00Z","extracted_data":{"severity":4},"confidence":.8},
      {"id":"3","event_type":"exercise","created_at":"2099-01-02T00:00:00Z","extracted_data":{"duration_minutes":30},"confidence":.9},
      {"id":"4","event_type":"mood","created_at":"2099-01-03T00:00:00Z","extracted_data":{"score":3},"confidence":.7},
    ]

def test_sleep_recovery_has_signals():
    x=sleep(events(),30)
    assert x["sleep"]["observations"] >= 1
    assert "limitations" in x

def test_longitudinal_is_noncausal():
    x=longitudinal(events(),30)
    assert "domains" in x
    assert all("causal" in a["interpretation"] for a in x["temporal_associations"])

def test_medical_summary_does_not_diagnose():
    x=summarize([{"type":"lab"}],[{"test_name":"Hb","flag":"high","value":15}])
    assert x["flagged_labs"][0]["flag"]=="high"
    assert any("diagnosis" in s.lower() for s in x["limitations"])
    assert extract_questions([],[])

def test_doctor_timeline_and_visit():
    x=build_timeline(events())
    assert x["count"]==4
    v=prepare_visit(events(),"fatigue")
    assert v["visit_summary"]["concern"]=="fatigue"
    assert v["questions"]

def test_safety_is_layered():
    x=evaluate("I have severe chest pain and trouble breathing")
    assert x["level"] in {"RED","AMBER"}
    assert x["no_diagnosis"] is True

def test_ai_routing_never_models_red():
    x=route("RED","health","chat")
    assert x.provider=="deterministic"

def test_budget_is_numeric():
    x=build_budget(1000,500)
    assert x["estimated_cost_usd"] is None
    assert x["pricing_status"]=="unknown"
    assert x["estimated_input_tokens"]==1000

def test_privacy_primitives():
    x=redact("email ashmit@example.com phone +91 9876543210")
    assert "ashmit@example.com" not in x
    assert "[EMAIL REDACTED]" in x
    assert consent_policy({"medical_records":False},"medical_records")["decision"]=="deny"
    assert minimize_payload({"a":1,"b":2},{"a"})=={"a":1}
