from personalization_engine import build_personalization
from habit_intelligence import analyze_habits
from mental_wellness_intelligence import assess_wellbeing
from womens_health_intelligence import classify_womens_health
from medication_intelligence import medication_overview
from preventive_health import preventive_snapshot
from sharing_architecture import build_share_plan
from provider_integration import to_fhir_resource
from advanced_agent import plan_agent
from knowledge_learning import knowledge_health
from production_hardening import readiness_report
from memory_manager import extract_explicit_personal_facts
from response_formatter import normalize_response

def test_identity_extraction():
    facts=extract_explicit_personal_facts("My name is Ashmit.")
    assert facts and facts[0]["key"]=="name" and facts[0]["value"]=="Ashmit"

def test_explicit_personal_facts():
    facts=extract_explicit_personal_facts("I live in Chennai and I work as a student.")
    assert {f["key"] for f in facts} >= {"location","occupation"}

def test_response_format():
    friendly="First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    assert normalize_response(friendly)==friendly            # a conversational paragraph is never turned into bullets
    assert normalize_response("A\n\n\n\nB")=="A\n\nB"
    assert normalize_response("  ")

def test_personalization():
    assert build_personalization({"full_name":"Ashmit"},{},[] )["style"]=="warm_formal"

def test_habits():
    assert analyze_habits([{"event_type":"sleep"}])["domains"][0]["domain"]=="sleep"

def test_wellness():
    assert assess_wellbeing([{"event_type":"mood","extracted_data":{"severity":"low"}}])["mood_observations"]

def test_womens_health():
    assert "topics" in classify_womens_health([{"event_type":"cycle","extracted_data":{}}])

def test_medications():
    assert medication_overview([{"event_type":"medication","extracted_data":{"name":"X"}}])["medications"]==["X"]

def test_preventive():
    assert "needs_context" in preventive_snapshot({},[])

def test_sharing_default_deny():
    assert build_share_plan(["labs"],{})["allowed"]==[]

def test_fhir():
    assert to_fhir_resource({"event_type":"lab_result","id":"1"})["resourceType"]=="Observation"

def test_agent_safety():
    assert plan_agent({}, {}, "RED")["actions"]==[]

def test_knowledge():
    assert knowledge_health([])["source_count"]==0

def test_readiness_shape():
    assert "checks" in readiness_report()
