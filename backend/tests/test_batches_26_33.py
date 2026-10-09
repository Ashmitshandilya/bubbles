from datetime import datetime, timezone, timedelta

from organ_intelligence import build_body_system_intelligence
from evidence_intelligence import build_grounding_packet, rank_evidence
from intervention_engine import select_interventions
from interoperability import export_bundle
from evaluation_governance import evaluate_case, release_gate
from multimodal_intelligence import inspect_media_metadata, voice_session_policy
from digital_twin import build_digital_twin
from health_agent import plan_agent_actions


def events():
    now=datetime.now(timezone.utc)
    return [
      {"id":"1","event_type":"sleep","created_at":(now-timedelta(days=1)).isoformat(),"extracted_data":{"hours":5}},
      {"id":"2","event_type":"hydration","created_at":(now-timedelta(days=2)).isoformat(),"extracted_data":{"water_ml":800}},
      {"id":"3","event_type":"smoking","created_at":now.isoformat(),"extracted_data":{"smoking":True}},
    ]


def test_body_system_intelligence_is_not_diagnosis():
    out=build_body_system_intelligence(events())
    assert out["total_systems"] > 0
    assert "diagnose" in out["interpretation"]


def test_evidence_ranking_and_grounding():
    items=[{"source_id":"a","title":"Guideline","source_type":"guideline","authority":1,"relevance":.9,"freshness":1}, {"source_id":"b","title":"Blog","source_type":"unknown","authority":.2,"relevance":.5,"freshness":1}]
    assert rank_evidence(items)[0]["source_id"]=="a"
    assert build_grounding_packet("q",items)["grounded"] is True


def test_intervention_red_safety_override():
    assert select_interventions({},"RED")["actions"] == []


def test_fhir_bundle():
    b=export_bundle(events())
    assert b["resourceType"]=="Bundle" and b["total"]==3


def test_evaluation_release_gate():
    r=evaluate_case({"requires_evidence":True},{"grounded":True})
    assert r["passed"] is True
    assert release_gate([r])["release_allowed"] is True


def test_multimodal_policy():
    assert inspect_media_metadata("image")["accepted"] is True
    assert inspect_media_metadata("executable")["accepted"] is False
    assert voice_session_policy()["consent_required"] is True


def test_twin_and_agent_user_control():
    state={"data_gaps":["sleep"],"deviations":{}}
    twin=build_digital_twin(state,{"data_quality":{"events_used":1}})
    plan=plan_agent_actions(twin,"GREEN","suggest")
    assert plan["mode"]=="user_controlled"
    assert plan["autonomy"]=="suggest"


def test_agent_red_override():
    twin=build_digital_twin({"data_gaps":[]}, {})
    assert plan_agent_actions(twin,"RED")["actions"]==[]
