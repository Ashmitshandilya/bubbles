"""Topic tags (plan C3): fixed word lists, English and Hinglish. A tag is a hint for chips and context, never a safety decision."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import topic_tags  # noqa: E402

CASES = [
    ("meri gf naraz hai, kya reply karu", ("relationship",)),
    ("my boyfriend and I had a fight about money", ("relationship",)),
    ("mera pati roz late aata hai", ("relationship",)),
    ("I feel anxious and lonely tonight", ("mind",)),
    ("mujhe bahut ghabrahat ho rahi hai", ("mind",)),
    ("I have a headache and some nausea", ("body",)),
    ("mujhe bukhar aur khansi hai", ("body",)),
    ("what should I eat after my gym workout", ("fitness",)),
    ("my period is late and the cramps are bad", ("body", "cycle")),
    ("my periods are irregular", ("cycle",)),
    ("how do I prepare for my doctor appointment", ("care",)),
    ("doctor ne dawai likhi hai", ("care",)),
    ("my husband says I stress too much and I can't sleep", ("relationship", "mind")),
    ("hello there", ()),
    ("", ()),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_tags(text, expected):
    assert topic_tags.tags(text) == expected


def test_whole_words_only():
    assert topic_tags.tags("I love exercise") == ("fitness",)
    assert topic_tags.tags("the next scenario") == ()           # "ex" inside a word is not an ex
    assert topic_tags.tags("my ex texted me") == ("relationship",)
    assert topic_tags.tags("I'm running late") == ("fitness",), "a known loose spot: running is a fitness word; it only picks chips, never safety"


def test_order_is_fixed_and_the_input_is_bounded():
    assert topic_tags.tags("doctor gym period anxiety boyfriend headache") == ("relationship", "mind", "body", "fitness", "cycle", "care")
    assert topic_tags.tags("x" * 50_000) == ()
    assert topic_tags.tags(None) == ()
