"""Deterministic menstrual-cycle engine: personal averages, predictions with ranges, phases, BBT / LH tightening, modes.

Pure functions over plain data (dates, dicts); no I/O, no randomness, no clock (callers pass ``today``). Every clinical
number comes from ``clinical_constants`` (status: PENDING CLINICIAN REVIEW). Bubbles never diagnoses: this module returns
ESTIMATES with ranges and a confidence label, and nothing here is contraception.

Vocabulary
* ``logs``  -> ``{date: day_log_dict}`` (see cycle_api.normalize_day_log for the shape).
* a "cycle" is the span from one period start to the next; only gaps inside ``CYCLE_PLAUSIBLE_DAYS`` count as cycle lengths
  (a bigger gap is far more likely to be a period nobody logged than a 100-day cycle).
* confidence: "learning" (< CYCLE_MIN_CYCLES_FOR_PREDICTION cycles) | "low" (irregular, postpartum, perimenopause) |
  "medium" | "high".
"""
from __future__ import annotations

import math
from bisect import bisect_right
from datetime import date, datetime, timedelta
from statistics import mean, stdev
from typing import Any, Iterable, Mapping

import clinical_constants as K
from cycle_content import CHIP_BY_ID

MODES = ("track", "birth_control", "conceive", "pregnancy", "postpartum", "perimenopause")
PHASES = ("menstrual", "follicular", "ovulatory", "luteal")
BLEEDING = frozenset({"light", "medium", "heavy"})   # flow levels that count as period days (spotting does not)
FERTILITY_HIDDEN_MODES = frozenset({"birth_control", "pregnancy", "postpartum"})
LOW_CONFIDENCE_MODES = frozenset({"postpartum", "perimenopause"})
Logs = Mapping[date, Mapping[str, Any]]


# --------------------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------------------

