"""Deterministic parser for rich, natural-language daily health logs.

Users should be able to write "I slept 6h 42m, oats and banana for breakfast,
walked 6,420 steps, period day 3, cramps 4/10 ..." without a form. This module
pulls out the *explicitly stated* measurements only. Nothing is inferred or
filled in: a log with no sleep mention produces no sleep metric, a log that says
"no medication" produces an explicit empty medication list, and reference
nutrition estimates are labelled as estimates and only attached to foods that
exist in Bubbles' food reference.

Symptoms, denials and temporal status come from ``health_semantics`` (passed in
as ``facts``); this module owns the numeric/lexical metrics around them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from event_dates import day_phrase, stated_date, user_today
from health_semantics import MEDICATION_NAME_PATTERN, Fact, display_name, normalize, split_sentences

_NUM = r"(\d+(?:[.,]\d+)?)"
_I = re.I
# Units are written longest-first with a word boundary: "6 hours 42 minutes" must never be read as "6 h" + "ours".
_HR_U = r"(?:hours?|hrs?|h)\b"
_MIN_U = r"(?:minutes?|mins?|m)\b"


def _num(text: str) -> float:
    t = text.strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", t):
        return float(t.replace(",", ""))
    return float(t.replace(",", "."))


# --------------------------------------------------------------------------
# Sleep
# --------------------------------------------------------------------------
_SLEEP_HM = re.compile(
    r"(?:slept|sleep(?:ing)?|asleep|sleep (?:duration|time|total))\D{0,25}?(\d{1,2})\s*" + _HR_U + r"\s*(?:and\s*)?(?:(\d{1,2})\s*" + _MIN_U + r")?", _I)
_SLEEP_HM_REV = re.compile(r"(\d{1,2})\s*" + _HR_U + r"\s*(?:and\s*)?(?:(\d{1,2})\s*" + _MIN_U + r")?\s*(?:of\s+)?sleep\b", _I)
_SLEEP_DEC = re.compile(r"(?:slept|sleep(?:ing)?)\D{0,15}?" + _NUM + r"\s*" + _HR_U + r"|" + _NUM + r"\s*" + _HR_U + r"\s*(?:of\s+)?sleep\b", _I)
_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?"
_BEDTIME = re.compile(r"(?:went to (?:bed|sleep)|bed ?time|in bed|bed at|bed|fell asleep|lights out|slept at|asleep at)\s*(?:at|around|by|~|:)?\s*" + _TIME, _I)
_WAKE = re.compile(
    r"(?:woke(?: up)?|wake(?:[- ]?up)?(?: time)?|got up|waking up|up)\s*(?:at|around|by|~|:)\s*" + _TIME
    + r"|(?:woke(?: up)?|wake(?:[- ]?up)?|got up)\s+(\d{1,2}:\d{2})\s*(am|pm)?"
    + r"|\bup\s+(\d{1,2}:\d{2})\s*(am|pm)?", _I)
# "Slept from 22:50 to 06:30" / "slept 10pm-6am": both ends must be clock times (a colon or am/pm), never bare numbers
_SLEEP_RANGE = re.compile(r"(?:slept|sleep|asleep|in bed)\s*(?:from|between)?\s*" + _TIME + r"\s*(?:to|until|till|-|–|—|and)\s*" + _TIME, _I)
_AWAKE = re.compile(r"woke up\s+(?:(\d+)|(once|twice)|(three|four|five) times|(a few|several) times)(?:\s+times)?\s*(?:during|in|at)\s+(?:the\s+)?night", _I)
_SLEEP_Q_NUM = re.compile(r"sleep quality\D{0,8}(\d{1,2})\s*/\s*10", _I)
_SLEEP_Q_WORD = re.compile(r"slept\s+(?:very\s+|pretty\s+|quite\s+|fairly\s+)?(great|well|badly|poorly|terribly|okay|ok|fine|deeply|restlessly)", _I)
_SLEEP_Q_MAP = {"great": 9, "deeply": 9, "well": 8, "fine": 6, "okay": 6, "ok": 6, "badly": 3, "poorly": 3, "restlessly": 3, "terribly": 2}

# --------------------------------------------------------------------------
# Cycle
# --------------------------------------------------------------------------
_CYCLE_DAY = re.compile(r"(?:cycle day|period day|\bcd)\s*(\d{1,2})\b|day\s+(\d{1,2})\s+of\s+(?:my\s+)?(?:cycle|period)", _I)
_FLOW = re.compile(r"\b(very heavy|heavy|moderate|medium|light|spotting)\s+(?:flow|bleeding|period)\b|\bflow\W{0,4}(?:is |was |:)?\s*(very heavy|heavy|moderate|medium|light|spotting)\b", _I)
_PERIOD_START = re.compile(r"\b(?:period (?:started|began|came|is here|is on|has started)|started (?:my )?period|on my period|having my period|menstruating)\b", _I)
_PERIOD_END = re.compile(r"\b(?:period (?:ended|stopped|finished|is over|has ended)|(?:ended|finished) (?:my )?period)\b", _I)
# an explicit "not active" beats anything inferred from a cycle day ("Cycle day 14, period not active")
_PERIOD_INACTIVE = re.compile(
    r"\bperiod\s+(?:is\s+)?(?:not|isn't)\s+(?:active|on|here|happening|started)\b|\bperiod\s+(?:is\s+)?inactive\b|"
    r"\bnot\s+(?:on|having)\s+(?:my\s+)?period\b|\bno period\s+(?:today|now)\b", _I)

# --------------------------------------------------------------------------
# Hydration / caffeine / activity / body / vitals
# --------------------------------------------------------------------------
_VOL = r"(l|lit(?:er|re)s?|ml|glass(?:es)?|cups?|bottles?)"
_WATER_A = re.compile(_NUM + r"\s*" + _VOL + r"\s*(?:of\s+)?water", _I)
_WATER_B = re.compile(r"water\D{0,12}?" + _NUM + r"\s*" + _VOL + r"\b", _I)
_WATER_C = re.compile(r"(?:drank|drink|drinking|had)\D{0,15}?" + _NUM + r"\s*(l|lit(?:er|re)s?|ml)\b", _I)
_CAFFEINE = re.compile(r"\b(\d+|a|one|two|three|four|five)\s*(?:cups?|mugs?|glasses?)\s*(?:of\s+)?(coffee|tea|chai|espresso|latte|cappuccino)\b", _I)
# "Coffee: 1 cup", "Tea - 2 cups"
_CAFFEINE_B = re.compile(r"\b(coffee|tea|chai|espresso|latte|cappuccino)\s*[:\-–]\s*(\d+|a|one|two|three|four|five)\s*(?:cups?|mugs?|glasses?)\b", _I)
_STEPS = re.compile(r"\b([\d,]{3,7})\s*steps\b|\bsteps\W{0,6}([\d,]{3,7})\b", _I)
_EXERCISE_WORDS = r"yoga|walk(?:ing)?|run(?:ning)?|jog(?:ging)?|gym|workout|cycling|swim(?:ming)?|exercise|pilates|stretching|dancing|hiking|strength|cardio|zumba"
_EX_A = re.compile(r"\b(\d{1,3})\s*(?:minutes?|mins?)\s*(?:of\s+)?(" + _EXERCISE_WORDS + r")\b", _I)
_EX_B = re.compile(r"\b(" + _EXERCISE_WORDS + r")\s*(?:for|:)?\s*(\d{1,3})\s*(?:minutes?|mins?)\b", _I)
_EX_H = re.compile(r"\b(\d(?:\.\d)?)\s*" + _HR_U + r"\s*(?:of\s+)?(" + _EXERCISE_WORDS + r")\b", _I)
# "Gym for 1 hour 15 minutes" / "1 hour 15 minutes of yoga": hours plus optional minutes
_EX_HM_B = re.compile(r"\b(" + _EXERCISE_WORDS + r")\s*(?:for|:)?\s*(\d(?:\.\d)?)\s*" + _HR_U + r"(?:\s*(?:and\s*)?(\d{1,2})\s*" + _MIN_U + r")?", _I)
_EX_HM_A = re.compile(r"\b(\d(?:\.\d)?)\s*" + _HR_U + r"\s*(?:and\s*)?(\d{1,2})\s*" + _MIN_U + r"\s*(?:of\s+)?(" + _EXERCISE_WORDS + r")\b", _I)
_WEIGHT = re.compile(r"(?:weight|weigh(?:ed|s)?)\D{0,12}?(\d{2,3}(?:\.\d+)?)\s*(kg|kgs|lbs?|pounds)\b", _I)
_HR = re.compile(r"(?:resting\s+)?(?:\bhr\b|heart rate|pulse)\D{0,8}?(\d{2,3})(?:\s*bpm)?", _I)
_BP = re.compile(r"(?:\bbp\b|blood pressure)\D{0,8}?(\d{2,3})\s*/\s*(\d{2,3})", _I)
_TEMP = re.compile(r"\btemp(?:erature)?\D{0,8}?(\d{2,3}(?:\.\d+)?)\s*°?\s*([cf])?\b", _I)
_SPO2 = re.compile(r"(?:spo2|oxygen(?: saturation)?)\D{0,8}?(\d{2,3})\s*%?", _I)

# --------------------------------------------------------------------------
# Mood / energy / stress / nutrition
# --------------------------------------------------------------------------
_MOOD_WORD = r"(stable|calm|happy|good|great|low|sad|irritable|anxious|moody|okay|ok|fine|neutral|flat|content|positive|stressed|up and down|tearful)"
_MOOD_A = re.compile(r"\bmood\s*(?:was|is|:|felt|seems?)?\s*(?:a bit |a little |fairly |pretty |quite |very |mostly |generally |relatively )?" + _MOOD_WORD + r"\b", _I)
_MOOD_B = re.compile(r"\b(?:feeling|felt|feel)\s+(?:a bit |a little |fairly |quite |very |mostly |relatively )?(calm|happy|good|great|sad|irritable|anxious|stable|content|low|moody|stressed|okay|fine)\b", _I)
_MOOD_NUM = re.compile(r"\bmood\W{0,6}(\d{1,2})\s*/\s*10", _I)
_ENERGY_A = re.compile(r"\benergy\s*(?:level)?\s*(?:was|is|:|felt)?\s*(?:a bit |a little |somewhat |quite |very |slightly )?(low|lower|high|higher|moderate|good|ok|okay|fine|normal|drained|great)\b", _I)
_ENERGY_B = re.compile(r"\b(low|lower|high|good|reduced)\s+energy\b", _I)
_ENERGY_NUM = re.compile(r"\benergy\W{0,6}(\d{1,2})\s*/\s*10", _I)
_STRESS_NUM = re.compile(r"\bstress(?:ed)?(?:\s*level)?\W{0,10}(\d{1,2})\s*/\s*10", _I)
_STRESS_WORD = re.compile(r"\bstress(?:\s*level)?\s*(?:was|is|:)?\s*(low|moderate|medium|high|mild)\b", _I)
_ANXIETY_NUM = re.compile(r"\banxiety\W{0,6}(\d{1,2})\s*/\s*10", _I)
_FOCUS = re.compile(r"\bfocus\s*(?:was|is|:)?\s*(good|poor|low|fine|sharp|scattered)\b", _I)
_CALORIES = re.compile(r"\b(\d{3,4})\s*(?:kcal|cal|calories)\b", _I)
_PROTEIN = re.compile(r"\b(\d{1,3})\s*g\s*(?:of\s+)?protein\b|\bprotein\W{0,6}(\d{1,3})\s*g\b", _I)

_SLOT = r"(breakfast|lunch|dinner|brunch|snacks?)"
_SLOT_FOR = re.compile(r"\b(?:for|at)\s+(?:my\s+)?" + _SLOT + r"\b", _I)
_SLOT_HEAD = re.compile(r"\b" + _SLOT + r"\s*(?::|-|–|was|were|had|included)\s*", _I)
_MEALS_HEAD = re.compile(r"\bmeals\s*:\s*", _I)          # "Meals: poha, curd, roti and sabzi" (no slot named)
_SLOT_KW = re.compile(r"\b(?:breakfast|brunch|lunch|dinner|snacks?)\b", _I)
_SLOT_ORDER = ("breakfast", "brunch", "lunch", "snack", "dinner", "meals")
_EAT_VERB = re.compile(r"\b(?:had|ate|eaten|have|having|eating|eat)\s+", _I)
_FOOD_SPLIT = re.compile(r",|\band\b|&|\bwith\b|\+|\bplus\b|\bthen\b", _I)
_FOOD_DET = re.compile(r"^(?:a|an|the|some|my|one|two|three|\d+(?:/\d+)?|(?:a )?(?:bowl|plate|cup|glass|piece|slice|serving|portion|handful) of|few|little)\s+", _I)
_FOOD_STOP = {"nothing", "something", "skipped", "also", "then", "it", "that", "this", "food", "meal", "snack", "lunch", "dinner", "breakfast", "i", "we"}
_SUPPLEMENTS = {"iron", "magnesium", "calcium", "zinc", "folic acid", "folate", "multivitamin", "multivitamins", "probiotic", "probiotics", "melatonin",
                "ashwagandha", "omega-3", "omega 3", "omega3"}

_COUNT_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "once": 1, "twice": 2, "a few": 3, "several": 4}


# --------------------------------------------------------------------------
@dataclass
class DailyLog:
    log_date: str
    metrics: dict[str, Any] = field(default_factory=dict)
    meals: dict[str, list[str]] = field(default_factory=dict)
    meal_phrases: dict[str, list[str]] = field(default_factory=dict)   # the words the user used per slot (quantities kept)
    estimates: dict[str, Any] = field(default_factory=dict)
    domains: set[str] = field(default_factory=set)

    @property
    def is_daily_log(self) -> bool:
        return len(self.domains) >= 3

    def to_dict(self) -> dict[str, Any]:
        return {"log_date": self.log_date, "metrics": self.metrics, "meals": self.meals,
                "estimates": self.estimates, "domains": sorted(self.domains)}


def _clock(h: str, m: str | None, ap: str | None, role: str) -> str | None:
    hour, minute = int(h), int(m) if m else 0
    if minute > 59 or hour > 24:
        return None
    ap = (ap or "").lower().replace(".", "")
    if ap == "pm" and hour < 12:
        hour += 12
    elif ap == "am" and hour == 12:
        hour = 0
    elif not ap and not m:
        return None
    elif not ap:
        if role == "bed" and 7 <= hour <= 11:
            hour += 12
        elif role == "bed" and hour == 12:
            hour = 0
    if hour >= 24:
        return None
    return f"{hour:02d}:{minute:02d}"


def _foods(phrase: str) -> list[str]:
    out: list[str] = []
    for part in _FOOD_SPLIT.split(phrase):
        item = part.strip(" .,:;-–")
        for _ in range(2):
            item = _FOOD_DET.sub("", item).strip()
        item = re.sub(r"\b(?:for|at)\b.*$", "", item).strip().lower()
        if not item or item in _FOOD_STOP or len(item.split()) > 3 or not re.search(r"[a-z]", item) or re.search(r"\d", item):
            continue
        out.append(item)
    return list(dict.fromkeys(out))


def _meals(text: str, raw: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    slots: dict[str, list[str]] = {}
    raw = raw if raw is not None else {}
    prev_end = 0
    for m in _SLOT_FOR.finditer(text):
        sentence_start = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start()), text.rfind("!", 0, m.start())) + 1
        start = max(prev_end, sentence_start)
        phrase = text[start:m.start()]
        verbs = list(_EAT_VERB.finditer(phrase))
        if verbs:
            phrase = phrase[verbs[-1].end():]
        elif start == prev_end and prev_end > sentence_start:
            phrase = phrase.lstrip(" ,;")
        else:
            comma = phrase.rfind(",")
            phrase = phrase[comma + 1:] if comma != -1 else phrase
            phrase = re.sub(r"^\s*(?:i|we)\s+", "", phrase, flags=_I)
        foods = _foods(phrase)
        slot = m.group(1).lower().rstrip("s") if m.group(1).lower().startswith("snack") else m.group(1).lower()
        if foods:
            raw.setdefault(slot, []).append(phrase.strip(" .,:;-"))
            slots.setdefault(slot, [])
            slots[slot] += [f for f in foods if f not in slots[slot]]
        prev_end = m.end()
    # "Breakfast was oats and a banana, lunch was rice and dal": each slot owns only the words up to the NEXT slot word
    heads = [(m.start(), m.end(), m.group(1).lower()) for m in _SLOT_HEAD.finditer(text)]
    heads += [(m.start(), m.end(), "meals") for m in _MEALS_HEAD.finditer(text)]
    heads.sort()
    for k, (_a, b, slot) in enumerate(heads):
        phrase = text[b:b + 160]
        kw = _SLOT_KW.search(phrase)
        if kw:
            phrase = phrase[:kw.start()]
        if k + 1 < len(heads):
            phrase = phrase[:max(0, heads[k + 1][0] - b)]
        phrase = re.split(r"[.;\n!?]", phrase, maxsplit=1)[0]
        slot = "snack" if slot.startswith("snack") else slot
        foods = _foods(phrase)
        if foods:
            raw.setdefault(slot, []).append(phrase.strip(" .,:;-"))
            slots.setdefault(slot, [])
            slots[slot] += [f for f in foods if f not in slots[slot]]
    order = {name: i for i, name in enumerate(_SLOT_ORDER)}
    return dict(sorted(slots.items(), key=lambda kv: order.get(kv[0], len(order))))


def _first(rx: re.Pattern[str], text: str) -> re.Match[str] | None:
    return rx.search(text)


_MED_NAME = "(?:" + MEDICATION_NAME_PATTERN.replace(" ", r"[\s\-]+") + ")"
_MED_VERB = re.compile(r"\b(?:took|taking|take|taken|popped|swallowed|had|started|using|on)\s+", _I)
_MED_ITEM = re.compile(
    r"(?:(?:my|some|a|an|the|one|two|\d+)\s+)?(?:\d+(?:\.\d+)?\s?(?:mg|mcg|g|iu|ml)\s+)?(" + _MED_NAME + r")\b"
    r"(?:\s+(?:supplements?|tablets?|pills?|capsules?))?(?:\s+\d+(?:\.\d+)?\s?(?:mg|mcg|g|iu|ml))?", _I)
_MED_SEP = re.compile(r"\s*(?:,|&|\+|\band\b|\bplus\b)\s*(?:and\s+)?", _I)


def _med_chain(sentence: str) -> list[str]:
    """Names in 'took A, B and my C' chains. Only names from the shared list are ever returned."""
    out: list[str] = []
    for verb in list(_MED_VERB.finditer(sentence))[:6]:
        pos = verb.end()
        for _ in range(8):
            item = _MED_ITEM.match(sentence, pos)
            if not item:
                break
            out.append(item.group(1))
            pos = item.end()
            sep = _MED_SEP.match(sentence, pos)
            if not sep:
                break
            pos = sep.end()
    return out


def _file_med(name: str, meds: list[str], supps: list[str]) -> None:
    clean = re.sub(r"[\s\-]+", " ", name.strip().lower())
    clean = "omega-3" if clean in {"omega 3", "omega3"} else clean
    if clean in _SUPPLEMENTS or clean.startswith("vitamin") or clean.endswith(("vitamin", "vitamins")):
        supps.append(clean)
    else:
        meds.append(clean)


def parse_daily_log(text: str, facts: Iterable[Fact] = (), *, now: datetime | None = None) -> DailyLog:
    """Extract the explicitly stated metrics. `facts` supplies symptom/denial/period context."""
    t = normalize(text)
    now = now or datetime.now(timezone.utc)
    today = user_today(now)
    day = today
    if re.match(r"\s*(?:\[day \d+\]\s*)?(?:for )?yesterday\b", t, _I) or re.search(r"\byesterday'?s? (?:log|summary|day)\b", t, _I):
        day = day - timedelta(days=1)
    # A message that names one day ("on 20 September I slept 5 hours", "on the 20th") is logged on that day.
    day = stated_date(text, today) or day
    log = DailyLog(log_date=day.isoformat())
    mt, d = log.metrics, log.domains

    # ---- sleep
    minutes = None
    for rx in (_SLEEP_HM, _SLEEP_HM_REV):
        m = rx.search(t)
        if m:
            minutes = int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)
            break
    if minutes is None:
        m = _SLEEP_DEC.search(t)
        if m:
            minutes = round(_num(m.group(1) or m.group(2)) * 60)
    if minutes is not None and 30 <= minutes <= 18 * 60:
        mt["sleep_minutes"] = int(minutes)
        d.add("sleep")
    bed = _BEDTIME.search(t)
    if bed:
        clock = _clock(bed.group(1), bed.group(2), bed.group(3), "bed")
        if clock:
            mt["bedtime"] = clock
            d.add("sleep")
    wake = _WAKE.search(t)
    if wake:
        g = wake.groups()
        clock = _clock(g[0], g[1], g[2], "wake") if g[0] else None
        if clock is None and g[3]:
            h, _, mm = g[3].partition(":")
            clock = _clock(h, mm, g[4], "wake")
        if clock is None and g[5]:
            h, _, mm = g[5].partition(":")
            clock = _clock(h, mm, g[6], "wake")
        if clock:
            mt["wake_time"] = clock
            d.add("sleep")
    rng = _SLEEP_RANGE.search(t)
    if rng:
        a, b = rng.groups()[:3], rng.groups()[3:]
        # a bare "6 to 8" is not a clock range: each end needs a colon or am/pm
        if all(x[1] or x[2] for x in (a, b)):
            bed_c, wake_c = _clock(a[0], a[1], a[2], "bed"), _clock(b[0], b[1], b[2], "wake")
            if bed_c and wake_c:
                mt.setdefault("bedtime", bed_c)
                mt.setdefault("wake_time", wake_c)
                d.add("sleep")
                span = (int(wake_c[:2]) * 60 + int(wake_c[3:]) - int(bed_c[:2]) * 60 - int(bed_c[3:])) % 1440
                if "sleep_minutes" not in mt and 30 <= span <= 18 * 60:   # a stated duration always wins over a derived one
                    mt["sleep_minutes"] = span
                    log.estimates["sleep_minutes"] = "derived from the stated bed and wake times"
    aw = _AWAKE.search(t)
    if aw:
        word = (aw.group(2) or aw.group(3) or aw.group(4) or "").lower()
        n = int(aw.group(1)) if aw.group(1) else _COUNT_WORDS.get(word)
        if n is not None:
            mt["awakenings"] = n
            d.add("sleep")
    sq = _SLEEP_Q_NUM.search(t)
    if sq and 1 <= int(sq.group(1)) <= 10:
        mt["sleep_quality"] = int(sq.group(1))
        d.add("sleep")
    else:
        sw = _SLEEP_Q_WORD.search(t)
        if sw:
            mt["sleep_quality"] = _SLEEP_Q_MAP[sw.group(1).lower()]
            log.estimates["sleep_quality"] = "estimated from wording"
            d.add("sleep")

    # ---- cycle
    cd = _CYCLE_DAY.search(t)
    if cd:
        mt["cycle_day"] = int(cd.group(1) or cd.group(2))
        d.add("cycle")
    fm = _FLOW.search(t)
    if fm:
        flow = (fm.group(1) or fm.group(2)).lower()
        mt["flow"] = {"medium": "moderate", "very heavy": "heavy"}.get(flow, flow)
        d.add("cycle")
    period = [f for f in facts if f.concept == "period" and f.experiencer == "self"]
    if _PERIOD_END.search(t) or _PERIOD_INACTIVE.search(t):
        mt["period_active"] = False
        d.add("cycle")
    elif _PERIOD_START.search(t) or "cycle_day" in mt or "flow" in mt or any(f.assertion == "present" and f.temporal in {"current", "recent", "unknown"} for f in period):
        if not any(f.assertion == "negated" for f in period):
            mt["period_active"] = True
            d.add("cycle")
    elif any(f.assertion == "negated" for f in period):
        mt["period_active"] = False
        d.add("cycle")

    # ---- hydration
    spans: list[tuple[int, int]] = []
    total_ml, estimated = 0.0, False
    for rx in (_WATER_A, _WATER_B, _WATER_C):
        for m in rx.finditer(t):
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue
            spans.append((m.start(), m.end()))
            amount, unit = _num(m.group(1)), m.group(2).lower()
            if unit.startswith("l") and unit != "ml":
                total_ml += amount * 1000
            elif unit == "ml":
                total_ml += amount
            elif unit.startswith("glass") or unit.startswith("cup"):
                total_ml += amount * 250
                estimated = True
            elif unit.startswith("bottle"):
                total_ml += amount * 500
                estimated = True
    if 50 <= total_ml <= 12000:
        mt["water_ml"] = int(round(total_ml))
        d.add("hydration")
        if estimated:
            log.estimates["water_ml"] = "glasses/cups/bottles converted at 250/250/500 ml"
    cups = 0
    seen_caf: list[tuple[int, int]] = []
    for rx, grp in ((_CAFFEINE, 1), (_CAFFEINE_B, 2)):
        for m in rx.finditer(t):
            if any(m.start() < e and s < m.end() for s, e in seen_caf):
                continue
            seen_caf.append((m.start(), m.end()))
            n = m.group(grp).lower()
            cups += int(n) if n.isdigit() else _COUNT_WORDS.get(n, 1)
    if cups:
        mt["caffeine_cups"] = cups
        d.add("hydration")

    # ---- activity
    sm = _STEPS.search(t)
    if sm:
        steps = int(_num(sm.group(1) or sm.group(2)))
        if 0 < steps < 100000:
            mt["steps"] = steps
            d.add("activity")
    ex_total, ex_types, seen_ex = 0, [], set()
    for rx, order in ((_EX_HM_A, "hmk"), (_EX_HM_B, "khm"), (_EX_A, "mn"), (_EX_B, "nm"), (_EX_H, "hn")):
        for m in rx.finditer(t):
            key = (m.start(), m.end())
            if any(m.start() < e and s < m.end() for s, e in seen_ex):
                continue
            seen_ex.add(key)
            if order == "mn":
                mins, kind = int(m.group(1)), m.group(2)
            elif order == "nm":
                kind, mins = m.group(1), int(m.group(2))
            elif order == "hmk":
                mins, kind = round(float(m.group(1)) * 60) + int(m.group(2)), m.group(3)
            elif order == "khm":
                kind, mins = m.group(1), round(float(m.group(2)) * 60) + (int(m.group(3)) if m.group(3) else 0)
            else:
                mins, kind = round(float(m.group(1)) * 60), m.group(2)
            if 0 < mins <= 600:
                ex_total += mins
                ex_types.append(kind.lower())
    if ex_total:
        mt["exercise_minutes"] = ex_total
        mt["exercise_types"] = list(dict.fromkeys(ex_types))
        d.add("activity")

    # ---- body / vitals
    wm = _WEIGHT.search(t)
    if wm:
        w = float(wm.group(1))
        kg = round(w * 0.45359237, 1) if wm.group(2).lower().startswith(("lb", "pound")) else round(w, 1)
        if 20 <= kg <= 400:
            mt["weight_kg"] = kg
            d.add("body")
    hm = _HR.search(t)
    if hm and 30 <= int(hm.group(1)) <= 220:
        mt["heart_rate_bpm"] = int(hm.group(1))
        d.add("vitals")
    bp = _BP.search(t)
    if bp and 60 <= int(bp.group(1)) <= 260 and 30 <= int(bp.group(2)) <= 160:
        mt["systolic_bp"], mt["diastolic_bp"] = int(bp.group(1)), int(bp.group(2))
        d.add("vitals")
    tm = _TEMP.search(t)
    if tm:
        value, unit = float(tm.group(1)), (tm.group(2) or "").lower()
        celsius = round((value - 32) / 1.8, 1) if unit == "f" or (not unit and value > 45) else value
        if 30 <= celsius <= 43:
            mt["temperature_c"] = celsius
            d.add("vitals")
    sp = _SPO2.search(t)
    if sp and 70 <= int(sp.group(1)) <= 100:
        mt["spo2_percent"] = int(sp.group(1))
        d.add("vitals")

    # ---- mood / energy / stress
    mm = _MOOD_A.search(t) or _MOOD_B.search(t)
    if mm:
        mt["mood"] = mm.group(1).lower()
        d.add("mood")
    mn = _MOOD_NUM.search(t)
    if mn and 0 <= int(mn.group(1)) <= 10:
        mt["mood_score"] = int(mn.group(1))
        d.add("mood")
    en = _ENERGY_NUM.search(t)
    if en and 0 <= int(en.group(1)) <= 10:
        mt["energy_score"] = int(en.group(1))
        d.add("mood")
    ew = _ENERGY_A.search(t) or _ENERGY_B.search(t)
    if ew:
        word = ew.group(1).lower()
        mt["energy"] = {"lower": "low", "higher": "high", "reduced": "low", "ok": "okay", "drained": "low"}.get(word, word)
        d.add("mood")
    sn = _STRESS_NUM.search(t)
    if sn and 0 <= int(sn.group(1)) <= 10:
        mt["stress_score"] = int(sn.group(1))
        d.add("mood")
    else:
        sw = _STRESS_WORD.search(t)
        if sw:
            mt["stress"] = {"medium": "moderate"}.get(sw.group(1).lower(), sw.group(1).lower())
            d.add("mood")
    an = _ANXIETY_NUM.search(t)
    if an and 0 <= int(an.group(1)) <= 10:
        mt["anxiety_score"] = int(an.group(1))
        d.add("mood")
    fo = _FOCUS.search(t)
    if fo:
        mt["focus"] = fo.group(1).lower()
        d.add("mood")

    # ---- nutrition
    log.meals = _meals(t, log.meal_phrases)
    if log.meals:
        d.add("nutrition")
        foods = [f for items in log.meals.values() for f in items]
        mt["meals"] = list(dict.fromkeys(foods))
        est = _estimate_nutrition(foods, log.meal_phrases)
        if est:
            log.estimates["nutrition"] = est
    cm = _CALORIES.search(t)
    if cm:
        mt["calories"] = int(cm.group(1))
        d.add("nutrition")
    pm = _PROTEIN.search(t)
    if pm:
        mt["protein_g"] = int(pm.group(1) or pm.group(2))
        d.add("nutrition")

    # ---- medication / supplements (from facts: explicit denials stay explicit)
    meds: list[str] = []
    supps: list[str] = []
    denied_meds = False
    facts = list(facts)
    taken_sentences: set[int] = set()
    for f in facts:
        if f.concept != "medication_use" or f.experiencer != "self":
            continue
        if f.assertion == "negated":
            denied_meds = True
        elif f.assertion == "present" and f.detail:
            taken_sentences.add(f.sentence_index)
            _file_med(f.detail, meds, supps)
    # "Took iron and vitamin C", "Took ibuprofen 400 mg and my levothyroxine": the verb governs a whole chain of names, but only
    # in a sentence where the semantics already confirmed that the user took something (not "Should I take iron and ...?")
    if taken_sentences:
        for i, sentence in enumerate(split_sentences(t)):
            if i in taken_sentences:
                for name in _med_chain(sentence):
                    _file_med(name, meds, supps)
    if supps:
        mt["supplements"] = list(dict.fromkeys(supps))
        d.add("medication")
    if meds:
        mt["medications"] = list(dict.fromkeys(meds))
        d.add("medication")
    if denied_meds and not meds and not supps:
        mt["medications"] = []
        d.add("medication")

    # ---- symptoms count as a domain when severity or a denial list is given
    if any(f.experiencer == "self" and f.assertion in {"present", "negated"} and f.concept not in {"period", "medication_use"} for f in facts):
        d.add("symptoms")
    return log


def _estimate_nutrition(foods: list[str], phrases: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
    """Reference estimates only for foods Bubbles actually knows; unknown foods stay unestimated.

    With the user's own words (``phrases``) quantities and household units count ("2 rotis" is two rotis); without them
    each known food counts as one reference serving.
    """
    if phrases:
        try:
            from meal_composer import compose
            parsed = compose(", ".join(p for ps in phrases.values() for p in ps))
            if parsed["items"]:
                t = parsed["totals"]
                return {"calories": t["kcal"], "calories_low": t["kcal_low"], "calories_high": t["kcal_high"], "protein_g": t["protein_g"],
                        "from": [i["food"] for i in parsed["items"]], "not_estimated": parsed["unrecognised"],
                        "basis": "Bubbles reference estimate with the portions you said; not a measurement"}
        except Exception:  # noqa: BLE001
            pass
    try:
        from indian_food_intelligence import lookup_food
    except Exception:  # noqa: BLE001
        return None
    cal = pro = 0.0
    known, unknown = [], []
    for f in foods:
        item = lookup_food(f) or lookup_food(f.rstrip("s"))
        if item:
            cal += item["calories"]
            pro += item["protein_g"]
            known.append(item["name"])
        else:
            unknown.append(f)
    if not known:
        return None
    return {"calories": round(cal), "protein_g": round(pro, 1), "from": known, "not_estimated": unknown,
            "basis": "Bubbles reference estimate, typical single servings; not a measurement"}


# --------------------------------------------------------------------------
# Natural-language summary of what was logged (deterministic; no model call)
# --------------------------------------------------------------------------

def _duration(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if m else f"{h}h"


def _sev_word(f: Fact) -> str:
    if f.severity is not None:
        return f"{f.severity}/10"
    return f.severity_label or ""


def _list(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def summarize_log(log: DailyLog, facts: Iterable[Fact], *, name: str | None = None) -> str:
    facts = [f for f in facts if f.experiencer == "self"]
    mt = log.metrics
    opener = f"Got it, {name}." if name else "Got it."
    try:
        day_word = day_phrase(log.log_date, user_today())
        day_word = day_word if day_word == "today" else "for " + day_word.removeprefix("on ")   # "I've logged for 20 September"
    except ValueError:
        day_word = f"for {log.log_date}"
    bits: list[str] = []

    cycle = []
    if mt.get("period_active") and "cycle_day" in mt:
        cycle.append(f"cycle day {mt['cycle_day']}")
    elif mt.get("period_active"):
        cycle.append("an active period")
    elif "cycle_day" in mt:
        cycle.append(f"cycle day {mt['cycle_day']}" + (" (period not active)" if mt.get("period_active") is False else ""))
    if mt.get("flow") and cycle:
        cycle = [f"{cycle[0]} with {mt['flow']} flow"]       # "cycle day 3 with moderate flow", never "...and moderate flow"
    elif mt.get("flow"):
        cycle.append(f"{mt['flow']} flow")
    positives = [f for f in facts if f.assertion == "present" and f.concept not in {"period", "medication_use"} and f.temporal in {"current", "recent", "recurring", "unknown"}]
    sym = []
    seen = set()
    for f in positives:
        if f.concept in seen:
            continue
        seen.add(f.concept)
        sev = _sev_word(f)
        label = display_name(f.concept)
        sym.append(f"{label} ({sev})" if sev else label)
    head = f"I've logged {day_word}"
    if cycle:
        head += " as " + _list(cycle)
    if sym:
        head += (", along with " if cycle else " with ") + _list(sym)
    bits.append(head + ".")

    body = []
    if "sleep_minutes" in mt:
        extra = []
        if mt.get("bedtime") and mt.get("wake_time"):
            extra.append(f"{mt['bedtime']}–{mt['wake_time']}")
        body.append(f"you slept {_duration(mt['sleep_minutes'])}" + (f" ({', '.join(extra)})" if extra else ""))
    if "water_ml" in mt:
        approx = "about " if "water_ml" in log.estimates else ""
        body.append(f"drank {approx}{mt['water_ml'] / 1000:.1f} L of water")
    if "steps" in mt:
        body.append(f"walked {mt['steps']:,} steps")
    if "exercise_minutes" in mt:
        body.append(f"exercised for {mt['exercise_minutes']} minutes")
    if log.meals:
        body.append("ate " + _list([_list(v) if k == "meals" else f"{_list(v)} for {k}" for k, v in log.meals.items()]))
    if "weight_kg" in mt:
        body.append(f"weighed {mt['weight_kg']} kg")
    vit = []
    if "heart_rate_bpm" in mt:
        vit.append(f"heart rate {mt['heart_rate_bpm']} bpm")
    if "systolic_bp" in mt:
        vit.append(f"blood pressure {mt['systolic_bp']}/{mt['diastolic_bp']}")
    if "temperature_c" in mt:
        vit.append(f"temperature {mt['temperature_c']} °C")
    if vit:
        body.append("recorded " + _list(vit))
    if mt.get("supplements"):
        body.append("took " + _list(mt["supplements"]))
    if mt.get("medications"):
        body.append("took " + _list(mt["medications"]))
    mood = []
    if mt.get("mood"):
        mood.append(f"a {mt['mood']} mood")
    if mt.get("energy"):
        mood.append(f"{mt['energy']} energy")
    if mt.get("stress") or "stress_score" in mt:
        mood.append(f"stress {mt.get('stress') or str(mt['stress_score']) + '/10'}")
    if mood:
        body.append("reported " + _list(mood))
    if body:
        bits.append("You " + _list([b.replace("you ", "", 1) if b.startswith("you ") else b for b in body]) + ".")

    denied = list(dict.fromkeys(display_name(f.concept) for f in facts if f.assertion == "negated" and f.concept not in {"medication_use", "period"}))
    if denied:
        bits.append("You also told me you have no " + _list(denied) + ", so I've noted those as not present.")
    if mt.get("medications") == [] and not mt.get("supplements"):
        bits.append("I've noted that you took no medication.")
    return " ".join([opener] + bits)
