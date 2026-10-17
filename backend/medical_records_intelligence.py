
"""Batch 21: safe medical-record/lab/report normalization using existing tables."""
from __future__ import annotations
from collections import Counter

def _label(row:dict)->str:
    return str(row.get("title") or row.get("name") or row.get("test_name") or row.get("report_name") or row.get("event_type") or "record")
def _lab_flag(x: dict) -> str:
    """The abnormal flag of one lab row: the stored flag, else derived from the range the user entered."""
    flag = str(x.get("abnormal_flag") or x.get("flag") or x.get("status") or "").strip().lower()
    if flag in {"high", "low", "abnormal", "critical", "positive"}:
        return flag
    try:
        value = float(x.get("value"))
        low = x.get("reference_min")
        high = x.get("reference_max")
        if low is not None and value < float(low):
            return "low"
        if high is not None and value > float(high):
            return "high"
    except (TypeError, ValueError):
        pass
    return ""


def summarize(records:list[dict], labs:list[dict]|None=None, reports:list[dict]|None=None)->dict:
    labs=labs or []; reports=reports or []
    abnormal=[]
    for x in labs:
        flag=_lab_flag(x)
        if flag:
            abnormal.append({"label":_label(x),"flag":flag,"value":x.get("value"),"unit":x.get("unit"),
                             "date":x.get("tested_at") or x.get("test_date") or x.get("created_at")})
    categories=Counter(str(x.get("report_type") or x.get("type") or x.get("category") or "other") for x in records)
    return {"record_count":len(records),"lab_count":len(labs),"report_count":len(reports),
            "record_categories":dict(categories),"flagged_labs":abnormal,
            "document_checklist":[{"item":"report/date identified","status":"verify"},{"item":"provider/facility identified","status":"verify"},{"item":"reference range retained","status":"verify"},{"item":"units retained","status":"verify"}],
            "limitations":["A flagged result is not interpreted as a diagnosis.","Reference ranges vary by laboratory and context.","Uploaded reports should be reviewed against the original document."]}
def extract_questions(records:list[dict],labs:list[dict]|None=None)->list[str]:
    out=["What does this result/report measure, and what was the reference range?","Which findings need follow-up and on what timeframe?"]
    for x in (labs or [])[:8]:
        if _lab_flag(x): out.append(f"What should I ask about the { _label(x) } result and its flagged status?")
    return list(dict.fromkeys(out))