def parse_day(value: Any) -> date | None:
    """A calendar day from a date / datetime / ISO string, else None (never raises)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _days(n: int | float) -> timedelta:
    return timedelta(days=int(n))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def chip_signal(chip_id: str) -> str | None:
    chip = CHIP_BY_ID.get(chip_id)
    return chip["signal"] if chip else None


def _disturbs_bbt(log: Mapping[str, Any]) -> bool:
    return any((CHIP_BY_ID.get(f) or {}).get("disturbs_bbt") for f in log.get("factors") or ())


# --------------------------------------------------------------------------------------------------
# period starts / ends / cycles
# --------------------------------------------------------------------------------------------------

def merge_starts(starts: Iterable[date]) -> list[date]:
    """Sorted unique starts; a start within PERIOD_MERGE_WITHIN_DAYS of the previous one is the same period."""
    kept: list[date] = []
    for start in sorted(set(starts)):
        if kept and (start - kept[-1]).days <= K.PERIOD_MERGE_WITHIN_DAYS:
            continue
        kept.append(start)
    return kept


def bleeding_runs(logs: Logs) -> list[tuple[date, date]]:
    """Runs of bleeding days (light/medium/heavy flow, or a marked period start); one missing log day does not split a run."""
    days = sorted(d for d, log in logs.items() if log.get("flow") in BLEEDING or log.get("period_start"))
    runs: list[tuple[date, date]] = []
    for day in days:
        if runs and (day - runs[-1][1]).days <= 2:
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))
    return runs


def derive_markers(logs: Logs, extra_starts: Iterable[date] = (), extra_ends: Iterable[date] = ()):
    """(starts, ends, runs): starts from explicit taps, the first day of each bleeding run and ``extra_starts``."""
    explicit = [d for d, log in logs.items() if log.get("period_start")]
    runs = bleeding_runs(logs)
    starts = merge_starts([*explicit, *extra_starts, *(r[0] for r in runs)])
    ends = sorted({*(d for d, log in logs.items() if log.get("period_end")), *extra_ends})
    return starts, ends, runs


def build_cycles(starts: list[date], ends: list[date], runs: list[tuple[date, date]]) -> list[dict]:
    lo, hi = K.CYCLE_PLAUSIBLE_DAYS
    cycles = []
    for i, start in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else None
        gap = (nxt - start).days if nxt else None
        cap = start + _days(K.PERIOD_MAX_PLAUSIBLE_DAYS - 1)
        if nxt:
            cap = min(cap, nxt - _days(1))
        end = next((e for e in ends if start <= e <= cap), None)
        if end is None:
            run = next((r for r in runs if r[0] <= start <= r[1]), None)
            # a single logged bleeding day says nothing about period length, so only runs of 2+ days count
            end = min(run[1], cap) if run and run[1] > run[0] else None
        cycles.append({"start": start, "next_start": nxt, "gap": gap,
                       "length": gap if gap is not None and lo <= gap <= hi else None,
                       "end": end, "period_days": (end - start).days + 1 if end else None})
    return cycles


def length_stats(lengths: list[int]) -> dict:
    """Weighted mean (newest cycle weighs 1, the one before 0.8, ...), plain SD, range. ``lengths`` is oldest -> newest."""
    n = len(lengths)
    if not n:
        return {"n": 0, "weighted_mean": None, "mean": None, "sd": None, "min": None, "max": None}
    weights = [K.CYCLE_HISTORY_WEIGHT_DECAY ** (n - 1 - i) for i in range(n)]
    return {"n": n, "weighted_mean": sum(w * x for w, x in zip(weights, lengths)) / sum(weights), "mean": mean(lengths),
            "sd": round(stdev(lengths), 2) if n >= 2 else None, "min": min(lengths), "max": max(lengths)}


def regularity(sd: float | None, n: int) -> dict | None:
    """0-100 (100 = identical cycle lengths; 50 at the irregular threshold). None until 3 cycles."""
    if sd is None or n < K.CYCLE_MIN_CYCLES_FOR_PREDICTION:
        return None
    score = round(_clamp(100 * (1 - sd / (2 * K.IRREGULAR_SD_DAYS)), 0, 100))
    label = "Very regular" if score >= 80 else "Fairly regular" if score >= 60 else "Somewhat variable" if score >= 40 else "Irregular"
    return {"score": score, "label": label}


def confidence_for(n: int, sd: float | None, mode: str) -> tuple[str, str]:
    """(label, plain-language note)."""
    if n < K.CYCLE_MIN_CYCLES_FOR_PREDICTION:
        return "learning", (f"Bubbles has seen {n} full cycle{'s' if n != 1 else ''} so far and needs {K.CYCLE_MIN_CYCLES_FOR_PREDICTION} "
                            "to learn your rhythm, so these ranges are wide.")
    if mode == "postpartum":
        return "low", "Cycles often take a while to settle after a birth, so predictions are low-confidence for now."
    if mode == "perimenopause":
        return "low", "Cycles commonly change during perimenopause, so predictions are low-confidence and the ranges are wide."
    if sd is not None and sd > K.IRREGULAR_SD_DAYS:
        return "low", f"Your cycle lengths vary by about {sd:.0f} days, so Bubbles shows wider ranges and treats predictions as low-confidence."
    if n >= K.CYCLE_HIGH_CONFIDENCE[0] and sd is not None and sd <= K.CYCLE_HIGH_CONFIDENCE[1]:
        return "high", f"Your last {n} cycles were very consistent, so the ranges are narrow. They are still estimates."
    return "medium", f"Based on your last {n} cycles. These are estimates and can be off by a few days."


# --------------------------------------------------------------------------------------------------
# BBT (3-over-6) and LH tests
# --------------------------------------------------------------------------------------------------

def detect_bbt_shift(temps: Mapping[date, float]) -> dict | None:
    """Coverline detection: 3 consecutive readings each above the highest of the previous 6 and at least
    BBT_SHIFT_RISE_C above their mean. Readings must be reasonably close together (<= 3 missing days across the 9)."""
    readings = sorted(temps.items())
    need = K.BBT_BASELINE_DAYS + K.BBT_SHIFT_DAYS
    for i in range(K.BBT_BASELINE_DAYS, len(readings) - K.BBT_SHIFT_DAYS + 1):
        base = readings[i - K.BBT_BASELINE_DAYS:i]
        high = readings[i:i + K.BBT_SHIFT_DAYS]
        if (high[-1][0] - base[0][0]).days + 1 > need + 3:
            continue
        base_t = [t for _d, t in base]
        cover, base_mean = max(base_t), mean(base_t)
        if all(t > cover and t >= base_mean + K.BBT_SHIFT_RISE_C for _d, t in high):
            first_high = high[0][0]
            return {"first_high_day": first_high, "ovulation_day": first_high - _days(1), "coverline": round(cover, 2),
                    "rise_c": round(mean(t for _d, t in high) - base_mean, 2)}
    return None


def _bbt_in(logs: Logs, lo: date, hi: date) -> dict[date, float]:
    out = {}
    for d, log in logs.items():
        t = log.get("bbt_c")
        if lo <= d <= hi and isinstance(t, (int, float)) and not _disturbs_bbt(log):
            out[d] = float(t)
    return out


def lh_ovulation(logs: Logs, lo: date, hi: date) -> dict | None:
    """Ovulation tightened by a positive/peak ovulation test: usually ~1 day after the first positive of the latest surge."""
    positives = sorted(d for d, log in logs.items() if lo <= d <= hi and log.get("ovulation_test") in ("positive", "peak"))
    if not positives:
        return None
    first = positives[-1]
    for d in reversed(positives):
        if (first - d).days <= 3:
            first = d
    a, b = K.LH_OVULATION_AFTER_POSITIVE_DAYS
    return {"first_positive": first, "ovulation_day": first + _days(1), "earliest": first + _days(a), "latest": first + _days(b)}


# --------------------------------------------------------------------------------------------------
# life-stage info
# --------------------------------------------------------------------------------------------------

def pregnancy_info(today: date, lmp: date | None, due: date | None) -> dict | None:
    """Completed weeks + days from the last period (a "12 + 3" reading), trimester and days to go."""
    if lmp is None and due is not None:
        lmp = due - _days(K.PREGNANCY_DAYS)
    if lmp is None or lmp > today:
        return None
    due = due or lmp + _days(K.PREGNANCY_DAYS)
    elapsed = (today - lmp).days
    week = int(_clamp(elapsed // 7, 1, 42))
    return {"lmp": lmp, "week": week, "day": elapsed % 7, "trimester": 1 if elapsed // 7 < 13 else 2 if elapsed // 7 < 28 else 3,
            "due_date": due, "days_to_go": (due - today).days}


def postpartum_info(today: date, delivery: date | None) -> dict | None:
    if delivery is None or delivery > today:
        return None
    since = (today - delivery).days
    return {"delivery_date": delivery, "days_since": since, "weeks_since": since // 7, "lochia_expected": since < K.POSTPARTUM_LOCHIA_DAYS}


# --------------------------------------------------------------------------------------------------
# phase maths
# --------------------------------------------------------------------------------------------------

def phase_for_day(cycle_day: int, cycle_length: int, period_days: int, luteal: int, ovulation_day: int | None = None) -> str:
    """menstrual -> follicular -> ovulatory (the day before to the day after the estimated ovulation) -> luteal."""
    ov = ovulation_day if ovulation_day is not None else max(period_days + 2, cycle_length + 1 - luteal)
    if cycle_day <= period_days:
        return "menstrual"
    if cycle_day < ov - 1:
        return "follicular"
    if cycle_day <= ov + 1:
        return "ovulatory"
    return "luteal"


# --------------------------------------------------------------------------------------------------
# the one entry point
# --------------------------------------------------------------------------------------------------

def analyse(logs: Logs | None = None, *, today: date, extra_starts: Iterable[date] = (), extra_ends: Iterable[date] = (),
            mode: str = "track", luteal_days: int | None = None, delivery_date: date | None = None,
            lmp: date | None = None, due_date: date | None = None) -> dict:
    """Everything the overview, calendar, flags, insights and report need. Dates are ``datetime.date`` objects."""
    logs = {d: l for d, l in (logs or {}).items() if isinstance(d, date)}
    mode = mode if mode in MODES else "track"
    raw_starts, ends, runs = derive_markers(logs, extra_starts, extra_ends)
    all_starts = [s for s in raw_starts if s <= today]
    starts = list(all_starts)
    if mode == "postpartum" and delivery_date:   # bleeding in the first weeks after birth is lochia, not a period
        starts = [s for s in starts if s >= delivery_date + _days(K.POSTPARTUM_LOCHIA_DAYS)]
    cycles = build_cycles(starts, ends, runs)
    lengths = [c["length"] for c in cycles if c["length"] is not None][-K.CYCLE_HISTORY_MAX_CYCLES:]
    stats = length_stats(lengths)
    n, sd = stats["n"], stats["sd"]
    confidence, confidence_note = confidence_for(n, sd, mode)
    irregular = n >= K.CYCLE_MIN_CYCLES_FOR_PREDICTION and sd is not None and sd > K.IRREGULAR_SD_DAYS
    periods = [c["period_days"] for c in cycles if c["period_days"]][-6:]
    period_avg = round(mean(periods), 1) if periods else None

    confirmed, personal_luteal = _confirmed_ovulations(cycles, logs, today)
    luteal_range = K.LUTEAL_RANGE_DAYS
    luteal = (int(_clamp(luteal_days, *luteal_range)) if luteal_days else
              round(_clamp(mean(personal_luteal), *luteal_range)) if len(personal_luteal) >= 2 else K.LUTEAL_LENGTH_DAYS)

    predicted_len = round(stats["weighted_mean"]) if n else K.CYCLE_DEFAULT_LENGTH_DAYS
    lo_h, hi_h = K.CYCLE_WINDOW_HALF_DAYS
    half = (K.CYCLE_LEARNING_HALF_WINDOW_DAYS if n < K.CYCLE_MIN_CYCLES_FOR_PREDICTION
            else int(_clamp(math.ceil(K.CYCLE_WINDOW_SD_MULTIPLIER * (sd or 0)), lo_h, hi_h)))
    if mode in LOW_CONFIDENCE_MODES:
        half = int(min(hi_h, half * 2))

    last = starts[-1] if starts else None
    state: dict[str, Any] = {
        "today": today, "mode": mode, "starts": starts, "all_starts": all_starts, "ends": ends, "runs": runs, "cycles": cycles,
        "lengths": lengths, "length_stats": stats, "period_length_average": period_avg, "irregular": irregular,
        "regularity": regularity(sd, n), "confidence": confidence, "confidence_note": confidence_note,
        "predicted_length": predicted_len, "half_window": half, "luteal": luteal, "confirmed_ovulations": confirmed,
        "last_start": last, "days_since_last_start": (today - last).days if last else None,
        "cycle_day": None, "stale": False, "next_period": None, "ovulation": None, "fertile_window": None,
        "fertility_note": None, "phase": None, "pregnancy": None, "postpartum": None, "pms": None,
    }
    state["pregnancy"] = pregnancy_info(today, lmp, due_date) if mode == "pregnancy" else None
    state["postpartum"] = postpartum_info(today, delivery_date) if mode == "postpartum" else None
    if last is not None:
        day = (today - last).days + 1
        state["stale"] = day > K.CYCLE_PLAUSIBLE_DAYS[1]
        state["cycle_day"] = None if state["stale"] else day
    if last is not None and mode != "pregnancy":
        _forecast(state, logs, last, today)
    if mode in FERTILITY_HIDDEN_MODES:
        state["ovulation"] = state["fertile_window"] = None
        state["fertility_note"] = {
            "birth_control": "Hormonal birth control changes ovulation and bleeding, so Bubbles does not estimate ovulation or a fertile window in this mode.",
            "postpartum": "Ovulation can return before the first period after a birth, and it cannot be predicted well, so Bubbles does not show a fertile window in this mode.",
            "pregnancy": "Fertility estimates are paused during pregnancy.",
        }[mode]
    state["_index"] = _cycle_index(state)
    cd, phase = locate(state, today)
    state["phase"] = phase if not state["stale"] else None
    state["pms"] = pms_hint(state, logs)
    return state


def _confirmed_ovulations(cycles: list[dict], logs: Logs, today: date) -> tuple[dict[date, date], list[int]]:
    """{cycle_start: ovulation day from a BBT shift} for cycles with enough temperatures, and the luteal lengths they imply."""
    confirmed: dict[date, date] = {}
    luteal: list[int] = []
    for c in cycles:
        end = (c["next_start"] - _days(1)) if c["next_start"] else today
        shift = detect_bbt_shift(_bbt_in(logs, c["start"], end))
        if shift:
            confirmed[c["start"]] = shift["ovulation_day"]
            if c["next_start"] and c["length"]:
                luteal.append((c["next_start"] - shift["ovulation_day"]).days)
    return confirmed, luteal


def _window(point: date, half: int) -> dict:
    return {"date": point, "earliest": point - _days(half), "latest": point + _days(half)}


def _forecast(state: dict, logs: Logs, last: date, today: date) -> None:
    half, luteal, mode = state["half_window"], state["luteal"], state["mode"]
    point = last + _days(state["predicted_length"])
    ov_range = (point - _days(luteal + half + 1), point - _days(luteal) + _days(half + 1))
    ov = {"date": point - _days(luteal), "source": "calendar", "confirmed": False}
    next_half = half

    shift = detect_bbt_shift(_bbt_in(logs, last, today))
    lh = None if shift else lh_ovulation(logs, last, today)
    if shift:
        ov = {"date": shift["ovulation_day"], "source": "bbt", "confirmed": True}
        ov_range = (shift["ovulation_day"] - _days(1), shift["ovulation_day"])
        point, next_half = ov["date"] + _days(luteal), max(1, min(half, 2))
    elif lh:
        ov = {"date": lh["ovulation_day"], "source": "lh_test", "confirmed": False}
        ov_range = (lh["earliest"], lh["latest"])
        point, next_half = ov["date"] + _days(luteal), max(1, min(half, 3))

    window = _window(point, next_half)
    in_days = (point - today).days
    status = "late" if today > window["latest"] else "due" if today >= window["earliest"] else "upcoming"
    state["next_period"] = {**window, "in_days": in_days, "status": status, "late_by_days": (today - point).days if status == "late" else None}
    state["ovulation"] = {"date": ov["date"], "earliest": ov_range[0], "latest": ov_range[1], "confirmed": ov["confirmed"],
                          "source": ov["source"], "passed": ov_range[1] < today}
    before = K.FERTILE_WINDOW_DAYS_BEFORE_OVULATION
    fw_earliest, fw_latest = ov_range[0] - _days(before), ov_range[1]
    state["fertile_window"] = {"start": ov["date"] - _days(before), "end": ov["date"], "earliest": fw_earliest, "latest": fw_latest,
                               "active_today": fw_earliest <= today <= fw_latest, "passed": fw_latest < today}
    if mode == "perimenopause":
        state["fertility_note"] = "Cycles change in perimenopause and pregnancy is still possible, so treat these ranges as rough."
    elif mode == "conceive":
        state["fertility_note"] = "Your most fertile days are the fertile window and especially the day or two before ovulation."


# --------------------------------------------------------------------------------------------------
# where is a date in the cycle
# --------------------------------------------------------------------------------------------------

def _cycle_index(state: dict) -> list[dict]:
    """Per cycle: length used for phase maths, period length and ovulation day (confirmed when known)."""
    out = []
    default_period = int(round(state["period_length_average"])) if state["period_length_average"] else K.PERIOD_DEFAULT_LENGTH_DAYS
    for c in state["cycles"]:
        complete = c["length"] is not None
        length = c["length"] if complete else state["predicted_length"]
        period = int(_clamp(c["period_days"] or default_period, 1, K.PERIOD_MAX_PLAUSIBLE_DAYS))
        conf = state["confirmed_ovulations"].get(c["start"])
        ov_day = (conf - c["start"]).days + 1 if conf else None
        out.append({"start": c["start"], "next_start": c["next_start"], "length": length, "period": period, "ov_day": ov_day,
                    "complete": complete})
    return out


def locate(state: dict, day: date) -> tuple[int | None, str | None]:
    """(cycle day, phase id) for any date: actual cycles in the past, the current cycle, and projected cycles ahead."""
    index = state["_index"] if "_index" in state else _cycle_index(state)
    if not index or day < index[0]["start"]:
        return None, None
    starts = [c["start"] for c in index]
    c = index[bisect_right(starts, day) - 1]
    offset = (day - c["start"]).days
    length, luteal, today = c["length"], state["luteal"], state["today"]
    is_last = c["next_start"] is None
    if is_last and state["next_period"] and day > today and day >= state["next_period"]["date"]:
        # beyond the predicted next period: roll forward on the predicted cycle length
        projected_start = state["next_period"]["date"]
        offset = (day - projected_start).days % max(1, state["predicted_length"])
        c = {**c, "ov_day": None}
    if offset + 1 > K.CYCLE_PLAUSIBLE_DAYS[1] and not c["complete"] and not (is_last and day > today):
        return None, None
    cycle_day = offset + 1
    return cycle_day, phase_for_day(cycle_day, length, c["period"], luteal, c["ov_day"])


# --------------------------------------------------------------------------------------------------
# PMS-window hint
# --------------------------------------------------------------------------------------------------

def _symptomatic(log: Mapping[str, Any]) -> bool:
    return (any(chip_signal(f) in ("symptom", "mood_negative") for f in log.get("factors") or ())
            or (log.get("pain_level") or 0) >= 3)


def pms_hint(state: dict, logs: Logs) -> dict | None:
    """"Around day X-Y based on your last N cycles" from the days before past periods on which you logged symptoms."""
    nxt = state.get("next_period")
    if not nxt or state["mode"] in ("pregnancy", "birth_control"):
        return None
    cycles = [c for c in state["cycles"] if c["length"] is not None][-6:]
    per_k: dict[int, int] = {}
    used = 0
    for c in cycles:
        hits = {(c["next_start"] - d).days for d, log in logs.items()
                if c["start"] <= d < c["next_start"] and 1 <= (c["next_start"] - d).days <= 14 and _symptomatic(log)}
        if hits:
            used += 1
            for k in hits:
                per_k[k] = per_k.get(k, 0) + 1
    if used >= K.INSIGHT_MIN_CYCLES:
        need = math.ceil(used / 2)
        ks = [k for k, count in per_k.items() if count >= need]
        if ks:
            kmax, kmin = max(ks), min(ks)
            length = state["predicted_length"]
            return {"from": nxt["date"] - _days(kmax), "to": nxt["date"] - _days(kmin), "personal": True, "cycles_used": used,
                    "text": f"Around day {length - kmax + 1}-{length - kmin + 1} of your cycle (the days before your period), based on your last {used} cycles."}
    return {"from": nxt["date"] - _days(5), "to": nxt["date"] - _days(1), "personal": False, "cycles_used": used,
            "text": "Many people notice changes in the days before a period. Log how you feel and Bubbles will learn your own window."}


# --------------------------------------------------------------------------------------------------
# "inner weather"
# --------------------------------------------------------------------------------------------------

def weather_tone(phase: str | None, log: Mapping[str, Any] | None, pms_today: bool) -> str:
    """bright | steady | heavier: today's own log when there is one, otherwise a gentle phase-based default."""
    if log:
        negatives = sum(1 for f in log.get("factors") or () if chip_signal(f) in ("symptom", "mood_negative"))
        positives = sum(1 for f in log.get("factors") or () if chip_signal(f) in ("mood_positive", "positive"))
        heavy = (log.get("flow") == "heavy" or log.get("soaking_hourly") or (log.get("pain_level") or 0) >= 6
                 or (log.get("energy") or 5) <= 2 or negatives >= 3)
        if heavy:
            return "heavier"
        if ((log.get("energy") or 0) >= 4 or positives >= 2) and (log.get("pain_level") or 0) < 4 and negatives < 2:
            return "bright"
        return "steady"
    if phase in ("follicular", "ovulatory"):
        return "bright"
    return "heavier" if pms_today else "steady"


