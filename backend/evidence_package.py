"""Context + evidence orchestrator contract. Pure functions: no database, no model call.

`plan_task` decides which engines a request needs (so greetings do not pull health records and "what is X" does not
trigger personal analysis). `build_package` combines the engines' outputs into ONE traceable structure that keeps
the four kinds of information separate, so the response layer cannot blur them:

  personal_facts      what the user said / logged (with assertion + time)      -> user_reported
  calculations        deterministic results with inputs, method, version       -> calculated
  observed_patterns   only candidate_association / repeated_pattern findings   -> statistical (never causal)
  retrieved_evidence  general knowledge with source + url + level + handling  -> external (NOT about the user)

It also records `facts_used` (for audit/debug without logging health text), the engine versions, and a `sufficiency`
verdict: when the request needs something that is missing, the package says so and `answerable` is False.

Wiring (not done yet): call plan_task in chat() before context building, pass real outputs to build_package, and give the
LLM only `render_for_model(package)`; store `facts_used`/`evidence_ids` in the reply metadata.
"""
from __future__ import annotations

import re
from typing import Any

VERSION = "1.0"
_FIRST = re.compile(r"\b(?:i|i'm|i've|my|me|mine|myself)\b", re.I)
_CALC = re.compile(r"\b(?:bmi|calories?|kcal|how many|how much|cycle length|period length|average|total|streak|deficit|bmr|tdee|protein|water intake|sleep debt)\b", re.I)
_PATTERN = re.compile(r"\b(?:why|pattern|trend|usually|always|often|link|related|connected|correlat\w*|every time|keep(?:s)? happening)\b", re.I)
_KNOWLEDGE = re.compile(r"\b(?:what is|what are|what does|is it normal|normal range|symptoms? of|causes? of|safe|side effects?|how (?:do|does|can|to)|should i|can i|is it ok|meaning|mean)\b", re.I)
_REPORTED = frozenset({"present", "negated", "possible", "resolved"})
_GREETING = re.compile(r"^\s*(?:hi|hello|hey|namaste|thanks?|thank you|ok(?:ay)?|good (?:morning|evening|night))\W*$", re.I)


def plan_task(message: str, *, has_health_topic: bool = False) -> dict[str, Any]:
    """Which engines does this request need? Safety always runs first and is not optional."""
    m = (message or "").strip()
    if _GREETING.match(m):
        return {"intent": "greeting", "safety": True, "personal_context": False, "calculation": False, "rag": False, "patterns": False}
    first = bool(_FIRST.search(m))
    return {
        "intent": "health_question" if (has_health_topic or _KNOWLEDGE.search(m) or first) else "chat",
        "safety": True,
        "personal_context": first or bool(_PATTERN.search(m)) or bool(_CALC.search(m) and first),
        "calculation": bool(_CALC.search(m)),
        "rag": has_health_topic or bool(_KNOWLEDGE.search(m)),
        "patterns": bool(_PATTERN.search(m)) and first,
    }


def _fact(f: dict) -> dict:
    return {"id": f.get("id") or f.get("concept"), "concept": f.get("concept"), "assertion": f.get("assertion"),
            "temporal": f.get("temporal_status") or f.get("temporal"), "source": f.get("source", "user_statement"), "origin": "user_reported"}


