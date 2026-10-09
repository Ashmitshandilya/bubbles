"""Fact-contract evaluation: the six statements from the engine spec (and three more) must never collapse into one fact.
Cases: tests/eval/fact_cases.jsonl (synthetic). `temporal: null` means the temporal value is not asserted."""
import json
from pathlib import Path

import health_semantics as hs

CASES = [json.loads(l) for l in (Path(__file__).parent / "eval" / "fact_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def facts(c):
    return [f for f in hs.analyze(c["text"]) if f.concept == c["concept"]]


def test_each_statement_gets_the_expected_assertion_and_time():
    bad = []
    for c in CASES:
        fs = facts(c)
        ok = len(fs) == 1 and fs[0].assertion == c["assertion"] and (c["temporal"] is None or fs[0].temporal == c["temporal"])
        if not ok:
            bad.append((c["id"], c["text"], [(f.assertion, f.temporal) for f in fs]))
    assert not bad, bad


def test_the_statements_are_not_collapsed_into_one_fact():
    keys = {(facts(c)[0].assertion, facts(c)[0].temporal) for c in CASES if c["id"] in {"F01", "F02", "F03", "F04", "F07", "F08"}}
    assert len(keys) == 6
