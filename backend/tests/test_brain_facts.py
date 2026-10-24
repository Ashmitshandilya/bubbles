"""The sheet of facts handed to the model: right numbers, honest gaps, only for what the message touches."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brain_facts as bf  # noqa: E402

TODAY = date(2026, 10, 24)


def series(**by_name):
    return {n: {TODAY - timedelta(days=len(v) - 1 - i): x for i, x in enumerate(v)} for n, v in by_name.items()}


def test_what_a_message_touches():
    assert bf.series_needed("why am I so tired lately?") == {"sleep_hours", "hydration_ml", "activity_minutes", "mood"}
    assert bf.series_needed("is my sleep ruining my mood") == {"sleep_hours", "mood", "activity_minutes"}
    assert bf.series_needed("I feel anxious today") == {"sleep_hours", "mood", "activity_minutes"}
    assert bf.series_needed("what is the capital of France") == set()


def test_the_sheet_has_the_numbers_and_the_rules():
    s = series(sleep_hours=[7, 7, 7, 7, 7, 7, 7, 6, 5, 5, 6, 6, 6, 6])
    text = bf.sheet(s, TODAY, {"sleep_hours"})
    assert text.startswith("WHAT BUBBLES ALREADY KNOWS") and "never invent others" in text
    assert "- sleep: last night 6 h" in text and "last 7 days average 5 h 43 min over 7 days logged" in text and "the week before averaged 7 h" in text


def test_a_topic_with_no_logs_is_marked_so_the_model_does_not_guess():
    text = bf.sheet(series(mood=[6, 6, 7]), TODAY, {"sleep_hours", "mood"})
    assert "- sleep: nothing logged in the last 14 days" in text and "- mood: " in text


def test_nothing_asked_nothing_written():
    assert bf.sheet(series(mood=[5]), TODAY, set()) == ""


def test_a_fight_and_a_bad_night_are_read_side_by_side():
    import brain_facts as b
    assert b.mentions_relationship("I had a fight with my boyfriend and slept badly")
    assert "mood" in {n for n in b.series_needed("my boyfriend and I argued")} and "sleep_hours" in b.series_needed("my boyfriend and I argued")
    line = b.tension_line([TODAY - timedelta(days=1), TODAY - timedelta(days=3), TODAY - timedelta(days=40)], TODAY)
    assert "2 in the last 14 days" in line and "yesterday" in line
    assert "none marked" in b.tension_line([], TODAY)
    text = b.sheet(series(sleep_hours=[6, 5]), TODAY, {"sleep_hours"}, [line])
    assert text.endswith(line)