def build_package(*, plan: dict, safety: dict | None = None, personal_facts: list[dict] | None = None,
                  calculations: list[dict] | None = None, evidence: list[dict] | None = None,
                  patterns: list[dict] | None = None, history: list[dict] | None = None) -> dict[str, Any]:
    # only statements about the user themselves count as personal facts: questions, quotes, hypotheticals and other people do not
    facts = [_fact(f) for f in (personal_facts or []) if f.get("assertion") in _REPORTED and f.get("experiencer", "self") == "self"]
    calcs = list(calculations or [])
    ev = [{"chunk_id": e.get("chunk_id"), "document_id": e.get("document_id"), "title": e.get("title"), "source": e.get("source_name"),
           "url": e.get("source_url"), "evidence_level": e.get("evidence_level"), "handling": e.get("policy", "standard"),
           "origin": "external_general_knowledge"} for e in (evidence or [])]
    shown_patterns = [p for p in (patterns or []) if p.get("status") in ("candidate_association", "repeated_pattern")]
    uncertainties, limitations = [], []

    answerable = True
    if plan.get("calculation") and calcs and all(c.get("status") != "ok" for c in calcs):
        answerable = False
        uncertainties += [f"{c.get('calc_id')}: {c.get('status')} - {c.get('reason', '')}".strip() for c in calcs]
    if plan.get("rag") and not ev:
        limitations.append("No external evidence was retrieved. Do not invent citations or present general claims as established.")
    if plan.get("patterns") and not shown_patterns:
        uncertainties.append("Not enough reliable data to identify a pattern yet.")
    if plan.get("personal_context") and not facts and not calcs:
        uncertainties.append("No personal records were available for this question; missing data is not the same as a healthy result.")
    for p in shown_patterns:
        limitations += [x for x in p.get("limitations", []) if x not in limitations]

    used = [f["id"] for f in facts] + [c.get("calc_id") for c in calcs] + [e["chunk_id"] for e in ev if e.get("chunk_id")] + [p.get("label") for p in shown_patterns]
    return {
        "package_version": VERSION,
        "intent": plan.get("intent"),
        "engines_invoked": [k for k in ("safety", "personal_context", "calculation", "rag", "patterns") if plan.get(k)],
        "safety_assessment": safety or {},
        "personal_facts": facts,
        "calculations": calcs,
        "observed_patterns": shown_patterns,
        "retrieved_evidence": ev,
        "historical_context": list(history or []),
        "uncertainties": uncertainties,
        "limitations": limitations,
        "sufficiency": {"answerable": answerable and not (plan.get("rag") and not ev and not any(c.get("status") == "ok" for c in calcs)),
                        "needs": [k for k, missing in (("calculation", bool(plan.get("calculation")) and not any(c.get("status") == "ok" for c in calcs)),
                                                       ("evidence", bool(plan.get("rag")) and not ev)) if missing]},
        "facts_used": [u for u in used if u],
        "engine_versions": {"evidence_package": VERSION, "calc_ids": sorted({c.get("calc_id") for c in calcs if c.get("calc_id")}),
                            "calc_versions": sorted({f"{c.get('calc_id')}@{c.get('version')}" for c in calcs})},
    }


def package_audit(pkg: dict) -> dict[str, Any]:
    """The part of a package that is safe to store with a reply: ids, labels, versions and verdicts. No free text from the user."""
    return {"version": pkg["package_version"], "intent": pkg["intent"], "engines": pkg["engines_invoked"], "facts_used": pkg["facts_used"][:40],
            "answerable": pkg["sufficiency"]["answerable"], "needs": pkg["sufficiency"]["needs"], "uncertainties": len(pkg["uncertainties"]),
            "evidence": [{"chunk_id": e.get("chunk_id"), "handling": e.get("handling")} for e in pkg["retrieved_evidence"]],
            "engine_versions": pkg["engine_versions"]}


def render_for_model(pkg: dict) -> str:
    """Compact, labelled text for the model. Each kind of information keeps its own label."""
    out = [f"INTENT: {pkg['intent']}"]
    if pkg["personal_facts"]:
        out.append("USER-REPORTED FACTS (what the user said; check assertion and time): " + "; ".join(
            f"{f['concept']} [{f['assertion']}, {f['temporal']}]" for f in pkg["personal_facts"]))
    for c in pkg["calculations"]:
        out.append(f"CALCULATED ({c.get('calc_id')} v{c.get('version')}, status={c.get('status')}): value={c.get('value')} {c.get('unit', '')}; "
                   f"inputs={c.get('inputs')}; limits={c.get('limitations')}; reason={c.get('reason', '')}")
    for p in pkg["observed_patterns"]:
        out.append(f"OBSERVED PATTERN IN THE USER'S LOGS ({p.get('status')}, n={p.get('n')}, rho={p.get('rho')}): {p.get('label')}. " + " ".join(p.get("limitations", [])))
    for e in pkg["retrieved_evidence"]:
        out.append(f"GENERAL EVIDENCE (not about the user): {e['title']} - {e['source']} ({e['evidence_level']}) {e['url'] or ''} handling={e['handling']}")
    out += [f"UNCERTAIN: {u}" for u in pkg["uncertainties"]] + [f"LIMITATION: {x}" for x in pkg["limitations"]]
    if not pkg["sufficiency"]["answerable"]:
        out.append("INSUFFICIENT: say what is missing; do not estimate or invent values.")
    return "\n".join(out)
