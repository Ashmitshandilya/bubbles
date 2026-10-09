"""Medication-safety evaluation (tests/eval/med_cases.jsonl): curated interaction and allergy checks.
Expectations come from standard pharmacology, not from engine output. `known_gap` cases document real misses: they must still
fail (so they are not forgotten); the test says when to remove the flag. Warnings only: the engine never forbids anything.
Brand-name aliases and any new rule need pharmacist review (clinical_constants.py header)."""
import json
from pathlib import Path

import med_schedule as m

CASES = [json.loads(l) for l in (Path(__file__).parent / "eval" / "med_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def ok(c):
    if c["kind"] == "interaction":
        got = m.check_interactions(c["names"])
        return (not got) if c["expect"] == "none" else (bool(got) and (c["expect"] == "any" or any(g["level"] == c["expect"] for g in got)))
    got = m.allergy_warnings(c["meds"], c["allergies"])
    return (not got) if c["expect"] == "none" else bool(got)


def test_regression_gate_and_known_gaps_are_tracked():
    res = [(c, ok(c)) for c in CASES]
    failed = [c["id"] for c, good in res if not good and not c["known_gap"]]
    fixed = [c["id"] for c, good in res if good and c["known_gap"]]
    assert not failed, f"medication-safety regressions: {failed}"
    assert not fixed, f"known gaps now pass, remove the flag: {fixed}"


def test_report(capsys):
    res = [(c, ok(c)) for c in CASES]
    with capsys.disabled():
        print(f"\nMED EVAL: {sum(g for _c, g in res)}/{len(res)} pass | known gaps: {[c['id'] for c, g in res if not g]}")
    assert len(res) >= 25
