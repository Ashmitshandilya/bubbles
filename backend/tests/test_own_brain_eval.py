"""The labelled evaluation of Bubbles' own brain: through the real router, which messages are answered locally and which are not.

Gates: (1) NOTHING that must go to the model, to safety or through the normal flow is ever answered locally (precision); (2) the local kinds are
recognised for the great majority of their labelled messages (coverage); (3) each message that is answered locally lands on the kind it was labelled for.
The coverage numbers are printed (run with -s), so a change that lowers them is visible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_pipeline as cp  # noqa: E402

CASES = [json.loads(l) for l in (Path(__file__).parent / "eval" / "own_brain_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
LOCAL = {"own_data", "knowledge", "companion"}


def route_of(text: str) -> str:
    return cp.analyze_turn(text, []).route


@pytest.fixture(scope="module")
def results():
    return [(c["text"], c["expect"], route_of(c["text"])) for c in CASES]


def test_nothing_that_must_not_be_local_is_answered_locally(results):
    wrong = [(t, r) for t, expect, r in results if expect == "other" and r in LOCAL]
    assert not wrong, wrong


def test_every_local_answer_is_the_kind_it_was_labelled_for(results):
    wrong = [(t, expect, r) for t, expect, r in results if expect in LOCAL and r in LOCAL and r != expect]
    assert not wrong, wrong


@pytest.mark.parametrize("kind,minimum", [("own_data", 0.9), ("knowledge", 0.85), ("companion", 0.85)])
def test_the_local_kinds_are_recognised(results, kind, minimum):
    rows = [(t, r) for t, expect, r in results if expect == kind]
    hit = sum(1 for _t, r in rows if r == kind)
    print(f"\n{kind}: {hit}/{len(rows)} answered locally ({hit / len(rows):.0%})")
    missed = [(t, r) for t, r in rows if r != kind]
    assert hit / len(rows) >= minimum, missed


def test_the_set_is_big_and_balanced_enough_to_mean_something():
    kinds = {k: sum(1 for c in CASES if c["expect"] == k) for k in ("own_data", "knowledge", "companion", "other")}
    assert min(kinds.values()) >= 20 and len(CASES) >= 150, kinds
