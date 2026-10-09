"""Bubbles memory manager: explicit personal facts + auditable diagnostics.

Uses the existing memory_items table when available and never treats absence of
data as a negative fact. Health-sensitive facts can require confirmation.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from event_filters import counts_as_observation

# A capture is at most 4 words and never crosses , . ? ! or a line break.
_WORD = r"[A-Za-z][A-Za-z'-]*"
_PHRASE = rf"({_WORD}(?:[ \t]+{_WORD}){{0,3}})"
FACT_PATTERNS=(
    ("name", rf"\bmy name is\s+{_PHRASE}", "The user's preferred name is {value}."),
    ("name", rf"\bcall me\s+{_PHRASE}", "The user prefers to be called {value}."),
    ("location", rf"\bI live in\s+{_PHRASE}", "The user says they live in {value}."),
    ("occupation", rf"\bI work as\s+(?:a\s+|an\s+)?{_PHRASE}", "The user says they work as {value}."),
    ("study", rf"\bI(?:'m| am) studying\s+{_PHRASE}", "The user says they are studying {value}."),
)
_STOP_WORDS=frozenset({"and","but","so","because","who","which"})
# "call me back / later / when ..." is a request, not a name
_NOT_NAMES=frozenset({"when","if","back","later","tomorrow","today","tonight","now","soon","again","at","on","as","in","whenever","anytime"})
_NEGATOR=re.compile(r"\b(?:don'?t|do not|doesn'?t|did not|didn'?t|never|not|no longer|stop(?:ped)?|won'?t|can'?t|cannot|isn'?t|aren'?t)\b",re.I)
_HYPOTHETICAL=re.compile(r"\b(?:if|suppose|supposing|should i|would i|could i|imagine|pretend|hypothetically|let'?s say)\b",re.I)

def _is_hedged(text:str, m:re.Match)->bool:
    """True when the match is negated, hypothetical, a question, or quoted rather than a plain first-person statement."""
    start=m.start()
    boundary=max(text.rfind(c,0,start) for c in ".!?\n")+1  # same sentence only
    before=text[max(boundary,start-30):start]
    if _NEGATOR.search(before) or _HYPOTHETICAL.search(before): return True
    lead=text[:start]
    if lead.count('"')%2==1 or lead.count("\u201c")>lead.count("\u201d"): return True
    end=re.search(r"[,.;!?\n]",text[m.end():])  # the clause the fact sits in
    return bool(end and end.group()=="?")

def extract_explicit_personal_facts(text:str)->list[dict[str,Any]]:
    text=(text or "").replace("\u2019","'")
    out=[]; seen=set()
    for key, pat, template in FACT_PATTERNS:
        for m in re.finditer(pat,text,re.I):
            if _is_hedged(text,m): continue
            words=[]
            for w in m.group(1).split():
                if w.lower() in _STOP_WORDS: break
                words.append(w)
            if not words or (key=="name" and words[0].lower() in _NOT_NAMES): continue
            value=" ".join(words)
            marker=(key,value.lower())
            if marker not in seen:
                seen.add(marker)
                out.append({"key":key,"value":value,"content":template.format(value=value),"confidence":0.98 if key!="name" else 0.99})
            break
    return out

def persist_explicit_facts(user_id:str, message_id:str|None, facts:list[dict[str,Any]])->list[dict[str,Any]]:
    from supabase_client import supabase
    saved=[]
    now=datetime.now(timezone.utc)
    for fact in facts:
        try:
            existing=(supabase.table("memory_items")
                      .select("id,content,structured_data,verification_status")
                      .eq("user_id",user_id).eq("memory_type","L2").eq("is_active",True)
                      .limit(200).execute().data or [])
            same_key=[x for x in existing if (x.get("structured_data") or {}).get("key")==fact["key"]]
            duplicate=next((x for x in same_key if str((x.get("structured_data") or {}).get("value","")).strip().casefold() == str(fact["value"]).strip().casefold()),None)
            review_days={"name":365,"location":365,"occupation":180,"study":180}.get(fact["key"],365)
            review_after=(now + timedelta(days=review_days)).isoformat()
            payload={
                "content":fact["content"],
                "structured_data":{"key":fact["key"],"value":fact["value"],"source":"explicit_user_statement","source_message_id":message_id},
                "source_type":"user_statement",
                "source_id":message_id,
                "confidence":fact["confidence"],
                "verification_status":"user_confirmed",
                "last_confirmed_at":now.isoformat(),
                "review_after":review_after,
                "is_active":True,
                "updated_at":now.isoformat(),
            }
            if duplicate:
                res=supabase.table("memory_items").update(payload).eq("id",duplicate["id"]).eq("user_id",user_id).execute()
                saved.append({"key":fact["key"],"memory_id":duplicate["id"],"action":"confirmed"})
                continue

            # A new value for the same key is a correction, not a silent overwrite.
            previous=same_key[0] if same_key else None
            res=supabase.table("memory_items").insert({"user_id":user_id,"memory_type":"L2",**payload}).execute()
            if res.data:
                new_id=res.data[0].get("id")
                if previous and new_id:
                    supabase.table("memory_items").update({
                        "is_active":False, "verification_status":"superseded",
                        "superseded_by":new_id, "updated_at":now.isoformat()
                    }).eq("id",previous["id"]).eq("user_id",user_id).execute()
                    supabase.table("memory_items").update({
                        "supersedes_memory_id":previous["id"]
                    }).eq("id",new_id).eq("user_id",user_id).execute()
                    action="superseded"
                else:
                    action="created"
                saved.append({"key":fact["key"],"memory_id":new_id,"action":action})
        except Exception as e:
            from logging_util import logger
            logger.error(
                component="MEMORY_MANAGER",
                operation="persist_explicit_facts",
                error=e,
                user_id=user_id,
                context={"fact_key": fact.get("key")},
                fallback_action="skipping_fact",
            )
    return saved

def memory_diagnostics(user_id:str)->dict[str,Any]:
    from supabase_client import supabase
    result={"L1":0,"L1_confirmed":0,"L1_pending":0,"L2":0,"L3":0,"name":None,"recent":[],"errors":[]}
    try:
        rows=supabase.table("extracted_health_events").select("id,event_type,extracted_data,confidence,created_at,extraction_status,user_confirmed").eq("user_id",user_id).order("created_at",desc=True).limit(200).execute().data or []
        rows=[r for r in rows if counts_as_observation(r)]  # rejected / denied / hedged rows are not memory
        result["L1"]=len(rows); result["recent"]=rows[:10]
        result["L1_confirmed"]=sum(1 for r in rows if r.get("user_confirmed") or r.get("extraction_status")=="confirmed")
        result["L1_pending"]=len(rows)-result["L1_confirmed"]
    except Exception as e:
        from logging_util import logger
        logger.error(
            component="MEMORY_MANAGER",
            operation="memory_diagnostics_l1",
            error=e,
            user_id=user_id,
            fallback_action="setting_l1_to_zero",
        )
        result["errors"].append("L1: unavailable")
    try:
        rows=supabase.table("memory_items").select("id,memory_type,content,structured_data,confidence,created_at,updated_at").eq("user_id",user_id).eq("is_active",True).order("updated_at",desc=True).limit(200).execute().data or []
        for r in rows:
            if r.get("memory_type") in result: result[r["memory_type"]]+=1
            sd=r.get("structured_data") or {}
            if sd.get("key")=="name": result["name"]=sd.get("value")
    except Exception as e:
        from logging_util import logger
        logger.error(
            component="MEMORY_MANAGER",
            operation="memory_diagnostics_l2_l3",
            error=e,
            user_id=user_id,
            fallback_action="setting_l2_l3_to_zero",
        )
        result["errors"].append("L2/L3: unavailable")
    return result