# --------------------------------------------------------------------------------------------------
# calendar
# --------------------------------------------------------------------------------------------------

def calendar_days(state: dict, logs: Logs, start: date, end: date) -> list[dict]:
    """One marker row per day in [start, end]. Predictions run at most 3 cycles ahead and widen with distance."""
    today, mode = state["today"], state["mode"]
    show_period_pred = mode != "pregnancy" and state["last_start"] is not None
    show_fertile = show_period_pred and mode not in FERTILITY_HIDDEN_MODES
    period_len = int(round(state["period_length_average"])) if state["period_length_average"] else K.PERIOD_DEFAULT_LENGTH_DAYS
    logged_period: set[date] = set()
    for c in state["cycles"]:
        if c["period_days"]:
            logged_period.update(c["start"] + _days(i) for i in range(c["period_days"]))
    logged_period.update(d for d, log in logs.items() if log.get("flow") in BLEEDING or log.get("period_start"))

    predicted: set[date] = set()
    possible: set[date] = set()
    fertile_pred: set[date] = set()
    fertile_poss: set[date] = set()
    ov_pred: set[date] = set()
    if show_period_pred and state["next_period"]:
        nxt, length, half, luteal = state["next_period"], state["predicted_length"], state["half_window"], state["luteal"]
        before = K.FERTILE_WINDOW_DAYS_BEFORE_OVULATION
        for k in range(3):
            point = nxt["date"] + _days(k * length)
            h = int(min(K.CYCLE_WINDOW_HALF_DAYS[1], math.ceil(max(half, nxt["latest"].toordinal() - nxt["date"].toordinal()) * math.sqrt(k + 1))))
            for i in range(period_len):
                predicted.add(point + _days(i))
            for i in range(-h, period_len + h):
                possible.add(point + _days(i))
            if show_fertile:
                if k == 0 and state["ovulation"]:
                    ov, o_lo, o_hi = state["ovulation"]["date"], state["ovulation"]["earliest"], state["ovulation"]["latest"]
                else:
                    ov = point - _days(luteal)
                    o_lo, o_hi = ov - _days(h + 1), ov + _days(h + 1)
                ov_pred.add(ov)
                fertile_pred.update(ov - _days(i) for i in range(before + 1))
                fertile_poss.update(o_lo - _days(before) + _days(i) for i in range((o_hi - o_lo).days + before + 1))
    confirmed = set(state["confirmed_ovulations"].values())

    rows = []
    day = start
    while day <= end:
        log = logs.get(day) or {}
        cycle_day, phase = locate(state, day)
        if day in logged_period:
            period = "logged"
        elif day >= today and day in predicted:
            period = "predicted"
        elif day >= today and day in possible:
            period = "possible"
        else:
            period = None
        future_or_now = day >= today
        fertile = ("predicted" if day in fertile_pred else "possible" if day in fertile_poss else None) if show_fertile and future_or_now else None
        ovulation = "confirmed" if day in confirmed else ("predicted" if (day in ov_pred and future_or_now) else None)
        if not show_fertile:
            ovulation = None
        symptoms = sum(1 for f in log.get("factors") or () if chip_signal(f) == "symptom") + (1 if (log.get("pain_level") or 0) >= 1 else 0)
        rows.append({"date": day, "cycle_day": cycle_day, "phase": phase, "period": period, "fertile": fertile, "ovulation": ovulation,
                     "period_start": bool(log.get("period_start")) or day in state["starts"], "flow": log.get("flow"),
                     "has_log": bool(log), "symptom_count": symptoms, "pain_level": log.get("pain_level"),
                     "is_today": day == today, "is_future": day > today})
        day += _days(1)
    return rows


