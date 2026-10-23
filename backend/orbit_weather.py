"""Partner weather: a soft, deniable nudge for the person you are paired with, built from what the other person chose to share (plan 7.5).

Privacy by construction, in code:

* The input is only a yes/no ("a heavier week" or not) computed from the sharer's own mood, stress and sleep. It never carries a number, a date of a
  log, a note or a word of chat. Nothing in this module reads a log; ``orbit.py`` reduces the logs to that one boolean before calling here.
* The output is one of twenty fixed, kind, generic lines. No line names a feeling, a log or a body.
* A heavy week raises the chance of a *gentle* line (seven in ten) but a calm week still gets one three times in ten, so a gentle line proves nothing.
* At most one line in any three days, and it stays the same for those three days: the line is a function of the pair and the three-day window, not of
  when the partner opened the app. A line is never first chosen within twelve hours of the sharer logging something.
* No line, or a line only some of the time, is normal: about three windows in ten show nothing at all.

The functions are pure. ``orbit.py`` owns the storage, the consent checks, the Safe Harbor pause and the pair.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

WINDOW_DAYS = 3
LOG_QUIET_HOURS = 12
SHOW_SHARE = 0.7            # share of windows that show any line at all
GENTLE_IF_HEAVY = 0.7
GENTLE_IF_CALM = 0.3        # "gentle lines also appear in calm weeks": at least three in ten of all calm-week lines

#: (id, tier, line). Every line is kind and general; none can be read as a report on the other person.
LINES: tuple[tuple[str, str, str], ...] = (
    ("g1", "gentle", "This might be a good week for small kindnesses."),
    ("g2", "gentle", "Ask how their day really was."),
    ("g3", "gentle", "A little extra patience could go a long way this week."),
    ("g4", "gentle", "Offer to take one small thing off their plate."),
    ("g5", "gentle", "A quiet evening together might be welcome."),
    ("g6", "gentle", "Check in with a short message, no reply needed."),
    ("g7", "gentle", "Listening without fixing can be the best gift this week."),
    ("g8", "gentle", "Make their favourite tea or coffee without being asked."),
    ("g9", "gentle", "A hug at the end of the day can say a lot."),
    ("g10", "gentle", "Be the calm in the room this week."),
    ("l1", "light", "Plan something relaxed this weekend."),
    ("l2", "light", "Send a message just because."),
    ("l3", "light", "Share something that made you smile today."),
    ("l4", "light", "Cook or order something you both like."),
    ("l5", "light", "A short walk together could be nice."),
    ("l6", "light", "Try a new small thing together this week."),
    ("l7", "light", "Say one thing you appreciate about them."),
    ("l8", "light", "Put the phones away for a while tonight."),
    ("l9", "light", "Look through some old photos together."),
    ("l10", "light", "Pick a song for the two of you."),
)
LINE_TEXT = {i: text for i, _tier, text in LINES}
TIER = {i: tier for i, tier, _text in LINES}

#: words no line may ever contain (a test holds this): nothing that names a log, a feeling or a body
BANNED = ("sleep", "mood", "stress", "period", "cycle", "anxious", "anxiety", "sad", "depress", "tired", "low", "log", "symptom", "pain", "angry", "worried",
          "unwell", "sick", "pms", "hormon", "cry")


def window_index(now: datetime) -> int:
    """The three-day window this moment falls in (counted from the Unix epoch)."""
    return int(now.astimezone(timezone.utc).timestamp() // (WINDOW_DAYS * 86400))


def _u(*parts: object) -> float:
    """A stable number in [0, 1) from the parts."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def ready(last_log_at: datetime | None, now: datetime) -> bool:
    """False within twelve hours of the sharer's newest log: a line is never first chosen right after something was logged."""
    return last_log_at is None or now - last_log_at >= timedelta(hours=LOG_QUIET_HOURS)


def pick(heavy: bool, pair_key: str, window: int) -> str | None:
    """The line id for this pair in this window, or None (a quiet window). The same inputs always give the same answer."""
    if _u(pair_key, window, "show") >= SHOW_SHARE:
        return None
    gentle = _u(pair_key, window, "tier") < (GENTLE_IF_HEAVY if heavy else GENTLE_IF_CALM)
    pool = [i for i, tier, _t in LINES if (tier == "gentle") == gentle]
    return pool[int(_u(pair_key, window, "line") * len(pool)) % len(pool)]


def heavy_week(mood_values: list[float], stress_values: list[float], sleep_hours: list[float]) -> bool | None:
    """True for a heavier week, False for a calm one, None when there is too little to say. The numbers stay in this function."""
    signals = 0
    seen = 0
    if len(mood_values) >= 2:
        seen += 1
        signals += (sum(mood_values) / len(mood_values)) <= 4
    if stress_values:
        seen += 1
        signals += max(stress_values) >= 7
    if len(sleep_hours) >= 3:
        seen += 1
        signals += (sum(sleep_hours) / len(sleep_hours)) < 6
    return None if not seen else signals >= 1


def describe_possible() -> list[dict[str, str]]:
    """Exactly what a partner could ever be shown, for the sharer's preview. No input, no state: just the twenty lines."""
    return [{"id": i, "text": text} for i, _tier, text in LINES]
