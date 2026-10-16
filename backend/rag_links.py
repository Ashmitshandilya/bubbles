"""Links between the things a person logs, as a retrieval layer over documents ALREADY in the RAG store.

No new medical text is written here. LINK_DOCS names verified stored documents (by title prefix) that talk about how two areas
affect each other; tag_documents() adds a `link:<a>-<b>` topic tag to them (additive, idempotent, reversible: remove the tag).
Then:
  * detect(query)          which links a question is asking about ("does lack of sleep affect my mood" -> mood-sleep)
  * pair_id(x, y)          the link id for two logged series (the association engine's pairs)
  * evidence_for_pair(id)  the stored sources behind a link, for the "what published sources say" line under a pattern

Dry run by default:  python rag_links.py          (shows what would be tagged)   |   python rag_links.py --apply
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any

# link id (two domains, sorted) -> title prefixes of stored documents that support it
LINK_DOCS: dict[str, list[str]] = {
    "mood-sleep": ["Poor sleep and depression/anxiety are bidirectionally linked", "Low mood, sadness and depression: causes, treatment and self-care"],
    "activity-mood": ["Exercise for depression: causes, treatment and self-care", "Exercise for depression: overview", "Benefits of exercise: overview",
                      "Low mood, sadness and depression: causes, treatment and self-care"],
    "activity-sleep": ["Regular exercise improves sleep quality", "Benefits of exercise: overview"],
    "hydration-symptom": ["Dehydration: overview", "Dehydration symptoms: thirst"],
    "sleep-symptom": ["10 headache triggers: overview", "Heart palpitations: causes, treatment and self-care"],
    "food-sleep": ["Evidence-aligned sleep habits", "Alcohol may hasten sleep onset", "Up to 400 mg/day caffeine"],
    "heart-sleep": ["Heart palpitations: causes, treatment and self-care", "Adults need 7"],
    "cycle-mood": ["Mood changes before and during periods are common", "Common physical and emotional PMS symptoms"],
    "cycle-sleep": ["Sleep is often worse in the late luteal", "Women's sleep is affected"],
    "sleep-weight": ["Adults need 7", "Sleep apnoea: repeated breathing pauses"],
    "stress-weight": ["Chronic stress can increase appetite"],
    "cycle-stress": ["Acute stress can delay ovulation and the period", "Common reasons periods become irregular or stop"],
    "fatigue-sleep": ["Fatigue: definition and common causes"],
    "cycle-fatigue": ["Fatigue: definition and common causes", "Iron deficiency anaemia: overview", "Heavy periods: overview"],
    "fatigue-labs": ["Fatigue: definition and common causes", "Iron deficiency anaemia: overview", "Underactive thyroid (hypothyroidism): causes, treatment and self-care"],
    "labs-weight": ["Underactive thyroid (hypothyroidism): causes, treatment and self-care"],
    "cycle-labs": ["Heavy periods: overview", "Iron deficiency anaemia: overview", "Underactive thyroid (hypothyroidism): causes, treatment and self-care"],
    # nutrients, blood markers and hormones (documents added by rag_nutrient_ingest.py; see nutrient_manifest.json)
    "fatigue-nutrient": ["Fatigue: definition and common causes", "Iron deficiency anaemia: overview", "Ferritin blood test", "Iron tests",
                         "Vitamin B tests", "Vitamin D test", "Magnesium blood test"],
    "hair-iron": ["Iron deficiency anaemia: overview", "Ferritin blood test", "Iron tests", "Haemoglobin test"],
    "mood-vitamind": ["Vitamin D test", "Low mood, sadness and depression: causes, treatment and self-care"],
    "b12-diet": ["Vitamin B tests", "Homocysteine test"],
    "cycle-thyroid": ["Underactive thyroid (hypothyroidism): causes, treatment and self-care", "TSH (thyroid stimulating hormone) test",
                      "Hypothyroidism (underactive thyroid)", "Hyperthyroidism (overactive thyroid)", "Common reasons periods become irregular or stop"],
    "cycle-hormones": ["Testosterone test", "Estrogen test", "Progesterone test", "Prolactin test", "FSH (follicle stimulating hormone) test",
                       "PCOS (polycystic ovary syndrome)", "Common reasons periods become irregular or stop"],
}
LINK_QUERY = {
    "mood-sleep": "sleep and mood link", "activity-mood": "exercise and mood", "activity-sleep": "exercise and sleep",
    "hydration-symptom": "dehydration symptoms headache", "sleep-symptom": "sleep and headache triggers", "food-sleep": "caffeine alcohol meals and sleep",
    "heart-sleep": "sleep and heart rate palpitations", "cycle-mood": "menstrual cycle and mood", "cycle-sleep": "menstrual cycle and sleep",
    "sleep-weight": "sleep and weight", "stress-weight": "stress and weight appetite", "cycle-stress": "stress and periods",
    "fatigue-sleep": "tiredness and sleep", "cycle-fatigue": "heavy periods tiredness iron",
    "fatigue-labs": "tiredness anaemia thyroid", "labs-weight": "underactive thyroid weight gain", "cycle-labs": "periods anaemia thyroid",
    "fatigue-nutrient": "tiredness vitamin or mineral deficiency blood test", "hair-iron": "hair fall iron ferritin",
    "mood-vitamind": "vitamin D and mood", "b12-diet": "vitamin B12 vegetarian vegan diet", "cycle-thyroid": "thyroid and periods", "cycle-hormones": "hormones and periods pcos",
}
SERIES_DOMAIN = {"sleep_hours": "sleep", "sleep_quality": "sleep", "mood": "mood", "activity_minutes": "activity", "hydration_ml": "hydration",
                 "symptom_severity": "symptom", "calories": "food", "resting_hr": "heart", "luteal": "cycle"}
_WORDS = {   # English + common Hinglish
    "sleep": r"sleep|slept|insomnia|bedtime|neend|\bnaps?\b",
    "mood": r"mood|depress|\bsad\b|anxi|udaas|mental health",
    "stress": r"stress|worr(?:y|ied)|tension|burnout",
    "activity": r"exercis|workout|\bwalk|\bgym\b|\bactive\b|activity|yoga|running|sports?\b",
    "hydration": r"\bwater\b|hydrat|dehydrat|\bdrink|fluids?\b|thirst|\bpani\b",
    "symptom": r"headache|migraine|\bpain\b|symptom|nausea|dizz",
    "heart": r"heart ?rate|heartbeat|palpitation|\bpulse\b|blood pressure|\bbp\b|dhadkan",
    "food": r"\bfood\b|\bmeals?\b|\beat(?:ing)?\b|calorie|\bdiet\b|caffeine|coffee|\btea\b|alcohol|khana",
    "cycle": r"\bperiods?\b|menstru|\bpms\b|luteal|ovulat|menopause|pcos|\bcycle\b",
    "weight": r"weight|obes|overweight|\bbmi\b",
    "fatigue": r"\btired|fatigue|exhaust|low energy|thakan|kamzori|weakness",
    "labs": r"thyroid|anaemi|anemi|\biron\b|vitamin d|\bb12\b|haemoglobin|hemoglobin|\bhb\b",
}
_RX = {k: re.compile(v, re.I) for k, v in _WORDS.items()}


def pair_id(x: str, y: str) -> str | None:
    """Link id for two logged series (e.g. 'sleep_hours', 'mood' -> 'mood-sleep'); None when no sources are tagged for it."""
    dx, dy = SERIES_DOMAIN.get(x), SERIES_DOMAIN.get(y)
    pid = "-".join(sorted((dx, dy))) if dx and dy and dx != dy else None
    return pid if pid in LINK_DOCS else None


def detect(query: str, limit: int = 2) -> list[str]:
    """Links a question is about: those where BOTH areas are mentioned. Plain keyword matching, no model."""
    present = [d for d, rx in _RX.items() if rx.search(query or "")]
    if len(present) < 2:
        return []
    hits = [pid for pid in LINK_DOCS if all(d in present for d in pid.split("-"))]
    return hits[:limit]


def tag_documents(db: Any, apply: bool = False) -> dict[str, Any]:
    """Add the link:<id> topic tag to the stored documents named in LINK_DOCS. Returns what was (or would be) changed."""
    changed: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []
    for pid, prefixes in LINK_DOCS.items():
        tag = f"link:{pid}"
        for prefix in prefixes:
            docs = db.table("rag_documents").select("id,title,topic_tags").like("title", prefix + "%").execute().data or []
            if not docs:
                missing.append((pid, prefix))
            for d in docs:
                tags = list(d.get("topic_tags") or [])
                if tag in tags:
                    continue
                changed.append((pid, d["title"][:70]))
                if apply:
                    db.table("rag_documents").update({"topic_tags": tags + [tag]}).eq("id", d["id"]).execute()
    return {"applied": apply, "tagged": len(changed), "changed": changed, "missing": missing}


_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_lock = threading.Lock()
TTL_SECONDS = 24 * 3600


def evidence_for_pair(pid: str, search=None, limit: int = 2) -> list[dict[str, Any]]:
    """Stored sources behind a link: [{title, source_name, source_url, snippet}]. Cached; [] when nothing is tagged or search fails."""
    with _lock:
        hit = _cache.get(pid)
    if hit and time.monotonic() - hit[0] < TTL_SECONDS:
        return hit[1]
    out: list[dict[str, Any]] = []
    try:
        if search is None:
            from rag import hybrid_search as search  # late: needs the service key
        for r in search(query=LINK_QUERY.get(pid, pid.replace("-", " and ")), topic=f"link:{pid}", limit=limit):
            out.append({"title": r.get("title"), "source_name": r.get("source_name"), "source_url": r.get("source_url"),
                        "snippet": " ".join(str(r.get("content") or "").split())[:240]})
    except Exception:  # noqa: BLE001 - evidence is an extra; the pattern is still shown without it
        return []
    with _lock:
        _cache[pid] = (time.monotonic(), out)
    return out


if __name__ == "__main__":
    import sys

    import rag

    res = tag_documents(rag._db(), apply="--apply" in sys.argv)
    print("APPLIED" if res["applied"] else "DRY RUN", "- documents to tag:", res["tagged"])
    for pid, title in res["changed"]:
        print("  ", pid, "<-", title)
    for pid, prefix in res["missing"]:
        print("   MISSING", pid, prefix)
