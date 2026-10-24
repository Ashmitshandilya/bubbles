"""Training examples for the paragraph reader: a person's own words about a day, and the events Bubbles must find in them.

Each row is (text, event types that MUST be found, event types that must NOT be found). The 'must not' side matters as much: a plain
statement must never invent a symptom or a medicine. Add a row whenever a real message is misread.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_pipeline as cp  # noqa: E402

CORPUS = [
    ("Slept 7 hours, drank 2 litres of water and walked for 40 minutes.", {"sleep", "hydration", "exercise"}, {"symptom", "medication"}),
    ("Yesterday I slept around 5 hours and woke up three times. Had two coffees.", {"sleep"}, {"symptom", "medication"}),
    ("Had poha for breakfast, dal chawal for lunch and skipped dinner.", {"food"}, {"symptom", "medication"}),
    ("My weight this morning was 61.5 kg.", {"weight"}, {"symptom", "medication"}),
    ("I have a headache since afternoon and took paracetamol.", {"symptom", "medication"}, set()),
    ("I twisted my knee while dancing and it hurts to walk.", {"symptom"}, {"medication"}),
    ("Fever of 101 last night and I feel weak.", {"vital_sign"}, set()),
    ("Period started today and the cramps are strong.", {"menstrual_symptom"}, set()),
    ("Took my iron supplement after lunch.", {"supplement"}, {"symptom"}),
    ("Aaj 6 ghante soya aur 3 glass paani piya.", {"sleep"}, {"symptom", "medication"}),
    ("Maine aaj 30 minute walk kiya aur dal roti khaya.", {"exercise"}, {"symptom", "medication"}),
    ("Mood was low today, work was stressful.", {"mood"}, {"medication"}),
    ("Had a fight with my girlfriend, slept only 4 hours.", {"sleep"}, {"medication"}),
    ("Nothing special today, just a normal day.", set(), {"symptom", "medication", "sleep", "weight"}),
    ("I am thinking about buying a new phone.", set(), {"symptom", "medication", "sleep", "weight", "food"}),
    ("My friend has a fever and is taking paracetamol.", set(), {"medication", "vital_sign"}),
    ("Mera weight 58 kg hai aaj.", {"weight"}, {"symptom", "medication"}),
    ("My goal is to reach 58 kg by December.", set(), {"weight"}),
    ("The doctor said my weight should be 55 kg someday.", set(), {"weight"}),
]


def _types(text: str) -> set[str]:
    turn = cp.analyze_turn(text, [])
    return {e["event_type"] for e in cp.build_rule_events(turn, "m1")}


@pytest.mark.parametrize("text,must,must_not", CORPUS, ids=[c[0][:40] for c in CORPUS])
def test_the_events_in_a_day_are_found_and_nothing_is_invented(text, must, must_not):
    got = _types(text)
    assert must <= got, (text, "missing", must - got, "found", got)
    assert not (must_not & got), (text, "invented", must_not & got)


@pytest.mark.xfail(reason="a distance with no minutes (ran 5 km) is not logged yet: exercise needs a duration", strict=True)
def test_a_run_given_only_as_a_distance_is_a_known_gap():
    assert "exercise" in _types("Went for a run this evening and ran 5 km, feeling good.")
