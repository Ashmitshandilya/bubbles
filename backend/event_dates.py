"""The calendar day a chat message says something happened on ("on 20 September", "on the 20th", "3 days ago").

Pure and deterministic: no model guesses a date. Only explicit wording counts, only past days (or today) are returned,
and only within the last year, so a vague or future date never moves an event. Hinglish "kal" / "parso" mean both
yesterday and tomorrow, so they are left alone.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

MAX_DAYS_BACK = 366

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH = r"(?P<{name}>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_ORD = r"(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+(?P<year>(?:19|20)\d{2}))?"
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_NUMBER_WORDS = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10}

# "the 3rd time", "on 2nd day of my period", "on 5 mg" are counts or amounts, not dates.
_NOT_A_DAY = r"(?!\s*(?:time|times|day|days|week|weeks|month|months|dose|doses|attempt|try|floor|round|set|sets|rep|reps|hour|hours|min|mins|minutes|mg|ml|g|kg|km|%|am|pm|o'?clock|:|\.\d))"
_ISO = re.compile(r"\b(?P<year>20\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
# Day first, as written in India: 20/09/2026. Without a year only after "on" ("on 20/9"), so "pain 6/10" is never a date.
_NUMERIC = re.compile(r"\b(?P<day>\d{1,2})[/.-](?P<month>\d{1,2})[/.-](?P<year>(?:20)?\d{2})\b")
_NUMERIC_ON = re.compile(r"\bon\s+(?P<day>\d{1,2})[/.-](?P<month>\d{1,2})\b(?![/.-]\d)")
_DAY_MONTH = re.compile(r"\b(?P<day>\d{1,2})" + _ORD + r"\s+(?:of\s+)?" + _MONTH.format(name="month") + _YEAR + r"\b", re.I)
_MONTH_DAY = re.compile(r"\b" + _MONTH.format(name="month") + r"\s+(?:the\s+)?(?P<day>\d{1,2})(?P<ord>st|nd|rd|th)?\b" + _NOT_A_DAY + _YEAR, re.I)
# A day of the month alone: "on the 20th", "on 20th", "20th ko" (the latest such day, never a future one).
_DAY_ONLY = re.compile(
    r"\b(?:on\s+(?:the\s+(?P<a>\d{1,2})(?:st|nd|rd|th)?|(?P<b>\d{1,2})(?:st|nd|rd|th))|(?P<c>\d{1,2})(?:st|nd|rd|th)\s+ko)\b" + _NOT_A_DAY, re.I)
_DAY_BEFORE_YESTERDAY = re.compile(r"\bday before yesterday\b", re.I)
_YESTERDAY = re.compile(r"\byesterday\b", re.I)
_DAYS_AGO = re.compile(r"\b(?P<n>\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\s+days?\s+ago\b", re.I)
_A_WEEK_AGO = re.compile(r"\b(?:a|one)\s+week\s+ago\b", re.I)
_WEEKDAY = re.compile(r"\b(?:(?P<last>last|this past)\s+|on\s+)(?P<weekday>" + "|".join(_WEEKDAYS) + r")\b", re.I)
_TODAY = re.compile(r"\b(?:today|this morning|this afternoon|this evening|tonight|right now|now|currently|aaj|abhi)\b", re.I)


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _bounded(day: date | None, today: date) -> date | None:
    if day is None or day > today or (today - day).days > MAX_DAYS_BACK:
        return None
    return day


def _calendar(month: int, day: int, year: str | None, today: date) -> date | None:
    if year:
        y = int(year)
        return _bounded(_safe(y + 2000 if y < 100 else y, month, day), today)
    # No year: this year's date when it has already happened, never a future one.
    return _bounded(_safe(today.year, month, day), today)


def _day_of_month(day: int, today: date) -> date | None:
    if not 1 <= day <= 31:
        return None
    if day <= today.day:
        return _safe(today.year, today.month, day)
    year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return _bounded(_safe(year, month, day), today)


def find_dates(text: str, today: date) -> list[tuple[int, date]]:
    """Every explicit past day in `text` with where it starts, in reading order. Overlapping wordings count once."""
    found: list[tuple[int, int, date]] = []

    def add(match: re.Match, day: date | None) -> None:
        # A wording that names a day we refuse (a future one, an impossible one) still claims its words, so a
        # shorter pattern cannot re-read part of it: "on 20 December" must not become "on the 20th".
        start, end = match.span()
        if any(start < e and s < end for s, e, _d in found):
            return
        found.append((start, end, day))

    s = text or ""
    for m in _ISO.finditer(s):
        add(m, _bounded(_safe(int(m["year"]), int(m["month"]), int(m["day"])), today))
    for m in _NUMERIC.finditer(s):
        add(m, _calendar(int(m["month"]), int(m["day"]), m["year"], today))
    for m in _DAY_MONTH.finditer(s):
        add(m, _calendar(_MONTHS[m["month"].lower()], int(m["day"]), m["year"], today))
    for m in _MONTH_DAY.finditer(s):
        if m["month"].lower() == "may" and not m["ord"] and not re.search(r"\b(?:on|in|since|from)\s+$", s[:m.start()], re.I):
            continue  # "I may 2 times": the verb, not the month
        add(m, _calendar(_MONTHS[m["month"].lower()], int(m["day"]), m["year"], today))
    for m in _NUMERIC_ON.finditer(s):
        add(m, _calendar(int(m["month"]), int(m["day"]), None, today))
    for m in _DAY_ONLY.finditer(s):
        add(m, _day_of_month(int(m["a"] or m["b"] or m["c"]), today))
    for m in _DAY_BEFORE_YESTERDAY.finditer(s):
        add(m, today - timedelta(days=2))
    for m in _YESTERDAY.finditer(s):
        add(m, today - timedelta(days=1))
    for m in _DAYS_AGO.finditer(s):
        raw = m["n"].lower()
        n = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
        add(m, _bounded(today - timedelta(days=n), today))
    for m in _A_WEEK_AGO.finditer(s):
        add(m, today - timedelta(days=7))
    for m in _WEEKDAY.finditer(s):
        back = (today.weekday() - _WEEKDAYS.index(m["weekday"].lower())) % 7
        add(m, today - timedelta(days=back or 7))   # "on monday" said on a Monday means last week's
    for m in _TODAY.finditer(s):
        add(m, today)
    return [(start, day) for start, _end, day in sorted(found, key=lambda item: item[0]) if day is not None]


def stated_date(text: str, today: date) -> date | None:
    """The one day the text names, or None when it names none or several different days."""
    days = {day for _pos, day in find_dates(text, today)}
    return days.pop() if len(days) == 1 else None


def user_today(now_utc: datetime | None = None) -> date:
    """The person's own calendar day: the timezone the app sent with this request (X-Tz-Offset-Minutes), else UTC.
    In India the UTC day is the wrong day for 5.5 hours every night."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    try:
        from wellness_common import request_tz  # imported here: wellness_common pulls in the storage modules
        offset = max(-840, min(840, int(request_tz() or 0)))
    except Exception:  # noqa: BLE001 - a missing or odd timezone falls back to UTC
        offset = 0
    return (now_utc.astimezone(timezone.utc) + timedelta(minutes=offset)).date()


def day_phrase(day: str | date, today: date) -> str:
    """"today", "yesterday" or "on 20 September" (the year only when it is not this year)."""
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    if d == today:
        return "today"
    if d == today - timedelta(days=1):
        return "yesterday"
    return f"on {d.day} {d:%B}" + (f" {d.year}" if d.year != today.year else "")
