"""Ask your own data: questions about the person's own logs, answered by Bubbles itself (no outside model).

Pure: ``detect`` reads a message, ``answer`` turns the person's daily series into a friendly, honest reply. "How did I sleep this week?", "am I
drinking enough water?", "what was my best mood day?" never need a model: the numbers are in the person's own logs. A missing log is said out loud, never
guessed and never read as fine. Only sleep, mood, water and movement are answered here; weight and food have their own safeguards in Fitness, and "why"
or "how can I" questions are for the model (which is then handed a sheet of these same numbers, see brain_facts.py).
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from statistics import mean
from typing import Any

# topic -> (series name, label in English, label in Hinglish, unit)
TOPICS: dict[str, dict[str, str]] = {
    "sleep": {"series": "sleep_hours", "en": "sleep", "hi": "neend"},
    "mood": {"series": "mood", "en": "mood", "hi": "mood"},
    "water": {"series": "hydration_ml", "en": "water", "hi": "paani"},
    "activity": {"series": "activity_minutes", "en": "movement", "hi": "activity"},
}
TOPIC_WORDS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep", "slept", "sleeping", "neend", "soya", "soyi", "so paya", "so payi"),
    "mood": ("mood",),
    "water": ("water", "hydrat", "paani", "pani"),
    "activity": ("activity", "active", "workout", "exercise", "exercised", "walk", "walked", "walking", "movement", "move", "moved", "moving"),
}

_ASKS_ABOUT_ME = re.compile(
    r"\b(?:my|mine|i\s+(?:slept|drank|walked|exercised|worked out|have|had|did|was|been)|(?:did|have|was|am|has|do)\s+i|me)\b|"
    r"\b(?:mera|meri|mere|maine|mujhe|main)\b|\b(?:pichle|is)\s+hafte\s+ka\b", re.I)
_QUESTION = re.compile(
    r"\?|^\s*(?:how|what|which|when|did|do|am|is|are|was|were|has|have|show|tell|check|give|batao|bata|dikhao|kitna|kitni|kitne|kaisa|kaisi|kya|kab)\b|"
    r"\b(?:summary|average|avg|compare|compared|batao|bata do|dikhao|kaisa|kaisi|kitna|kitni|kitne)\b", re.I)
# advice and "why" questions are for the model, which then gets these numbers as facts
_NOT_A_DATA_QUESTION = re.compile(
    r"\bhow\s+(?:can|do|to|should|could|would)\b|\bwhat\s+should\b|\bwhy\b|\btips?\b|\badvice\b|\bimprove\b|\bhelp\s+me\b|\bsuggest|\bsleep(?:ing)?\s+better\b(?!\s+than)|\bsleep\s+more\b|"
    r"\bapnea\b|\bdeficien\w+|\bcan\s+you\b|\bfix\b|\bdisorder\b|\bkaise\b|\bkya\s+karu\b|\bkarna\s+chahiye\b|\bkyun\b|\bkyu\b|\bshould\s+i\b|\bcan\s+i\b|\bhow\s+much\s+(?:should|do\s+i\s+need|is\s+too)\b|\bneed\s+to\b|\bdo\s+i\s+need\b|\bhow\s+(?:much|many)\s+\w+\s+(?:should|do\s+i\s+need|is\s+(?:too|enough|good))\b", re.I)
_LAST = re.compile(r"\blast\s+night\b|\btoday\b|\byesterday\b|\bthis\s+morning\b|\baaj\b|\bkal\s+raat\b|\bkal\b|\braat\s+ko\b", re.I)
_LAST_WEEK = re.compile(r"\blast\s+week\b|\bpichle\s+hafte\b", re.I)
_MONTH = re.compile(r"\bmonth\b|\b30\s+days\b|\bmahine\b|\bmahina\b", re.I)
_TWO_WEEKS = re.compile(r"\b(?:2|two)\s+weeks\b|\b14\s+days\b|\bfortnight\b", re.I)
_BEST = re.compile(r"\bbest\b|\bmost\b|\bhighest\b|\blongest\b|\bhappiest\b|\bsabse\s+(?:acha|accha|zyada)\b", re.I)
_WORST = re.compile(r"\bworst\b|\bleast\b|\blowest\b|\bshortest\b|\bsabse\s+(?:kam|bura)\b", re.I)
_COMPARE = re.compile(r"\bcompar\w+|\bbetter\s+than\b|\bworse\s+than\b|\bimprov\w+\b|\btrend\b|\bgetting\s+(?:better|worse)\b|\bbadh\b|\bghat\b", re.I)
_ENOUGH = re.compile(r"\benough\b|\bkaafi\b|\bkafi\b|\bpurana\b|\bpura\b", re.I)

WEEKDAYS_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
GLASS_ML = 250
SLEEP_NEED = (7.0, 9.0)       # the usual adult range; individual needs differ
ACTIVITY_WEEK_MINUTES = 150   # the usual adult guide for a week of moderate movement
MIN_DAYS_FOR_TREND = 3


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def detect(text: str) -> dict[str, Any] | None:
    """The data question being asked, or None. ``{"topic", "kind", "days", "offset"}`` with kind in last, summary, best, worst, compare, enough."""
    t = _norm(text)
    if not t or len(t) > 160 or _NOT_A_DATA_QUESTION.search(t):
        return None
    topics = [k for k, words in TOPIC_WORDS.items() if any(w in t for w in words)]
    if len(topics) != 1 or not _QUESTION.search(t) or not _ASKS_ABOUT_ME.search(t):
        return None
    topic = topics[0]
    if _BEST.search(t):
        kind = "best"
    elif _WORST.search(t):
        kind = "worst"
    elif _COMPARE.search(t):
        kind = "compare"
    elif _ENOUGH.search(t):
        kind = "enough"
    elif _LAST.search(t) and not re.search(r"\bweek\b|\bhafte\b", t):
        kind = "last"
    else:
        kind = "summary"
    days = 30 if _MONTH.search(t) else 14 if _TWO_WEEKS.search(t) else 7
    return {"topic": topic, "kind": kind, "days": days, "offset": 7 if _LAST_WEEK.search(t) and kind == "summary" else 0}


# ---- numbers -----------------------------------------------------------------------------------------------------------------

Series = dict[date, float | None]


def window(series: Series, today: date, days: int, offset: int = 0) -> dict[date, float]:
    """The logged values (never a missing day counted as zero) in the ``days`` days ending ``offset`` days before today."""
    end = today - timedelta(days=offset)
    start = end - timedelta(days=days - 1)
    return {d: v for d, v in series.items() if v is not None and start <= d <= end}


def hours(h: float) -> str:
    total = int(round(h * 60))
    return f"{total // 60} h {total % 60:02d} min" if total % 60 else f"{total // 60} h"


def fmt(topic: str, value: float) -> str:
    if topic == "sleep":
        return hours(value)
    if topic == "water":
        return f"{value / 1000:.1f} L" if value >= 1000 else f"{int(round(value))} ml"
    if topic == "activity":
        return f"{int(round(value))} min"
    return f"{value:.1f}".rstrip("0").rstrip(".") + "/10"


def _day(d: date, today: date) -> str:
    if d == today:
        return "today"
    if d == today - timedelta(days=1):
        return "yesterday"
    return WEEKDAYS_EN[d.weekday()] + (" " + d.strftime("%d %b").lstrip("0") if (today - d).days > 6 else "")


def _pick(seed: str, options: tuple[str, ...]) -> str:
    return options[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


def _change_words(topic: str, now: float, before: float) -> str | None:
    """"a little lower than the week before", or None when the two are close (within a tenth of the earlier one, or half a mood point)."""
    diff = now - before
    close = 0.5 if topic == "mood" else max(0.1 * abs(before), 1e-9)
    if abs(diff) < close:
        return None
    size = "a lot" if abs(diff) >= 3 * close else "a little"
    if topic == "sleep":
        mins = int(round(abs(diff) * 60 / 5) * 5)
        return f"about {mins} minutes {'more' if diff > 0 else 'less'} a night than the week before"
    return f"{size} {'higher' if diff > 0 else 'lower'} than the week before"


# ---- the answer --------------------------------------------------------------------------------------------------------------

def answer(intent: dict[str, Any], series: dict[str, Series], today: date, *, name: str | None = None, language: str = "en", seed: str = "") -> str:
    """A friendly reply from the person's own logs. Never raises on missing data: a gap is the answer."""
    topic, kind, days, offset = intent["topic"], intent["kind"], intent["days"], intent.get("offset", 0)
    spec = TOPICS[topic]
    data: Series = series.get(spec["series"], {}) or {}
    hinglish = language == "hi-latn"
    label = spec["hi" if hinglish else "en"]
    hi = f" {name}" if name else ""
    seed = seed or f"{topic}{kind}"

    if kind == "last":
        return _last(topic, data, today, label, hinglish, hi, seed)
    win = window(data, today, days, offset)
    if not win:
        return _gap(topic, label, days, hinglish, hi, offset)
    if kind in ("best", "worst"):
        return _extreme(topic, win, today, label, kind, days, hinglish)
    if kind == "compare":
        return _compare(topic, data, today, label, days, hinglish)
    if kind == "enough":
        return _enough(topic, win, days, label, hinglish)
    return _summary(topic, data, win, today, label, days, offset, hinglish, hi, seed)


