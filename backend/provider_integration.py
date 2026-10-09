"""Batch 42: clinician/provider exchange adapters and FHIR mapping contracts."""
from __future__ import annotations
from typing import Any

from event_filters import clean_data, counts_as_observation
from interoperability import is_denial, verification_status

FHIR_MAP={"profile":"Patient","vital_sign":"Observation","lab_result":"Observation","medical_condition":"Condition",
          "medication":"MedicationStatement","doctor_visit":"Encounter","allergy":"AllergyIntolerance",
          "medical_report":"DiagnosticReport","doctor_appointment":"Appointment"}
def to_fhir_resource(event:dict[str,Any])->dict[str,Any]:
    typ=str(event.get("event_type") or "").lower()
    denial=is_denial(event)
    if not denial and not counts_as_observation(event):
        # rejected / hypothetical / other-person / screen rows are never exchanged
        return {"resourceType":"OperationOutcome","issue":[{"severity":"information","code":"not-supported","diagnostics":"event is not an exportable live observation"}]}
    resource="Observation" if denial else FHIR_MAP.get(typ,"Observation")
    d=clean_data(event.get("extracted_data") if isinstance(event.get("extracted_data"),dict) else {})
    status=verification_status(event)
    out={"resourceType":resource,"status":"unknown","code":{"text":typ},"value":d,
         "verificationStatus":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/condition-ver-status","code":status}],"text":status},
         "provenance":{"source":"bubbles","source_event_id":event.get("id")}}
    if denial: out["valueCodeableConcept"]={"text":"absent"}
    return out