# --------------------------------------------------------------------------------------------------
# insights (phase x metric), never causal
# --------------------------------------------------------------------------------------------------

#: id -> (label, unit, source label, threshold scale, decimals)
METRICS = {
    "energy": ("Energy", "1-5", "your cycle logs", 4.0, 1),
    "mood": ("Mood balance", "-1 to +1", "your cycle logs", 2.0, 2),
    "pain": ("Pain", "0-10", "your cycle logs", 10.0, 1),
    "sleep_quality": ("Sleep quality", "1-5", "your cycle logs", 4.0, 1),
    "sleep_hours": ("Sleep duration", "hours", "your sleep tracker", 4.0, 1),
    "tracker_mood": ("Mood score", "1-10", "your mood tracker", 9.0, 1),
    "weight": ("Weight change within a cycle", "kg vs your cycle average", "your weight tracker", 5.0, 2),
}


def mood_balance(log: Mapping[str, Any]) -> float | None:
    pos = sum(1 for f in log.get("factors") or () if chip_signal(f) == "mood_positive")
    neg = sum(1 for f in log.get("factors") or () if chip_signal(f) == "mood_negative")
    return (pos - neg) / (pos + neg) if pos + neg else None


def _phase_of(state: dict, day: date) -> tuple[str, date] | None:
    """Phase for a date inside a COMPLETED cycle (the current cycle is still being written), else None."""
    cd, phase = locate(state, day)
    if cd is None or phase is None:
        return None
    for c in state["_index"]:
        if c["start"] <= day and c["complete"] and day < c["next_start"]:
            return phase, c["start"]
    return None