def _gap(topic: str, label: str, days: int, hinglish: bool, hi: str, offset: int = 0) -> str:
    when = "that week" if offset else ("the last week" if days <= 7 else f"the last {days} days")
    if hinglish:
        return f"Mujhe{hi} {label} ka koi log nahi mila {'us hafte' if offset else 'pichle ' + str(days) + ' din'} ka. Jo yaad hai bata do, main note kar leta hoon aur phir saath dekhte hain."
    return f"I don't have any {label} logged for {when} yet, so I'd only be guessing. Tell me how it's been and I'll note it, then we can look at it together."


def _last(topic: str, data: Series, today: date, label: str, hinglish: bool, hi: str, seed: str) -> str:
    recent = [(d, v) for d, v in data.items() if v is not None and today - timedelta(days=1 if topic == "sleep" else 0) <= d <= today]
    if topic == "sleep":
        recent = [(d, v) for d, v in data.items() if v is not None and d >= today - timedelta(days=1)]
    if not recent:
        if hinglish:
            return f"Abhi tak {label} ka log nahi dikh raha. Batao kaisa raha, main likh leta hoon?"
        what = {"sleep": "last night's sleep", "water": "any water today", "activity": "any movement today", "mood": "a mood check today"}[topic]
        return _pick(seed, (f"I don't see {what} logged yet. Tell me how it went and I'll note it?",
                            f"Nothing logged for {what.replace('any ', '').replace('a ', '')} yet. Want to tell me now?"))
    d, v = max(recent)
    usual = [x for dd, x in data.items() if x is not None and dd != d and today - timedelta(days=14) <= dd <= today]
    context = ""
    if len(usual) >= 3:
        diff = v - mean(usual)
        close = 0.5 if topic == "mood" else 0.1 * mean(usual)
        if abs(diff) >= close:
            context = (" That is a bit " + ("above" if diff > 0 else "below") + f" your usual {fmt(topic, mean(usual))}.") if not hinglish else (
                " Tumhare usual " + fmt(topic, mean(usual)) + " se " + ("zyada" if diff > 0 else "kam") + " hai.")
        else:
            context = f" About your usual {fmt(topic, mean(usual))}." if not hinglish else f" Tumhare usual {fmt(topic, mean(usual))} jaisa hi."
    when = _day(d, today)
    if hinglish:
        return f"{'Kal raat' if topic == 'sleep' and when != 'today' else 'Aaj'} ka {label}: {fmt(topic, v)}.{context}"
    lead = {"sleep": f"You slept {fmt(topic, v)}", "mood": f"You logged your mood as {fmt(topic, v)}", "water": f"You've had {fmt(topic, v)} of water",
            "activity": f"You've moved for {fmt(topic, v)}"}[topic]
    suffix = {"sleep": " last night" if when in ("today", "yesterday") else f" ({when})", "mood": f" {when}", "water": " today", "activity": " today"}[topic]
    return f"{lead}{suffix}.{context}"


