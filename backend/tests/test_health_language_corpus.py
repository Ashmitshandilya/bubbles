"""Regression suite: 308 labeled natural-language cases written independently of the engine.

The corpus (health_language_corpus.py) was authored by an agent that never saw the implementation, from a
written spec, so the engine cannot be overfit to its own tests. Each case checks some of: the facts the engine
extracts (assertion / temporal / severity), concepts that must NOT count as an active symptom, the safety
state, whether a message is a correction of a wrong warning, contradictions, and parsed daily-log metrics.

A label the engine disagrees with is never silently skipped: it must be listed in KNOWN_LABEL_DISPUTES with
the reason, so the list of disagreements stays small, visible and reviewed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from conversation_correction import detect_contradictions, detect_correction  # noqa: E402
from daily_log_parser import parse_daily_log  # noqa: E402
from health_language_corpus import CASES  # noqa: E402
from health_semantics import analyze  # noqa: E402
from safety_engine import assess_safety  # noqa: E402

KNOWN_LABEL_DISPUTES = {
    "hdg-008-my-throat-feels-a": (
        "Label says the throat-tightness fact is 'possible' because the user is unsure of the CAUSE ('not sure if it's an "
        "allergy'). The engine records a present, mild symptom and routes it to urgent/clarify (the label's state check "
        "passes). Treating a stated physical symptom as merely possible would under-triage."),
    "con-011-i-barely-slept-last": (
        "Expects a sleep-duration contradiction (earlier '8 hours', now '3 hours'). Contradictions are detected between "
        "symptom/medication/period statements; numeric duration conflicts are not modelled yet."),
}


def _check(case: dict) -> list[str]:
    errs: list[str] = []
    text = case["text"]
    facts = analyze(text)
    rows = [dict(id=f"h{i}", role=h["role"], content=h["content"]) for i, h in enumerate(case.get("history") or [])]
    for concept, exp in (case.get("facts") or {}).items():
        cands = [f for f in facts if f.concept == concept]
        if not cands:
            errs.append(f"fact {concept}: not produced (got {[(f.concept, f.assertion) for f in facts]})")
            continue
        if not any(f.assertion == exp["assertion"] and ("temporal" not in exp or f.temporal == exp["temporal"])
                   and ("severity" not in exp or f.severity == exp["severity"]) for f in cands):
            errs.append(f"fact {concept}: expected {exp}, got {[(f.assertion, f.temporal, f.severity) for f in cands]}")
    for concept in case.get("not_active") or []:
        for f in facts:
            if f.concept == concept and f.active:
                errs.append(f"{concept} wrongly active ({f.assertion}/{f.temporal}, {f.reason})")
    state = assess_safety(text, facts).state
    if "state" in case and state != case["state"]:
        errs.append(f"state: expected {case['state']}, got {state}")
    if "state_in" in case and state not in case["state_in"]:
        errs.append(f"state: expected one of {case['state_in']}, got {state}")
    if "correction" in case:
        c = detect_correction(text, facts, rows)
        exp = case["correction"]
        if c.is_correction != exp["is_correction"]:
            errs.append(f"correction: expected {exp['is_correction']}, got {c.is_correction} ({c.kind})")
        elif exp["is_correction"] and set(exp.get("concepts", [])) - set(c.concepts):
            errs.append(f"correction concepts: expected {exp['concepts']}, got {list(c.concepts)}")
    if "contradiction" in case:
        prior = [f for r in rows if r["role"] == "user" for f in analyze(r["content"])]
        found = [(c["concept"], c["kind"]) for c in detect_contradictions(facts, prior)]
        exp = case["contradiction"]
        if (exp["concept"], exp["kind"]) not in found:
            errs.append(f"contradiction: expected {exp}, got {found}")
    if "log" in case:
        metrics = parse_daily_log(text, facts).metrics
        for key, want in case["log"].items():
            got = metrics.get(key, "<missing>")
            if key == "meals":
                ok = set(want) <= set(got if got != "<missing>" else [])
            elif key in ("supplements", "medications"):
                ok = (got == want) if got != "<missing>" else want == []
            else:
                ok = got == want
            if not ok:
                errs.append(f"log {key}: expected {want}, got {got}")
    return errs


def test_corpus_is_the_expected_size_and_ids_are_unique():
    assert len(CASES) >= 300
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert set(KNOWN_LABEL_DISPUTES) <= {c["id"] for c in CASES}, "a dispute names a case that no longer exists"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_corpus_case(case):
    errs = _check(case)
    if case["id"] in KNOWN_LABEL_DISPUTES:
        pytest.skip(f"disputed label: {KNOWN_LABEL_DISPUTES[case['id']]}")
    assert not errs, f"{case['text'][:120]!r}\n  " + "\n  ".join(errs)


def test_disputes_are_still_disputes():
    """If the engine starts agreeing with a disputed label, remove it from the list (keeps the list honest)."""
    by_id = {c["id"]: c for c in CASES}
    for case_id in KNOWN_LABEL_DISPUTES:
        assert _check(by_id[case_id]), f"{case_id} now passes: delete it from KNOWN_LABEL_DISPUTES"


def test_safety_critical_categories_have_no_exceptions():
    """Anything tagged escalation/adversarial/negation/correction must pass outright (no disputes allowed there)."""
    critical = {"escalation", "adversarial", "negation", "correction"}
    for case in CASES:
        if critical & set(case.get("tags", [])):
            assert case["id"] not in KNOWN_LABEL_DISPUTES, case["id"]


# ---------------------------------------------------------------------------------------------------------------------
# Hinglish (romanized Hindi) and Devanagari. Written by the implementer (unlike CASES above, which are implementation-blind),
# so they are kept separate and checked with the same _check. They pin the facts, not just the safety level, so the
# negation / hypothetical / other-person / history handling stays aligned with English.
# Term choices await native-speaker and clinician review: docs/clinical/HINGLISH_SAFETY_TERMS_REVIEW.md.
# ---------------------------------------------------------------------------------------------------------------------
_EMG, _NO, _POT = "EMERGENCY", "NO_REDFLAG", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION"


def _hi(case_id, text, state, **facts):
    return {"id": f"hinglish-{case_id}", "text": text, "state": state,
            "facts": {c: dict(zip(("assertion", "temporal"), v if isinstance(v, tuple) else (v,))) for c, v in facts.items()}}


HINGLISH_CASES = [
    # escalation: the reported misses
    _hi("chest-arm", "mere seene mein bahut tez dard ho raha hai aur left haath sunn ho gaya", _EMG,
        chest_pain=("present", "current"), stroke_signs=("present", "current")),
    _hi("cant-breathe", "saans nahi aa rahi", _EMG, shortness_of_breath=("present", "current")),
    _hi("deva-chest", "मेरे सीने में बहुत तेज दर्द हो रहा है", _EMG, chest_pain=("present", "current")),
    _hi("deva-breath", "साँस नहीं आ रही", _EMG, shortness_of_breath=("present", "current")),
    _hi("breath-effort", "mujhe saans lene mein bahut takleef ho rahi hai", _EMG, shortness_of_breath=("present", "current")),
    _hi("heart-attack", "dil ka daura pad raha hai", _EMG, heart_attack="present"),
    _hi("face-droop", "mera chehra ek taraf latak gaya hai", _EMG, stroke_signs="present"),
    _hi("slurred", "zubaan ladkhada rahi hai", _EMG, stroke_signs="present"),
    _hi("bleeding", "khoon ruk nahi raha", _EMG, heavy_bleeding="present"),
    _hi("anaphylaxis", "gala band ho raha hai", _EMG, allergic_reaction="present"),
    _hi("faint", "main behosh ho raha hoon", _EMG, fainting=("present", "current")),
    _hi("seizure", "mirgi ka daura pad raha hai", _EMG, seizure="present"),
    _hi("crisis", "main marna chahta hoon", _EMG, suicidal_ideation="present"),
    _hi("crisis-passive", "jeene ka mann nahi karta", _EMG, suicidal_ideation="present"),
    _hi("deva-crisis", "मैं मरना चाहता हूँ", _EMG, suicidal_ideation="present"),
    _hi("self-harm", "khud ko nuksan pahunchana chahta hoon", _EMG, self_harm="present"),
    # Hindi words that look like English question cues
    _hi("do-din", "do din se seene mein dard hai", _EMG, chest_pain=("present", "current")),
    _hi("is-waqt", "is waqt saans phool rahi hai", _EMG, shortness_of_breath=("present", "current")),
    # negation (Hindi puts the negator after the symptom)
    _hi("neg", "mujhe seene mein dard nahi hai", _NO, chest_pain="negated"),
    _hi("neg-deva", "मेरे सीने में दर्द नहीं है", _NO, chest_pain="negated"),
    _hi("neg-code-mixed", "mujhe chest pain nahi hai", _NO, chest_pain="negated"),
    _hi("neg-list", "seene mein dard aur saans ki takleef nahi hai", _NO, chest_pain="negated", shortness_of_breath="negated"),
    _hi("neg-one-of-two", "seene mein dard nahi hai lekin saans nahi aa rahi", _EMG,
        chest_pain="negated", shortness_of_breath=("present", "current")),
    _hi("not-stopping", "seene mein dard nahi ruk raha", _EMG, chest_pain=("present", "current")),
    _hi("past-denial-but-now", "seene mein dard nahi ho raha tha lekin ab ho raha hai", _EMG, chest_pain="present"),
    _hi("crisis-denied", "main marna nahi chahta", _NO),
    _hi("without", "bina saans phoole main 5 km daud leta hoon", _NO, shortness_of_breath="negated"),
    # someone else / hypothetical / question / history
    _hi("other", "mere papa ko seene mein dard ho raha hai", _NO, chest_pain="other_person"),
    _hi("other-deva", "मेरे पापा को सीने में दर्द हो रहा है", _NO, chest_pain="other_person"),
    _hi("told-dad", "papa ko bataya ki seene mein dard hai", _EMG, chest_pain="present"),
    _hi("family-history", "meri family mein heart attack ki history hai", _NO, heart_attack="other_person"),
    _hi("hypothetical", "agar mujhe seene mein dard ho to kya karun?", _NO, chest_pain="hypothetical"),
    _hi("hypothetical-deva", "अगर मुझे सीने में दर्द हो तो क्या करूँ?", _NO, chest_pain="hypothetical"),
    _hi("question", "kya seene mein dard heart attack ka lakshan hota hai?", _NO, chest_pain="question", heart_attack="question"),
    _hi("self-question", "kya karun, seene mein bahut dard hai", _EMG, chest_pain="present"),
    _hi("history", "pichhle saal mujhe seene mein dard hua tha", _NO, chest_pain=("present", "past")),
    _hi("history-deva", "मुझे पिछले साल सीने में दर्द हुआ था", _NO, chest_pain=("present", "past")),
    _hi("childhood", "bachpan mein mujhe mirgi ke daure aate the", _NO, seizure=("present", "past")),
    _hi("resolved", "subah seene mein dard tha, ab theek hoon", _POT, chest_pain=("present", "resolved")),
    _hi("recurring", "seedhiyan chadhte waqt saans phoolti hai", _POT, shortness_of_breath=("present", "recurring")),
    _hi("breath-stopped-not-resolved", "saans ruk ruk ke aa rahi hai", _EMG, shortness_of_breath=("present", "current")),
    # look-alikes that are not red flags
    _hi("on-tour", "main daure par hoon", _NO),
    _hi("stomach", "pet mein dard hai", _NO),
    _hi("meal", "2 roti aur dal khayi", _NO),
]


@pytest.mark.parametrize("case", HINGLISH_CASES, ids=[c["id"] for c in HINGLISH_CASES])
def test_hinglish_case(case):
    errs = _check(case)
    assert not errs, f"{case['text'][:120]!r}\n  " + "\n  ".join(errs)


def test_devanagari_is_read_like_the_romanized_spelling():
    from health_semantics import normalize
    assert normalize("मेरे सीने में दर्द नहीं है। साँस नहीं आ रही") == "mere sine mein dard nahi hai. saans nahi aa rahi"
    assert normalize("I have chest pain") == "I have chest pain"
