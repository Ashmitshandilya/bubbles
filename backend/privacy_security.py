
"""Batch 25: consent, minimization and redaction primitives.

This is intentionally storage-neutral: it can operate with the existing 20-table
schema without inventing a second privacy database. In production, authorization,
RLS and secrets remain the enforcement boundary.
"""
from __future__ import annotations
import re
SENSITIVE_PATTERNS=[
 (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'),"[EMAIL REDACTED]"),
 (re.compile(r'\b(?:\+?91[-\s]?)?[6-9]\d{9}\b'),"[PHONE REDACTED]"),
 (re.compile(r'\b(?:\d[ -]*?){13,19}\b'),"[NUMBER REDACTED]"),
]
def redact(text:str)->str:
    out=str(text or "")
    for p,r in SENSITIVE_PATTERNS: out=p.sub(r,out)
    return out
def consent_policy(consent:dict|None, purpose:str)->dict:
    c=consent or {}
    allowed=bool(c.get(purpose,False))
    return {"purpose":purpose,"allowed":allowed,"decision":"allow" if allowed else "deny",
            "principles":["purpose limitation","data minimization","least privilege","explicit user control"]}
def minimize_payload(payload:dict,allowed_fields:set[str])->dict:
    return {k:v for k,v in payload.items() if k in allowed_fields}
def security_headers()->dict:
    return {"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","X-Frame-Options":"DENY",
            "Strict-Transport-Security":"max-age=31536000; includeSubDomains","Permissions-Policy":"camera=(), microphone=(), geolocation=()"}
def threat_check()->dict:
    return {"status":"baseline","controls":["bearer auth","server-side authorization","RLS","no secrets in client bundle","redaction before external model calls"],"note":"Review deployment-specific headers, CORS and key rotation before production."}