def _summary(topic: str, data: Series, win: dict[date, float], today: date, label: str, days: int, offset: int, hinglish: bool, hi: str, seed: str) -> str:
    n, avg = len(win), mean(win.values())
    span = f"{days} din" if hinglish else (f"the last {days} days" if days > 7 else "the last 7 days")
    unit_logged = {"sleep": "nights", "mood": "days", "water": "days", "activity": "days"}[topic]
    total_bits = ""
    if topic == "water":
        total_bits = f" (about {avg / GLASS_ML:.1f} glasses)"
    before = window(data, today, days, offset + days)
    change = _change_words(topic, avg, mean(before.values())) if len(before) >= MIN_DAYS_FOR_TREND and n >= MIN_DAYS_FOR_TREND else None
    low, high = min(win, key=win.get), max(win, key=win.get)
    note = ""
    if n < MIN_DAYS_FOR_TREND:
        note = " Only " + (f"{n} {unit_logged[:-1] if n == 1 else unit_logged}" if not hinglish else f"{n} din") + " so far, so take it lightly."
        if hinglish:
            note = f" Abhi sirf {n} din ka data hai, to ise halke mein lena."
    if hinglish:
        lead = _pick(seed, (f"Pichle {span} mein tumne {n} din {label} log kiya, average {fmt(topic, avg)} raha.", f"{span.capitalize()} ka {label}: {n} din ke log se average {fmt(topic, avg)}."))
        extra = f" Pichle hafte se {change.replace('about ', '').replace('a night than the week before', 'kam/zyada')}." if change and topic != "sleep" else ""
        return lead + extra + note
    lead = _pick(seed, (f"Over {span}, you logged {label} on {n} {unit_logged[:-1] if n == 1 else unit_logged} and it averaged {fmt(topic, avg)}{total_bits}.",
                        f"Here's {span} of {label} from your logs: {n} {unit_logged[:-1] if n == 1 else unit_logged} logged, averaging {fmt(topic, avg)}{total_bits}."))
    parts = [lead]
    if change:
        parts.append(f"That's {change}.")
    if n >= MIN_DAYS_FOR_TREND and low != high:
        parts.append(f"Lowest was {fmt(topic, win[low])} ({_day(low, today)}), highest {fmt(topic, win[high])} ({_day(high, today)}).")
    if note:
        parts.append(note.strip())
    return " ".join(parts)


