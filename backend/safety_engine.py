"""Deterministic, semantics-aware safety triage for Bubbles' health conversations.

This is not a diagnostic engine. It is a conservative routing layer that decides
whether urgent language is *actually being asserted by the user about
themselves, now*, before any AI response is produced.

Decisions are made on structured facts (see ``health_semantics``), never on raw
keyword presence: a negated, hypothetical, quoted, historical or other-person
mention of "chest pain" does not escalate, while a bare "chest pain" or "I have
severe chest pain right now" does.

States (finest grain) map onto the legacy levels the rest of the app uses:

    NO_REDFLAG                              -> GREEN
    POTENTIAL_REDFLAG_NEEDS_CLARIFICATION   -> AMBER  (ask, do not alarm)
    URGENT                                  -> AMBER  (prompt professional assessment)
    EMERGENCY                               -> RED    (hard gate: deterministic copy, no AI)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

import locale_support

from health_semantics import (
    CRISIS, PAIN_CONCEPTS, POSSIBLE_IS_EMERGENCY, Fact, analyze, display_name, keyword_hits,
)

STATES = ("NO_REDFLAG", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", "URGENT", "EMERGENCY")
_RANK = {s: i for i, s in enumerate(STATES)}
_LEVEL = {
    "NO_REDFLAG": "GREEN",
    "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION": "AMBER",
    "URGENT": "AMBER",
    "EMERGENCY": "RED",
}
POTENTIAL = "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION"
#: red-flag *events* (not ongoing symptoms): when one has just ended it still needs assessment.
EVENT_LIKE = frozenset({"fainting", "seizure", "stroke_signs", "allergic_reaction"})
#: red-flag symptoms a user can describe as plainly mild ("a little tightness"): URGENT (get assessed today), not "call 112 now".
MILD_SOFT = frozenset({"chest_pain", "shortness_of_breath", "allergic_reaction"})
#: ...unless the same sentence carries a feature that makes a heart/airway/allergy emergency likely.
_ACS_FEATURES = re.compile(
    r"radiat|spread|\barm\b|\bjaw\b|sweat|clammy|nause|dizz|light[\s-]?head|faint|pass(?:ed|ing)? out|black(?:ed|ing)? out|"
    r"getting worse|worsen|\bworse\b|crushing|short(?:ness)? of breath|breathless|can't breathe|trouble breathing|difficulty breathing|"
    r"blue|swell|swollen|closing|hives", re.I)


@dataclass(frozen=True)
class SafetyAssessment:
    level: str
    reasons: tuple[str, ...]
    user_message: str
    state: str = "NO_REDFLAG"
    concepts: tuple[str, ...] = ()        # concepts that drove the state
    facts: tuple[Fact, ...] = ()          # every fact found (active or not)
    trace: tuple[dict, ...] = ()          # per-fact decision log (no user text)
    crisis: bool = False

    @property
    def active(self) -> bool:
        return self.state != "NO_REDFLAG"


def _tier(f: Fact) -> tuple[str | None, str]:
    """Effective tier/label: pain concepts with a severe qualifier become urgent."""
    if f.tier:
        return f.tier, f.label
    if f.concept in PAIN_CONCEPTS and (f.severity_label == "severe" or (f.severity or 0) >= 8):
        return "urgent", "severe pain"
    if f.concept == "allergic_reaction" and f.label == "allergic reaction" and f.temporal in {"current", "unknown", "recent"}:
        # "I'm having an allergic reaction": the severe wordings are red; the plain statement still needs prompt assessment
        return "urgent", "allergic reaction"
    return None, f.label


def _is_mild(f: Fact) -> bool:
    if f.severity is not None:
        return 1 <= f.severity <= 3
    return f.severity_label == "mild"


def _contribution(f: Fact) -> tuple[str | None, str, str]:
    """(state, label, why) for one fact. state None = does not escalate."""
    tier, label = _tier(f)
    if f.experiencer != "self":
        return None, label, f"not_self:{f.assertion}"
    if f.assertion not in {"present", "possible"}:
        return None, label, f"not_a_current_report:{f.assertion}"
    if tier is None:
        return None, label, "concept_not_flagged"
    crisis = f.concept in CRISIS
    t = f.temporal
    mild_soft = (tier == "red" and f.concept in MILD_SOFT and t in {"current", "unknown"} and _is_mild(f)
                 and not _ACS_FEATURES.search(f.source_text))
    if f.assertion == "possible":
        if mild_soft and f.concept in POSSIBLE_IS_EMERGENCY:
            return "URGENT", label, "mild_red_flag_symptom"
        if f.concept in POSSIBLE_IS_EMERGENCY and (t in {"current", "unknown", "recent"} or (crisis and t == "recurring")):
            return "EMERGENCY", label, "hedged_but_emergency_class"
        if tier == "red":
            return POTENTIAL, label, "hedged_red_flag"
        return None, label, "hedged_urgent_tier"
    if tier == "red":
        if mild_soft:
            return "URGENT", label, "mild_red_flag_symptom"
        if t in {"current", "unknown"}:
            return "EMERGENCY", label, "current_red_flag"
        if t == "recurring":
            if crisis:
                return "EMERGENCY", label, "recurring_crisis"
            if f.concept in EVENT_LIKE:
                return "URGENT", label, "recurring_event_red_flag"   # repeated seizures/faints need prompt assessment
            return POTENTIAL, label, "recurring_red_flag"
        if f.concept in EVENT_LIKE and t in {"recent", "resolved"} and (t == "recent" or f.same_day):
            # a seizure/faint/stroke sign/anaphylaxis that already ended still needs prompt assessment
            return "URGENT", label, "recent_single_event_red_flag"
        if t == "recent":
            return POTENTIAL, label, "recent_red_flag_status_unknown"
        if t == "resolved":
            return (POTENTIAL, label, "resolved_same_day_or_crisis") if (f.same_day or crisis) else (None, label, "resolved_historical")
        return None, label, "historical"
    if tier == "urgent":
        if t in {"current", "unknown"}:
            return "URGENT", label, "current_urgent_symptom"
        if t == "recent":
            return POTENTIAL, label, "recent_urgent_status_unknown"
        return None, label, "historical_or_resolved"
    return None, label, "unclassified"


def assess_facts(facts: Iterable[Fact], text: str = "") -> SafetyAssessment:
    facts = tuple(facts)
    best = "NO_REDFLAG"
    reasons: list[str] = []
    concepts: list[str] = []
    red_concepts: set[str] = set()
    trace: list[dict] = []
    crisis = False
    for f in facts:
        state, label, why = _contribution(f)
        trace.append({
            "concept": f.concept, "assertion": f.assertion, "temporal": f.temporal, "reason": f.reason,
            "decision": state or "NO_REDFLAG", "why": why,
        })
        if state is None:
            continue
        if _RANK[state] > _RANK[best]:
            best = state
        reasons.append(label)
        concepts.append(f.concept)
        if (f.tier == "red") and f.assertion in {"present", "possible"}:
            red_concepts.add(f.concept)
        crisis = crisis or f.concept in CRISIS
    # two independent hedged/recent red flags together are more than a clarifying question
    if best == POTENTIAL and len(red_concepts) >= 2:
        best = "URGENT"
    return SafetyAssessment(
        level=_LEVEL[best], reasons=tuple(dict.fromkeys(reasons)), user_message=text, state=best,
        concepts=tuple(dict.fromkeys(concepts)), facts=facts, trace=tuple(trace), crisis=crisis,
    )


def assess_safety(message: str, facts: Iterable[Fact] | None = None) -> SafetyAssessment:
    """Triage one user message. Pass `facts` to reuse an extraction already done for this message.

    Never raises: if semantic analysis fails, the fail-safe path asks a clarifying question when
    the text contains any red-flag wording, instead of returning a 500 or silently saying GREEN.
    """
    try:
        text = message if isinstance(message, str) else ("" if message is None else str(message))
        text = text.strip()
    except Exception:  # noqa: BLE001 - even a hostile __str__ must not break triage
        text = ""
    try:
        return assess_facts(analyze(text) if facts is None else facts, text)
    except Exception as error:  # noqa: BLE001 - safety must degrade, not crash
        return _fail_safe(text, error)


def _fail_safe(text: str, error: Exception) -> SafetyAssessment:
    try:
        from logging_util import logger
        logger.error(component="SAFETY", operation="assess", error=error, fallback_action="keyword_fail_safe")
    except Exception:  # noqa: BLE001
        pass
    try:
        hits = keyword_hits(text)
    except Exception:  # noqa: BLE001 - both analysis and keyword scan failed: never answer GREEN blind
        return SafetyAssessment("AMBER", ("safety analysis unavailable",), text, POTENTIAL,
                                trace=({"decision": POTENTIAL, "why": "analysis_and_keyword_scan_failed"},))
    if not hits:
        return SafetyAssessment("GREEN", (), text, "NO_REDFLAG", trace=({"decision": "NO_REDFLAG", "why": "analysis_failed_no_keywords"},))
    return SafetyAssessment(
        level="AMBER", reasons=tuple(dict.fromkeys(label for _c, _t, label in hits)), user_message=text,
        state=POTENTIAL, concepts=tuple(dict.fromkeys(c for c, _t, _l in hits)),
        trace=({"decision": POTENTIAL, "why": "analysis_failed_keyword_fail_safe"},),
        crisis=any(c in CRISIS for c, _t, _l in hits),
    )


# --------------------------------------------------------------------------
# Model guidance and deterministic copy
# --------------------------------------------------------------------------

def safety_instruction(assessment: SafetyAssessment) -> str:
    if assessment.state == "EMERGENCY":
        base = (
            "SAFETY ROUTING: Potentially urgent warning language was detected. "
            "Do not diagnose. Encourage prompt/emergency medical assessment as appropriate. "
            "If the situation sounds immediately life-threatening, tell the user to contact local emergency services now. "
            "Do not bury the urgent action under a long explanation."
        )
    elif assessment.state == "URGENT":
        base = (
            "SAFETY ROUTING: Concerning symptoms may need timely professional assessment. "
            "Avoid diagnosis and avoid false reassurance. Give practical next steps and state what worsening signs should trigger urgent care."
        )
    elif assessment.state == POTENTIAL:
        base = (
            "SAFETY ROUTING: The user mentioned something that could be a red flag but its status is unclear. "
            "Ask ONE brief clarifying question (is it happening now? how severe?) and give a short safety net. Do not diagnose and do not alarm."
        )
    else:
        base = (
            "SAFETY ROUTING: No deterministic urgent trigger was detected. This does not rule out a medical emergency. "
            "Use normal cautious health guidance and escalate when the user's symptoms warrant it."
        )
    notes = []
    for f in assessment.facts:
        flaggable = f.tier == "red" or f.concept in PAIN_CONCEPTS
        if flaggable and _contribution(f)[0] is None:
            notes.append(f"- {display_name(f.concept)}: user context is '{f.assertion}/{f.temporal}'. This is NOT a current symptom; never say it was detected or reported.")
    if notes:
        base += "\nMENTIONED BUT NOT ACTIVE (do not treat as symptoms):\n" + "\n".join(dict.fromkeys(notes))
    return base


def _names(assessment: SafetyAssessment) -> str:
    seen = list(dict.fromkeys(display_name(c) for c in assessment.concepts))
    if not seen:
        return "a potentially serious symptom"
    return ", ".join(seen[:-1]) + (" and " if len(seen) > 1 else "") + seen[-1]


#: crisis lines for India (the default); `locale_support.crisis_lines(country)` gives the wording for anywhere else. One copy for every crisis reply.
CRISIS_LINES = locale_support.crisis_lines(None)

_NET = {
    "chest_pain": "it spreads to your arm, jaw or back, or comes with trouble breathing, sweating, nausea or fainting",
    "shortness_of_breath": "your lips look blue, you cannot speak in full sentences, or it is getting worse",
    "fainting": "it happens again, or you have chest pain, a racing heartbeat, or an injury from the fall",
}


def emergency_response(assessment: SafetyAssessment, country: Any = None) -> str:
    """Hard-gate copy: deterministic, never sent through a model."""
    if assessment.crisis:
        return (
            "### I'm really glad you told me\n\n"
            "What you're describing sounds heavy, and your safety matters most right now. "
            "If you might act on these thoughts or you are in immediate danger, please call your local emergency number now.\n\n"
            "### Reaching someone right now\n"
            f"- {locale_support.crisis_lines(country)}\n"
            "- If you can, tell someone you trust and ask them to stay with you.\n"
            "- If I've misunderstood you, tell me. I'd rather be corrected than miss something.\n\n"
            "I'm not a substitute for a crisis service or a clinician, but I'm here to keep talking."
        )
    return (
        "### Please get urgent medical help\n\n"
        f"You told me you're having {_names(assessment)} right now. "
        "That can be serious. If it is happening now or feels severe, contact your local emergency service "
        "or go to the nearest emergency department now.\n\n"
        "### While getting help\n"
        "- Do not drive yourself if you feel faint, confused, severely unwell, or unsafe to travel.\n"
        "- If someone is nearby, tell them what is happening and ask them to stay with you.\n"
        "- Bubbles cannot safely determine the cause of a red-flag symptom from chat alone.\n\n"
        "If I've misread you, tell me and I'll correct it straight away."
    )


def clarification_response(assessment: SafetyAssessment, country: Any = None) -> str:
    """Short, calm follow-up for a possible red flag whose status is unclear (no model call)."""
    lines = ["Thanks for telling me. Before we go on, I want to check something so I don't guess:\n"]
    nets: list[str] = []
    for f in assessment.facts:
        state, _label, _why = _contribution(f)
        if state != POTENTIAL and not (state == "URGENT" and f.temporal in {"recent"}):
            continue
        name = display_name(f.concept)
        if f.assertion == "possible":
            q = f"You mentioned something that might be {name}. Is it happening right now, and how strong is it from 0 to 10?"
        elif f.temporal == "recurring":
            q = f"You said {name} comes and goes. How often does it happen, what brings it on, and does it ease with rest?"
        elif f.temporal == "resolved":
            q = f"I'm glad the {name} passed. When did it happen, how long did it last, and has anything like it come back since?"
        else:
            q = f"Is the {name} still happening right now, or has it stopped? When did it start?"
        if q not in lines:
            lines.append(f"- {q}")
        if f.concept in _NET:
            nets.append(f"- {display_name(f.concept).capitalize()}: seek emergency care if {_NET[f.concept]}.")
    if len(lines) == 1:  # no per-fact detail available (fail-safe path): ask once per concept
        for concept in dict.fromkeys(assessment.concepts):
            lines.append(f"- You mentioned something that sounds like {display_name(concept)}. Is it happening right now, and how strong is it from 0 to 10?")
    if assessment.crisis:
        lines.append(f"- If you are thinking about harming yourself, please reach out now. {locale_support.crisis_lines(country)}")
    lines.append("\nIf it's happening now and it's severe, don't wait for my reply: call your local emergency number.")
    if nets:
        lines.append("\n**Go to emergency care straight away if:**\n" + "\n".join(dict.fromkeys(nets)))
    return "\n".join(lines)


def urgent_fallback_response(assessment: SafetyAssessment) -> str:
    """Used only if the AI provider is unavailable for an URGENT message."""
    return (
        "### This deserves prompt attention\n\n"
        f"You mentioned {_names(assessment)}. I can't assess it from chat, so please speak to a clinician or an urgent-care service today. "
        "If it gets worse, or you develop trouble breathing, chest pain, confusion, or you can't keep fluids down, go to emergency care.\n\n"
        "If I've misunderstood anything, tell me."
    )
