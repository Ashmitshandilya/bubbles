"""Batch 30/45 model governance contract.

Keeps model choice separate from clinical policy. A model can be swapped without
changing safety rules, memory semantics, or user data contracts.
"""
from __future__ import annotations
from typing import Any

CAPABILITIES={
 "reasoning":{"structured":"yes","health_sensitive":"allowed_only_if_configured","safety":"must_be_upstream"},
 "extraction":{"structured":"yes","health_sensitive":"allowed_only_if_configured","safety":"deterministic_validation"},
 "summarization":{"structured":"yes","health_sensitive":"allowed_only_if_configured","safety":"source_grounded"},
 "emergency_response":{"structured":"no","health_sensitive":"model_not_authoritative","safety":"deterministic"},
}
def model_contract(task:str, provider:str, model:str)->dict[str,Any]:
    cap=CAPABILITIES.get(task,CAPABILITIES["reasoning"])
    return {"task":task,"provider":provider,"model":model,"capability":cap,
            "requires_post_validation":True,"version":"bubbles-model-contract-v1"}