def _extreme(topic: str, win: dict[date, float], today: date, label: str, kind: str, days: int, hinglish: bool) -> str:
    pick = max if kind == "best" else min
    d = pick(win, key=win.get)
    word = {"sleep": ("longest", "shortest"), "mood": ("highest", "lowest"), "water": ("most", "least"), "activity": ("most active", "least active")}[topic][0 if kind == "best" else 1]
    span = f"the last {days} days" if days > 7 else "this week"
    if len(win) < 2:
        return f"I only have one {label} entry for {span} ({fmt(topic, win[d])}, {_day(d, today)}), so there's nothing to compare it with yet."
    if hinglish:
        return f"Pichle {days} din mein sabse {'zyada' if kind == 'best' else 'kam'} {label}: {fmt(topic, win[d])} ({_day(d, today)})."
    return f"Your {word} day for {label} in {span} was {_day(d, today)}: {fmt(topic, win[d])}. That's from the {len(win)} days you logged."


def _compare(topic: str, data: Series, today: date, label: str, days: int, hinglish: bool) -> str:
    now, before = window(data, today, days), window(data, today, days, days)
    if len(now) < MIN_DAYS_FOR_TREND or len(before) < MIN_DAYS_FOR_TREND:
        return (f"I need at least {MIN_DAYS_FOR_TREND} days of {label} in each of the two weeks to compare them fairly, and I don't have that yet "
                f"({len(now)} this time, {len(before)} the time before). A few more logs and I can.") if not hinglish else (
            f"Compare karne ke liye dono hafton mein kam se kam {MIN_DAYS_FOR_TREND} din ka {label} chahiye. Abhi {len(now)} aur {len(before)} din hain.")
    a, b = mean(now.values()), mean(before.values())
    change = _change_words(topic, a, b)
    if hinglish:
        return f"Is baar {label} average {fmt(topic, a)}, pichli baar {fmt(topic, b)}." + ("" if change else " Lagbhag same hai.")
    if change is None:
        return f"Your {label} is about the same: averaging {fmt(topic, a)} against {fmt(topic, b)} the time before."
    return f"Your {label} averaged {fmt(topic, a)} against {fmt(topic, b)} before, which is {change}. It's a pattern in what you logged, not a verdict."


def _enough(topic: str, win: dict[date, float], days: int, label: str, hinglish: bool) -> str:
    avg, n = mean(win.values()), len(win)
    if topic == "sleep":
        lo, hi = SLEEP_NEED
        verdict = ("a little under" if avg < lo else "within" if avg <= hi else "above")
        base = f"You've averaged {fmt(topic, avg)} over {n} logged nights, which is {verdict} the 7 to 9 hours most adults do well on."
        tail = " People differ, so how rested you feel matters more than the number." if verdict != "within" else " If you feel rested, that's a good sign."
        return base + tail
    if topic == "activity":
        weekly = avg * 7
        verdict = "under" if weekly < ACTIVITY_WEEK_MINUTES else "at or above"
        return (f"You've averaged {fmt(topic, avg)} a day, roughly {int(round(weekly))} minutes a week, which is {verdict} the 150 minutes a week adults are usually "
                "encouraged to aim for. Any movement counts, and gentle days are fine.")
    if topic == "water":
        return (f"You've averaged {fmt(topic, avg)} a day on the {n} days you logged (about {avg / GLASS_ML:.1f} glasses). Needs vary with weather and activity; pale "
                "yellow pee and rarely feeling thirsty are good signs. I only know what you log, so unlogged sips aren't counted.")
    return f"I can't say what's \"enough\" for {label}, but over {n} days you've averaged {fmt(topic, avg)}."
