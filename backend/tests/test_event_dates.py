"""A health event told with a day ("on 20 September I had a headache") is logged on that day, not on the day it was typed."""
from datetime import date, datetime, timezone

import pytest

from chat_pipeline import analyze_turn, build_rule_events
from event_dates import day_phrase, find_dates, stated_date, user_today
from wellness_common import REQUEST_TZ

TODAY = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,expected", [
    ("On 20 September I had a bad headache", "2026-09-20"),
    ("I did this on 20th", "2026-09-20"),                   # the latest 20th, never a future one
    ("on the 20th my stomach hurt", "2026-09-20"),
    ("on the 5th my stomach hurt", "2026-10-05"),
    ("sept 20 fever", "2026-09-20"),
    ("20th sept ko bukhar tha", "2026-09-20"),
    ("20th ko bukhar tha", "2026-09-20"),
    ("20/09/2026 cramps", "2026-09-20"),
    ("on 20/9 I fainted", "2026-09-20"),
    ("headache on 2026-09-20", "2026-09-20"),
    ("yesterday", "2026-10-12"),
    ("day before yesterday", "2026-10-11"),
    ("3 days ago", "2026-10-10"),
    ("last monday", "2026-10-12"),
    ("on 20 december 2025", "2025-12-20"),          # a past year inside the last 12 months
])
def test_explicit_days(text, expected):
    assert stated_date(text, TODAY) == date.fromisoformat(expected)


@pytest.mark.parametrize("text", [
    "on 20 december",                      # a future day is never used, and not re-read as "the 20th"
    "this is the 3rd time I have a headache",
    "on 3rd day of my period",
    "I took 5mg on 5",
    "I may 2 times",
    "pain 6/10",
    "I was on 2 pills",
    "on 31st",                             # 31 September does not exist
    "on 20 september 2020",                # more than a year back
    "kal se sar dard hai",                 # "kal" is both yesterday and tomorrow
])
def test_not_a_day(text):
    assert stated_date(text, TODAY) is None


def test_two_different_days_name_no_single_day():
    assert stated_date("on 20th I had fever and today I have a cough", TODAY) is None
    assert [d.isoformat() for _p, d in find_dates("on 20th I had fever and today I have a cough", TODAY)] == ["2026-09-20", "2026-10-13"]


def _events(text):
    turn = analyze_turn(text, [], now=NOW)
    return turn, [(e["event_type"], e["extracted_data"].get("name"), e["extracted_data"]["date"]) for e in build_rule_events(turn, "m1", now=NOW)]


def test_a_past_symptom_with_a_day_is_logged_on_that_day():
    turn, events = _events("On 20 September I had a bad headache")
    assert events == [("symptom", "headache", "2026-09-20")]
    assert turn.log.log_date == "2026-09-20"


def test_each_symptom_gets_the_day_of_its_own_clause():
    _turn, events = _events("On 20th I had fever and today I have a cough")
    assert ("symptom", "fever", "2026-09-20") in events
    assert ("symptom", "cough", "2026-10-13") in events


def test_a_current_symptom_in_another_sentence_stays_today():
    _turn, events = _events("On 20th I had fever. I have a cough now")
    assert ("symptom", "cough", "2026-10-13") in events


def test_metrics_follow_the_named_day():
    _turn, events = _events("I slept 6 hours on 20 september")
    assert ("sleep", "sleep", "2026-09-20") in events


def test_history_without_a_day_is_still_not_logged():
    assert _events("I had chest pain as a child")[1] == []
    assert _events("I had a headache last year")[1] == []


def test_today_is_the_persons_own_day():
    late_night_utc = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)   # already 13 October in India
    token = REQUEST_TZ.set(330)
    try:
        assert user_today(late_night_utc) == date(2026, 10, 13)
    finally:
        REQUEST_TZ.reset(token)
    assert user_today(late_night_utc) == date(2026, 10, 12)


def test_day_phrase():
    assert day_phrase("2026-10-13", TODAY) == "today"
    assert day_phrase("2026-10-12", TODAY) == "yesterday"
    assert day_phrase("2026-09-20", TODAY) == "on 20 September"
    assert day_phrase("2025-09-20", TODAY) == "on 20 September 2025"
