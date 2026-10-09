"""Batch 30: deterministic AI evaluation and release-gate primitives."""
from __future__ import annotations
from typing import Any

REQUIRED_GATES=("safety","grounding","privacy","schema","regression")

def evaluate_case(case:dict[str,Any], result:dict[str,Any]) -> dict[str,Any]:
    checks={
      "safety": bool(result.get("safety_ok", True)),
      "grounding": bool(result.get("grounded", not case.get("requires_evidence",False))),
      "privacy": not bool(result.get("leaked_sensitive_data",False)),
      "schema": bool(result.get("schema_valid",True)),
      "regression": bool(result.get("regression_ok",True)),
    }
    return {"passed":all(checks.values()),"checks":checks,"failed_gates":[k for k,v in checks.items() if not v]}


def release_gate(results:list[dict[str,Any]]) -> dict[str,Any]:
    total=len(results); passed=sum(1 for r in results if r.get("passed"))
    return {"release_allowed": total>0 and passed==total,"cases":total,"passed":passed,"failed":total-passed,"required_gates":list(REQUIRED_GATES)}


def model_audit(model:str, version:str, metrics:dict[str,float]|None=None) -> dict[str,Any]:
    return {"model":model,"version":version,"metrics":metrics or {},"policy":"pin versions for reproducibility; retain safety and grounding gates across model changes."}
