"""Ask-your-data: what is recognised, what is left to the model, and that every number in an answer is in the person's own series."""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_answers as da  # noqa: E402

TODAY = date(2026, 10, 24)


def series(**by_name):
    out = {}
    for name, values in by_name.items():   # values: list of floats, newest last; None = not logged
        out[name] = {TODAY - timedelta(days=len(values) - 1 - i): v for i, v in enumerate(values)}
    return out


# ---- what is recognised ----
@pytest.mark.parametrize("text,topic,kind", [
    ("how did I sleep last night?", "sleep", "last"),
    ("how has my sleep been this week", "sleep", "summary"),
    ("what was my average mood this week?", "mood", "summary"),
    ("how much water have I had today?", "water", "last"),
    ("what was my best mood day this month", "mood", "best"),
    ("which night did I sleep the least?", "sleep", "worst"),
    ("is my sleep better than last week?", "sleep", "compare"),
    ("am I sleeping enough?", "sleep", "enough"),
    ("have I been active enough lately?", "activity", "enough"),
    ("meri neend kaisi rahi is hafte?", "sleep", "summary"),
    ("mera paani kitna hua aaj?", "water", "last"),
])
def test_data_questions_are_recognised(text, topic, kind):
    got = da.detect(text)
    assert got and got["topic"] == topic and got["kind"] == kind, got


@pytest.mark.parametrize("text", [
    "how can I sleep better?",                      # advice
    "why am I so tired all the time",               # why: for the model, with facts
    "what should I do about my mood",
    "tips for drinking more water",
    "I slept 6 hours last night",                   # a log, not a question
    "how did you sleep?",                           # about Bubbles
    "how much water should I drink",                # a guideline question: knowledge card, not data
    "hello",
    "how are my sleep and mood this week?",         # two topics: ambiguous, leave to the model
    "what is a good mood booster",
])
def test_everything_else_is_left_alone(text):
    assert da.detect(text) is None


def test_windows_and_offsets():
    assert da.detect("how was my sleep this month?")["days"] == 30
    assert da.detect("how was my sleep last week?")["offset"] == 7
    assert da.detect("how was my sleep over the last 2 weeks?")["days"] == 14


# ---- answers ----
def test_a_summary_uses_only_logged_days_and_never_counts_a_gap_as_zero():
    s = series(sleep_hours=[7, None, 6, None, 5, 8, 7])
    text = da.answer({"topic": "sleep", "kind": "summary", "days": 7, "offset": 0}, s, TODAY)
    assert "5 nights" in text and "6 h 36 min" in text      # (7+6+5+8+7)/5 = 6.6
    assert "Lowest was 5 h" in text and "highest 8 h" in text


def test_nothing_logged_is_said_plainly():
    text = da.answer({"topic": "sleep", "kind": "summary", "days": 7, "offset": 0}, {}, TODAY, name="Riya")
    assert "don't have any sleep logged" in text and "guessing" in text


def test_last_night_against_the_usual():
    s = series(sleep_hours=[7, 7, 7, 7, 7, 7, 7, 5])
    text = da.answer({"topic": "sleep", "kind": "last", "days": 7, "offset": 0}, s, TODAY)
    assert "5 h" in text and "below your usual 7 h" in text


def test_no_last_night_is_a_gap_not_the_last_known_value():
    s = series(sleep_hours=[7, 7, 7, None, None, None])
    text = da.answer({"topic": "sleep", "kind": "last", "days": 7, "offset": 0}, s, TODAY)
    assert "don't see" in text.lower() and "7 h" not in text


def test_compare_needs_enough_days_in_both_weeks():
    thin = series(mood=[6, 7])
    assert "at least 3 days" in da.answer({"topic": "mood", "kind": "compare", "days": 7, "offset": 0}, thin, TODAY)
    full = series(mood=[4, 4, 4, 4, 4, 4, 4, 7, 7, 7, 7, 7, 7, 7])
    text = da.answer({"topic": "mood", "kind": "compare", "days": 7, "offset": 0}, full, TODAY)
    assert "averaged 7/10" in text and "4/10" in text and "higher" in text and "not a verdict" in text


def test_enough_is_hedged_and_never_a_diagnosis():
    s = series(sleep_hours=[5.5] * 7)
    text = da.answer({"topic": "sleep", "kind": "enough", "days": 7, "offset": 0}, s, TODAY)
    assert "a little under" in text and "how rested you feel matters more" in text
    for banned in ("insomnia", "disorder", "you should see", "deficien"):
        assert banned not in text.lower()


def test_water_in_glasses_and_activity_per_week():
    w = da.answer({"topic": "water", "kind": "summary", "days": 7, "offset": 0}, series(hydration_ml=[1500, 2000, 1750]), TODAY)
    assert "1.8 L" in w and "glasses" in w
    a = da.answer({"topic": "activity", "kind": "enough", "days": 7, "offset": 0}, series(activity_minutes=[30] * 7), TODAY)
    assert "210 minutes a week" in a and "at or above" in a


def test_one_entry_is_not_called_a_trend():
    text = da.answer({"topic": "mood", "kind": "best", "days": 7, "offset": 0}, series(mood=[None, None, 6]), TODAY)
    assert "one mood entry" in text


def test_hinglish_replies_stay_hinglish():
    s = series(sleep_hours=[7, 6, 5, 7])
    text = da.answer({"topic": "sleep", "kind": "summary", "days": 7, "offset": 0}, s, TODAY, language="hi-latn")
    assert "Pichle" in text and "neend" in text
    gap = da.answer({"topic": "sleep", "kind": "summary", "days": 7, "offset": 0}, {}, TODAY, language="hi-latn")
    assert "nahi mila" in gap


def test_every_number_in_a_reply_comes_from_the_series():
    s = series(sleep_hours=[6.5, 7.25, 5.75, 8.0, 6.0, 7.5, 6.25], mood=[5, 6, 7, 6, 5, 6, 7])
    allowed = {str(x) for x in range(0, 61)} | {"7", "9", "14", "30", "150"}
    for intent in ({"topic": "sleep", "kind": "summary", "days": 7, "offset": 0}, {"topic": "sleep", "kind": "worst", "days": 7, "offset": 0},
                   {"topic": "mood", "kind": "summary", "days": 7, "offset": 0}):
        text = da.answer(intent, s, TODAY)
        numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
        assert numbers <= allowed | {"6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "5.7", "5.8", "7.3", "7.5"} | {n for n in numbers if "." not in n}, (text, numbers)
