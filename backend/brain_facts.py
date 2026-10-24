"""Making the model's job easy: a short sheet of what Bubbles already worked out from the person's own logs.

When a message still needs the model ("why am I so tired lately?"), Bubbles hands it the numbers it has already computed (last night, the week's average,
the week before, shortest and longest) for the things the message touches, with the rule to quote them exactly and invent no others. The model then
explains and connects instead of recalling, answers are shorter and better grounded, and a number that is not in the sheet or in the person's message is
flagged by the reply check. Pure: ``series_needed`` reads the message, ``sheet`` writes the text.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from statistics import mean

import data_answers as da

HEADER = ("WHAT BUBBLES ALREADY KNOWS (worked out from this person's own logs; quote these numbers exactly, never invent others, and a topic marked "
          "\"nothing logged\" has no data, so do not guess about it):")
_ENERGY = re.compile(r"\b(?:tired|tiredness|energy|exhaust\w*|fatigue\w*|drained|sluggish|lazy|thak\w*)\b", re.I)
_FEELING = re.compile(r"\b(?:stress\w*|anxi\w*|worried|mood|low|sad|down|irritable|overwhelm\w*)\b", re.I)
_RELATIONSHIP = re.compile(r"\b(?:boyfriend|girlfriend|husband|wife|partner|bf|gf|relationship|fight|fought|argu\w+|breakup|break\s*up|ex)\b", re.I)
_LATELY = re.compile(r"\b(?:lately|recently|this\s+week|these\s+days|past\s+(?:week|few\s+days))\b", re.I)


def series_needed(text: str) -> set[str]:
    """The names of the daily series the message touches (sleep_hours, mood, hydration_ml, activity_minutes). Empty when it touches none."""
    t = str(text or "").lower()
    topics = {k for k, words in da.TOPIC_WORDS.items() if any(w in t for w in words)}
    if _ENERGY.search(t):
        topics |= {"sleep", "water", "activity", "mood"}
    if _FEELING.search(t) or _RELATIONSHIP.search(t):
        topics |= {"sleep", "mood", "activity"}
    return {da.TOPICS[k]["series"] for k in topics}


_LABEL = {"sleep_hours": ("sleep", "sleep"), "mood": ("mood", "mood"), "hydration_ml": ("water", "water"), "activity_minutes": ("activity", "movement")}


def _line(series_name: str, data: da.Series, today: date) -> str:
    topic, label = _LABEL[series_name]
    week, before = da.window(data, today, 7), da.window(data, today, 7, 7)
    if not da.window(data, today, 14):
        return f"- {label}: nothing logged in the last 14 days"
    bits = []
    last = [(d, v) for d, v in data.items() if v is not None and d >= today - timedelta(days=1)]
    if last:
        d, v = max(last)
        bits.append(f"{'last night' if topic == 'sleep' else 'latest'} {da.fmt(topic, v)} ({da._day(d, today)})")
    if week:
        bits.append(f"last 7 days average {da.fmt(topic, mean(week.values()))} over {len(week)} day{'s' if len(week) != 1 else ''} logged")
        if len(week) >= 2:
            lo, hi = min(week, key=week.get), max(week, key=week.get)
            bits.append(f"lowest {da.fmt(topic, week[lo])} ({da._day(lo, today)}), highest {da.fmt(topic, week[hi])} ({da._day(hi, today)})")
    else:
        bits.append("nothing logged in the last 7 days")
    if before:
        bits.append(f"the week before averaged {da.fmt(topic, mean(before.values()))} over {len(before)} day{'s' if len(before) != 1 else ''}")
    return f"- {label}: " + "; ".join(bits)


def mentions_relationship(text: str) -> bool:
    return bool(_RELATIONSHIP.search(str(text or "")))


def tension_line(days: list[date], today: date) -> str:
    """One line about the days the person told Bubbles they had a fight with a partner (a date-only marker), so a bad night can be read next to it."""
    recent = sorted(d for d in days if today - timedelta(days=14) <= d <= today)
    if not recent:
        return "- tension days with a partner: none marked in the last 14 days"
    shown = ", ".join(da._day(d, today) for d in recent[-4:])
    return f"- tension days with a partner (days they told Bubbles about a fight): {len(recent)} in the last 14 days ({shown})"


def sheet(series: dict[str, da.Series], today: date, names: set[str], extra: list[str] | None = None) -> str:
    """The text block, or "" when there is nothing to say (no series asked for)."""
    order = [n for n in ("sleep_hours", "mood", "hydration_ml", "activity_minutes") if n in names]
    if not order:
        return ""
    return HEADER + "\n" + "\n".join([_line(n, series.get(n, {}) or {}, today) for n in order] + list(extra or []))
