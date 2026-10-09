"""Versioned safety evaluation (tests/eval/safety_cases.jsonl). Run `pytest tests/test_eval_safety.py -s` for the report.

expect: green = GREEN; not_green = AMBER or RED; red = RED.
`known_gap` cases document real failures: they must still fail (so nobody forgets them) and the test tells you to
remove the flag once fixed. Every other case is a regression gate. Cases were written from the expected clinical
behaviour, not copied from engine output. They are synthetic and contain no real user data.
"""
import json
from pathlib import Path

import safety_engine as se

CASES = [json.loads(line) for line in (Path(__file__).parent / "eval" / "safety_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
OK = {"green": lambda lv: lv == "GREEN", "not_green": lambda lv: lv != "GREEN", "red": lambda lv: lv == "RED"}


def run():
    return [(c, OK[c["expect"]](se.assess_safety(c["text"]).level)) for c in CASES]


def test_regression_gate_and_known_gaps_are_tracked():
    results = run()
    failed = [c["id"] + " " + c["text"] for c, ok in results if not ok and not c["known_gap"]]
    fixed = [c["id"] for c, ok in results if ok and c["known_gap"]]
    assert not failed, "safety regressions: " + "; ".join(failed)
    assert not fixed, f"known gaps now pass, remove known_gap flag: {fixed}"


def test_report(capsys):
    results = run()
    by = {}
    for c, ok in results:
        by.setdefault(c["tag"], []).append(ok)
    n_ok = sum(ok for _c, ok in results)
    gaps = [c["id"] for c, ok in results if not ok]
    with capsys.disabled():
        print(f"\nSAFETY EVAL: {n_ok}/{len(results)} pass | known gaps: {gaps}")
        for tag, v in sorted(by.items()):
            print(f"  {tag:42} {sum(v)}/{len(v)}")
    assert len(results) >= 30
