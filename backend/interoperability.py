"""Batch 29: storage-neutral FHIR interoperability mappings."""
from __future__ import annotations
from typing import Any

from event_filters import clean_data, counts_as_observation, event_moment, provenance

RESOURCE_MAP={
 "vital_sign":"Observation","lab_result":"Observation","symptom":"Condition","medical_condition":"Condition",
 "medication":"MedicationStatement","allergy":"AllergyIntolerance","doctor_visit":"Encounter","appointment":"Appointment",
 "medical_report":"DiagnosticReport","procedure":"Procedure","family_history":"FamilyMemberHistory",
}
_VER_STATUS_SYSTEM="http://terminology.hl7.org/CodeSystem/condition-ver-status"


def verification_status(event: dict[str,Any]) -> str:
    """`confirmed` only when the user confirmed the extracted event; everything else is `unconfirmed`."""
    return "confirmed" if event.get("user_confirmed") else "unconfirmed"


def is_denial(event: dict[str,Any]) -> bool:
    """The user explicitly said this was NOT present. Never exportable as a positive Condition."""
    data=event.get("extracted_data") or event.get("data") or {}
    return (isinstance(data,dict) and data.get("present") is False) or provenance(event).get("assertion")=="negated"


def to_fhir_resource(event: dict[str,Any]) -> dict[str,Any]:
    event_type=str(event.get("event_type") or "unknown").lower()
    denial=is_denial(event)
    resource_type="Observation" if denial else RESOURCE_MAP.get(event_type,"Observation")
    data=clean_data(event.get("extracted_data") if isinstance(event.get("extracted_data"),dict) else {})
    status=verification_status(event)
    resource={"resourceType":resource_type,"id":str(event.get("id") or ""),"meta":{"tag":[
        {"system":"https://bubbles.local/provenance","code":"bubbles-event"},
        {"system":"https://bubbles.local/verification","code":status}]}}
    moment=event_moment(event)
    if moment: resource["effectiveDateTime"]=moment.isoformat()
    elif event.get("created_at"): resource["effectiveDateTime"]=event["created_at"]
    if resource_type in {"Condition","AllergyIntolerance"}:
        resource["verificationStatus"]={"coding":[{"system":_VER_STATUS_SYSTEM,"code":status}],"text":status}
    if resource_type in {"Condition","Observation"}: resource["code"]={"text":str(data.get("name") or data.get("symptom") or event_type)}
    if denial: resource["valueCodeableConcept"]={"text":"absent"}
    if resource_type=="MedicationStatement": resource["medicationCodeableConcept"]={"text":str(data.get("name") or data.get("medication") or "unspecified")}
    if resource_type=="DiagnosticReport": resource["code"]={"text":str(data.get("title") or data.get("report_type") or "medical report")}
    return resource


def export_bundle(events:list[dict[str,Any]], bundle_type="collection") -> dict[str,Any]:
    """Only live positive observations are exported; rejected rows, denials and screens are not."""
    live=[e for e in events if isinstance(e,dict) and counts_as_observation(e)]
    return {"resourceType":"Bundle","type":bundle_type,"total":len(live),"entry":[{"resource":to_fhir_resource(e)} for e in live]}
