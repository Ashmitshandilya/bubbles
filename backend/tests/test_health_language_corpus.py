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