def compute_insights(state: dict, logs: Logs, tracker: Mapping[str, list[tuple[date, float]]] | None = None) -> dict:
    tracker = tracker or {}
    completed = sum(1 for c in state["cycles"] if c["length"] is not None)
    min_cycles, min_points = K.INSIGHT_MIN_CYCLES, K.INSIGHT_MIN_POINTS_PER_PHASE
    series: dict[str, list[tuple[date, float]]] = {k: [] for k in METRICS}
    for d, log in sorted(logs.items()):
        for key, field in (("energy", "energy"), ("pain", "pain_level"), ("sleep_quality", "sleep_quality")):
            if isinstance(log.get(field), (int, float)):
                series[key].append((d, float(log[field])))
        bal = mood_balance(log)
        if bal is not None:
            series["mood"].append((d, bal))
    series["sleep_hours"] = list(tracker.get("sleep_hours", []))
    series["tracker_mood"] = list(tracker.get("tracker_mood", []))
    series["weight"] = _center_by_cycle(state, tracker.get("weight_kg", []))

    metrics = []
    for key, (label, unit, source, scale, decimals) in METRICS.items():
        buckets: dict[str, list[tuple[float, date]]] = {p: [] for p in PHASES}
        for d, value in series[key]:
            found = _phase_of(state, d)
            if found:
                buckets[found[0]].append((value, found[1]))
        per_phase = [{"phase": p, "mean": round(mean(v for v, _c in buckets[p]), decimals) if buckets[p] else None,
                      "n": len(buckets[p]), "cycles": len({c for _v, c in buckets[p]})} for p in PHASES]
        enough = [p for p in per_phase if p["n"] >= min_points]
        cycles_with = len({c for p in PHASES for _v, c in buckets[p]})
        entry = {"id": key, "label": label, "unit": unit, "source": source, "ready": False, "needs": None, "per_phase": per_phase,
                 "difference": None, "summary": None, "confidence": None}
        if cycles_with < min_cycles or len(enough) < 2:
            entry["needs"] = (f"Needs about {min_cycles} full cycles with at least {min_points} {label.lower()} entries in two or more phases "
                              f"(so far {cycles_with} cycle{'s' if cycles_with != 1 else ''}).")
        else:
            hi = max(enough, key=lambda p: p["mean"])
            lo = min(enough, key=lambda p: p["mean"])
            diff = round(hi["mean"] - lo["mean"], decimals)
            entry.update(ready=True, difference=diff, confidence="moderate" if cycles_with >= 5 and min(p["n"] for p in enough) >= 8 else "low")
            if diff >= K.INSIGHT_MIN_DIFFERENCE_FRACTION * scale:
                entry["summary"] = (f"In {source}, {label.lower()} tends to be higher in your {hi['phase']} phase ({hi['mean']}) than in your "
                                    f"{lo['phase']} phase ({lo['mean']}), across {cycles_with} cycles. This is a pattern in what you recorded, not a cause.")
            else:
                entry["summary"] = f"No clear difference in {label.lower()} between phases so far ({cycles_with} cycles)."
        metrics.append(entry)

    symptoms = _symptom_phases(state, logs)
    ready = completed >= min_cycles and any(m["ready"] for m in metrics)
    if completed < min_cycles:
        message = (f"Bubbles is still learning. Phase patterns need at least {min_cycles} full cycles; you have {completed}. "
                   "Keep logging how you feel and they will appear.")
    elif not ready:
        message = "Bubbles has your cycles but needs more daily logs (energy, mood, pain, sleep) before it can compare phases."
    else:
        message = "Here is what your own logs show across the phases of your cycle."
    return {"ready": ready, "cycles_used": completed, "min_cycles": min_cycles, "message": message, "metrics": metrics,
            "symptoms": symptoms}


def _center_by_cycle(state: dict, points: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """Weight against that cycle's own average, so a long-term trend is not mistaken for a phase effect."""
    by_cycle: dict[date, list[tuple[date, float]]] = {}
    for d, v in points:
        found = _phase_of(state, d)
        if found:
            by_cycle.setdefault(found[1], []).append((d, v))
    out = []
    for rows in by_cycle.values():
        if len(rows) >= 2:
            m = mean(v for _d, v in rows)
            out.extend((d, v - m) for d, v in rows)
    return out


def _symptom_phases(state: dict, logs: Logs) -> list[dict]:
    logged_days = {p: 0 for p in PHASES}
    counts: dict[str, dict[str, int]] = {}
    for d, log in logs.items():
        found = _phase_of(state, d)
        if not found:
            continue
        phase = found[0]
        logged_days[phase] += 1
        for f in set(log.get("factors") or ()):
            if chip_signal(f) == "symptom":
                counts.setdefault(f, {p: 0 for p in PHASES})[phase] += 1
    rows = []
    for chip_id, per in counts.items():
        total = sum(per.values())
        if total < 3:
            continue
        rows.append({"id": chip_id, "label": (CHIP_BY_ID.get(chip_id) or {}).get("label", chip_id), "total_days": total,
                     "per_phase": [{"phase": p, "days": per[p], "share": round(per[p] / logged_days[p], 2) if logged_days[p] else 0.0}
                                   for p in PHASES],
                     "most_common_phase": max(PHASES, key=lambda p: (per[p] / logged_days[p]) if logged_days[p] else 0)})
    return sorted(rows, key=lambda r: -r["total_days"])[:8]
