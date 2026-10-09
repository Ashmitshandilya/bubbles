"""cycle_engine: predictions, ranges, confidence, modes, BBT / LH tightening, phases, calendar and insights on synthetic histories."""
from __future__ import annotations

from datetime import date, timedelta as td

import pytest

import clinical_constants as K
import cycle_engine as E

TODAY = date(2026, 10, 8)


def logs_for(starts, period_days=5, **extra):
    """Flow logs for every day of every period (so period length is known)."""
    out = {}
    for s in starts:
        for i in range(period_days):
            out[s + td(days=i)] = {"flow": "medium" if i < 3 else "light", "period_start": i == 0, **extra}
    return out


def history(lengths, last_start_days_ago=10, period_days=5):
    """Starts that produce exactly `lengths` (oldest -> newest) with the newest start `last_start_days_ago` before TODAY."""
    starts = [TODAY - td(days=last_start_days_ago)]
    for length in reversed(lengths):
        starts.insert(0, starts[0] - td(days=length))
    return starts, logs_for(starts, period_days)


def analyse(lengths, mode="track", ago=10, **kw):
    starts, logs = history(lengths, ago)
    return E.analyse(logs, today=TODAY, mode=mode, **kw), starts, logs


# ---- personal averages, ranges, confidence ---------------------------------------------------------

def test_regular_28_day_history_gives_narrow_high_confidence_ranges():
    st, starts, _ = analyse([28] * 6)
    assert st["lengths"] == [28] * 6 and st["confidence"] == "high" and not st["irregular"]
    nxt = st["next_period"]
    assert nxt["date"] == starts[-1] + td(days=28)
    assert (nxt["latest"] - nxt["earliest"]).days == 2 * K.CYCLE_WINDOW_HALF_DAYS[0]
    assert nxt["status"] == "upcoming" and nxt["in_days"] == 18
    assert st["regularity"]["score"] == 100


def test_ovulation_is_luteal_days_before_next_period_and_fertile_window_is_five_days_plus_ovulation():
    st, _, _ = analyse([28] * 6)
    ov, fw, nxt = st["ovulation"], st["fertile_window"], st["next_period"]
    assert (nxt["date"] - ov["date"]).days == K.LUTEAL_LENGTH_DAYS
    assert (fw["end"] - fw["start"]).days == K.FERTILE_WINDOW_DAYS_BEFORE_OVULATION
    assert fw["end"] == ov["date"] and ov["source"] == "calendar" and not ov["confirmed"]
    assert fw["earliest"] <= fw["start"] and fw["latest"] >= fw["end"]


def test_luteal_override_moves_ovulation():
    st, _, _ = analyse([28] * 6, luteal_days=12)
    assert (st["next_period"]["date"] - st["ovulation"]["date"]).days == 12
    st, _, _ = analyse([28] * 6, luteal_days=99)   # clamped into the allowed range
    assert (st["next_period"]["date"] - st["ovulation"]["date"]).days == K.LUTEAL_RANGE_DAYS[1]


@pytest.mark.parametrize("n_cycles,label", [(0, "learning"), (1, "learning"), (2, "learning"), (3, "medium"), (5, "medium"), (6, "high")])
def test_confidence_is_learning_until_three_cycles(n_cycles, label):
    st, _, _ = analyse([28 + (i % 2) for i in range(n_cycles)] if n_cycles in (3, 5) else [28] * n_cycles)
    assert st["confidence"] == label


def test_learning_uses_default_length_and_wide_window():
    starts = [TODAY - td(days=10)]
    st = E.analyse(logs_for(starts), today=TODAY)
    assert st["confidence"] == "learning" and st["predicted_length"] == K.CYCLE_DEFAULT_LENGTH_DAYS
    nxt = st["next_period"]
    assert (nxt["date"] - nxt["earliest"]).days == K.CYCLE_LEARNING_HALF_WINDOW_DAYS


def test_no_data_means_no_prediction_and_no_crash():
    st = E.analyse({}, today=TODAY)
    assert st["next_period"] is None and st["cycle_day"] is None and st["phase"] is None and st["confidence"] == "learning"
    assert E.calendar_days(st, {}, date(2026, 10, 1), date(2026, 10, 31))[0]["period"] is None


def test_recent_cycles_weigh_more():
    stats = E.length_stats([30, 30, 30, 26])
    plain = sum([30, 30, 30, 26]) / 4
    weights = [0.8 ** 3, 0.8 ** 2, 0.8, 1.0]
    expected = sum(w * x for w, x in zip(weights, [30, 30, 30, 26])) / sum(weights)
    assert stats["weighted_mean"] == pytest.approx(expected) and stats["weighted_mean"] < plain


def test_irregular_mode_widens_windows_and_lowers_confidence():
    reg, _, _ = analyse([28] * 6)
    irr, _, _ = analyse([24, 35, 27, 40, 26, 38])
    assert irr["irregular"] and irr["confidence"] == "low" and irr["length_stats"]["sd"] > K.IRREGULAR_SD_DAYS
    assert irr["half_window"] > reg["half_window"] * 3
    assert irr["regularity"]["label"] in {"Irregular", "Somewhat variable"}


def test_window_half_width_is_clamped():
    st, _, _ = analyse([21, 60, 25, 70, 22, 80])
    assert st["half_window"] == K.CYCLE_WINDOW_HALF_DAYS[1]


@pytest.mark.parametrize("length", [21, 24, 35, 40])
def test_short_and_long_regular_cycles_are_predicted_at_their_own_length(length):
    st, starts, _ = analyse([length] * 5, ago=3)
    assert st["predicted_length"] == length
    assert st["next_period"]["date"] == starts[-1] + td(days=length)


def test_pcos_like_long_variable_cycles_are_low_confidence_with_wide_ranges():
    st, _, _ = analyse([38, 52, 33, 60, 41, 47], ago=5)
    assert st["confidence"] == "low" and st["irregular"]
    window = st["next_period"]
    assert (window["latest"] - window["earliest"]).days >= 8


def test_implausible_gaps_are_missed_logs_not_cycles():
    starts = [TODAY - td(days=300), TODAY - td(days=150), TODAY - td(days=122), TODAY - td(days=94)]
    st = E.analyse(logs_for(starts), today=TODAY)
    assert st["lengths"] == [28, 28]   # the 150-day gap is not a cycle length


def test_late_period_status_and_days():
    st, starts, _ = analyse([28] * 5, ago=36)
    nxt = st["next_period"]
    assert nxt["status"] == "late" and nxt["late_by_days"] == 8 and st["cycle_day"] == 37


def test_due_status_inside_window():
    st, _, _ = analyse([28] * 5, ago=28)
    assert st["next_period"]["status"] == "due"


# ---- markers ---------------------------------------------------------------------------------------

def test_second_start_within_a_week_is_the_same_period():
    assert E.merge_starts([date(2026, 1, 1), date(2026, 1, 5), date(2026, 1, 29)]) == [date(2026, 1, 1), date(2026, 1, 29)]


def test_starts_are_derived_from_flow_runs_without_explicit_taps():
    logs = {}
    for s in (date(2026, 8, 1), date(2026, 8, 29), date(2026, 9, 26)):
        for i in range(4):
            logs[s + td(days=i)] = {"flow": "medium"}
    logs[date(2026, 9, 10)] = {"flow": "spotting"}   # spotting is not a period day
    st = E.analyse(logs, today=TODAY)
    assert st["starts"] == [date(2026, 8, 1), date(2026, 8, 29), date(2026, 9, 26)]
    assert [c["period_days"] for c in st["cycles"]] == [4, 4, 4]


def test_explicit_end_sets_period_length_and_one_day_runs_do_not():
    logs = {date(2026, 9, 1): {"period_start": True, "flow": "medium"}, date(2026, 9, 6): {"period_end": True}}
    st = E.analyse(logs, today=TODAY)
    assert st["cycles"][0]["period_days"] == 6
    only_start = E.analyse({date(2026, 9, 1): {"period_start": True}}, today=TODAY)
    assert only_start["cycles"][0]["period_days"] is None


def test_tracker_starts_are_merged_in():
    st = E.analyse({}, today=TODAY, extra_starts=[TODAY - td(days=56), TODAY - td(days=28), TODAY])
    assert st["lengths"] == [28, 28]


def test_future_starts_are_ignored():
    st = E.analyse({}, today=TODAY, extra_starts=[TODAY + td(days=5)])
    assert st["starts"] == []


# ---- phases / cycle day ---------------------------------------------------------------------------------

def test_phase_for_day_covers_the_cycle():
    assert E.phase_for_day(1, 28, 5, 14) == "menstrual" and E.phase_for_day(5, 28, 5, 14) == "menstrual"
    assert E.phase_for_day(8, 28, 5, 14) == "follicular"
    assert [E.phase_for_day(d, 28, 5, 14) for d in (14, 15, 16)] == ["ovulatory"] * 3
    assert E.phase_for_day(22, 28, 5, 14) == "luteal"


def test_cycle_day_and_phase_for_any_date():
    st, starts, _ = analyse([28] * 6)
    assert E.locate(st, starts[-1]) == (1, "menstrual")
    assert E.locate(st, starts[-1] + td(days=27))[0] == 28
    assert E.locate(st, starts[-3] + td(days=2)) == (3, "menstrual")           # a past cycle
    assert E.locate(st, starts[0] - td(days=1)) == (None, None)                 # before any data
    future = st["next_period"]["date"] + td(days=3)
    assert E.locate(st, future) == (4, "menstrual")                              # rolled into the next predicted cycle
    assert st["cycle_day"] == 11 and st["phase"] == "follicular"


def test_stale_history_has_no_cycle_day():
    st, _, _ = analyse([28] * 4, ago=200)
    assert st["cycle_day"] is None and st["stale"] and st["phase"] is None


# ---- BBT and LH ----------------------------------------------------------------------------------------

def temps(start, values):
    return {start + td(days=i): v for i, v in enumerate(values)}


def test_bbt_three_over_six_detects_shift_and_ovulation_day():
    t = temps(date(2026, 9, 1), [36.3, 36.35, 36.3, 36.4, 36.3, 36.35, 36.3, 36.7, 36.75, 36.8, 36.8])
    shift = E.detect_bbt_shift(t)
    assert shift["first_high_day"] == date(2026, 9, 8) and shift["ovulation_day"] == date(2026, 9, 7)
    assert shift["rise_c"] >= K.BBT_SHIFT_RISE_C


@pytest.mark.parametrize("values", [
    [36.3] * 9,                                                      # flat
    [36.3, 36.35, 36.3, 36.4, 36.3, 36.35, 36.45, 36.45, 36.45],     # rise too small
    [36.3, 36.35, 36.3, 36.4, 36.3, 36.35, 36.7, 36.3, 36.7],        # not 3 in a row
    [36.3, 36.35],                                                   # too few readings
])
def test_bbt_no_shift(values):
    assert E.detect_bbt_shift(temps(date(2026, 9, 1), values)) is None


def test_bbt_readings_spread_too_far_apart_do_not_count():
    t = {date(2026, 9, 1) + td(days=3 * i): v for i, v in enumerate([36.3, 36.3, 36.3, 36.3, 36.3, 36.3, 36.8, 36.8, 36.8])}
    assert E.detect_bbt_shift(t) is None


def test_bbt_confirms_ovulation_and_tightens_next_period():
    start = TODAY - td(days=14)
    logs = logs_for([start - td(days=28 * k) for k in range(5, 0, -1)] + [start])
    for d, v in temps(start + td(days=5), [36.3, 36.35, 36.3, 36.4, 36.3, 36.35, 36.3, 36.7, 36.75, 36.8]).items():
        logs.setdefault(d, {})["bbt_c"] = v
    st = E.analyse(logs, today=TODAY)
    ov = st["ovulation"]
    assert ov["confirmed"] and ov["source"] == "bbt"
    assert st["next_period"]["date"] == ov["date"] + td(days=K.LUTEAL_LENGTH_DAYS)
    assert (st["next_period"]["latest"] - st["next_period"]["earliest"]).days <= 4


def test_illness_or_alcohol_days_are_ignored_for_bbt():
    start = TODAY - td(days=14)
    logs = logs_for([start])
    for d, v in temps(start + td(days=5), [36.3, 36.35, 36.3, 36.4, 36.3, 36.35, 36.3, 36.7, 36.75, 36.8]).items():
        logs.setdefault(d, {})["bbt_c"] = v
    for d in (start + td(days=12), start + td(days=13), start + td(days=14)):
        logs[d]["factors"] = ["fever"]
    st = E.analyse(logs, today=TODAY)
    assert not st["ovulation"]["confirmed"]


def test_lh_positive_tightens_ovulation_but_does_not_confirm_it():
    start = TODAY - td(days=14)
    logs = logs_for([start - td(days=28 * k) for k in range(5, 0, -1)] + [start])
    logs[start + td(days=11)] = {"ovulation_test": "positive"}
    logs[start + td(days=12)] = {"ovulation_test": "peak"}
    st = E.analyse(logs, today=TODAY)
    ov = st["ovulation"]
    assert ov["source"] == "lh_test" and not ov["confirmed"] and ov["date"] == start + td(days=12)
    assert (ov["latest"] - ov["earliest"]).days == K.LH_OVULATION_AFTER_POSITIVE_DAYS[1] - K.LH_OVULATION_AFTER_POSITIVE_DAYS[0]


# ---- modes ----------------------------------------------------------------------------------------------

def test_birth_control_hides_fertility_but_predicts_the_next_bleed():
    st, _, _ = analyse([28] * 5, mode="birth_control")
    assert st["ovulation"] is None and st["fertile_window"] is None and st["next_period"]
    assert "birth control" in st["fertility_note"].lower()
    rows = E.calendar_days(st, {}, TODAY, TODAY + td(days=40))
    assert all(r["fertile"] is None and r["ovulation"] is None for r in rows)


def test_conceive_mode_keeps_fertility_and_adds_a_note():
    st, _, _ = analyse([28] * 5, mode="conceive")
    assert st["fertile_window"] and st["fertility_note"]


def test_pregnancy_mode_pauses_period_predictions_and_counts_weeks():
    lmp = TODAY - td(days=7 * 12 + 3)
    st = E.analyse({}, today=TODAY, mode="pregnancy", lmp=lmp, extra_starts=[lmp])
    assert st["next_period"] is None and st["fertile_window"] is None
    p = st["pregnancy"]
    assert (p["week"], p["day"], p["trimester"]) == (12, 3, 1)
    assert p["due_date"] == lmp + td(days=K.PREGNANCY_DAYS) and p["days_to_go"] == K.PREGNANCY_DAYS - 87
    assert E.pregnancy_info(TODAY, None, TODAY + td(days=100))["week"] == (K.PREGNANCY_DAYS - 100) // 7
    assert E.pregnancy_info(TODAY, None, None) is None and E.pregnancy_info(TODAY, TODAY + td(days=3), None) is None
    assert E.pregnancy_info(TODAY, TODAY - td(days=7 * 30), None)["trimester"] == 3
    rows = E.calendar_days(st, {}, TODAY, TODAY + td(days=60))
    assert all(r["period"] is None for r in rows)


def test_postpartum_ignores_lochia_bleeding_and_is_low_confidence():
    delivery = TODAY - td(days=200)
    starts = [delivery + td(days=10)] + [delivery + td(days=60 + 30 * i) for i in range(5)]
    st = E.analyse(logs_for(starts), today=TODAY, mode="postpartum", delivery_date=delivery)
    assert delivery + td(days=10) not in st["starts"]
    assert st["confidence"] == "low" and st["fertile_window"] is None and "ovulation" in st["fertility_note"].lower()
    assert st["postpartum"]["weeks_since"] == 28 and not st["postpartum"]["lochia_expected"]
    assert E.postpartum_info(TODAY, TODAY - td(days=10))["lochia_expected"]


def test_perimenopause_is_low_confidence_with_doubled_window():
    base, _, _ = analyse([28, 29, 28, 29, 28, 29])
    peri, _, _ = analyse([28, 29, 28, 29, 28, 29], mode="perimenopause")
    assert peri["confidence"] == "low" and peri["half_window"] == min(14, base["half_window"] * 2)
    assert peri["fertile_window"] and "rough" in peri["fertility_note"]


def test_unknown_mode_falls_back_to_track():
    assert E.analyse({}, today=TODAY, mode="nonsense")["mode"] == "track"


# ---- PMS hint, weather, calendar, insights ---------------------------------------------------------------------

def symptom_history(with_symptoms=True):
    starts, logs = history([28] * 5, 10)
    if with_symptoms:
        for s in starts[1:]:
            for k in (3, 2, 1):                                   # symptoms 1-3 days before each period
                logs[s - td(days=k)] = {"factors": ["bloating", "irritable"], "pain_level": 4}
    return starts, logs


def test_personal_pms_window_is_learned_from_symptom_days():
    _, logs = symptom_history()
    st = E.analyse(logs, today=TODAY)
    pms = st["pms"]
    assert pms["personal"] and pms["cycles_used"] >= 3 and "day 26-28" in pms["text"]
    assert pms["to"] == st["next_period"]["date"] - td(days=1)


def test_general_pms_hint_without_logs_is_not_personal():
    _, logs = symptom_history(False)
    pms = E.analyse(logs, today=TODAY)["pms"]
    assert pms["personal"] is False and "Log how you feel" in pms["text"]


def test_weather_tone():
    assert E.weather_tone("menstrual", {"flow": "heavy"}, False) == "heavier"
    assert E.weather_tone("luteal", {"pain_level": 7}, False) == "heavier"
    assert E.weather_tone("follicular", {"energy": 5, "factors": ["happy", "calm"]}, False) == "bright"
    assert E.weather_tone("luteal", {"energy": 3}, False) == "steady"
    assert E.weather_tone("follicular", None, False) == "bright"
    assert E.weather_tone("luteal", None, True) == "heavier"
    assert E.weather_tone("menstrual", None, False) == "steady"


def test_calendar_markers():
    st, starts, logs = analyse([28] * 5)
    rows = {r["date"]: r for r in E.calendar_days(st, logs, starts[-1], TODAY + td(days=40))}
    assert rows[starts[-1]]["period"] == "logged" and rows[starts[-1]]["period_start"]
    nxt = st["next_period"]["date"]
    assert rows[nxt]["period"] == "predicted" and rows[nxt - td(days=1)]["period"] == "possible"
    assert rows[TODAY]["is_today"] and rows[TODAY + td(days=1)]["is_future"]
    assert rows[st["ovulation"]["date"]]["ovulation"] == "predicted"
    assert any(r["fertile"] == "predicted" for r in rows.values())
    assert rows[starts[-1] + td(days=2)]["has_log"]


def test_insights_need_cycles_and_data_then_report_phase_differences_without_causal_words():
    starts, logs = history([28] * 6)
    st = E.analyse(logs, today=TODAY)
    empty = E.compute_insights(st, logs)
    assert not empty["ready"] and all(m["needs"] for m in empty["metrics"])
    for s in starts[:-1]:
        for offset in range(0, 28):
            d = s + td(days=offset)
            log = logs.setdefault(d, {})
            log["energy"] = 2 if offset >= 20 else 4
    st = E.analyse(logs, today=TODAY)
    out = E.compute_insights(st, logs)
    energy = next(m for m in out["metrics"] if m["id"] == "energy")
    assert out["ready"] and energy["ready"] and energy["difference"] >= 1.0
    assert "luteal" in energy["summary"] and "not a cause" in energy["summary"]
    assert "because" not in energy["summary"].lower() and "caused by" not in energy["summary"].lower()
    assert energy["confidence"] in {"low", "moderate"}


def test_insights_say_no_clear_difference_when_phases_match():
    starts, logs = history([28] * 6)
    for s in starts[:-1]:
        for offset in range(28):
            logs.setdefault(s + td(days=offset), {})["energy"] = 3
    out = E.compute_insights(E.analyse(logs, today=TODAY), logs)
    assert "No clear difference" in next(m for m in out["metrics"] if m["id"] == "energy")["summary"]


def test_symptom_by_phase_and_tracker_series():
    starts, logs = history([28] * 6)
    for s in starts[:-1]:
        for offset in range(28):
            d = s + td(days=offset)
            logs.setdefault(d, {})["factors"] = ["bloating"] if offset >= 22 else []
    st = E.analyse(logs, today=TODAY)
    out = E.compute_insights(st, logs)
    bloat = next(s for s in out["symptoms"] if s["id"] == "bloating")
    assert bloat["most_common_phase"] == "luteal"
    sleep = [(s + td(days=o), 8.0 if o < 14 else 6.0) for s in starts[:-1] for o in range(28)]
    out = E.compute_insights(st, logs, {"sleep_hours": sleep})
    assert next(m for m in out["metrics"] if m["id"] == "sleep_hours")["ready"]


def test_regularity_none_before_three_cycles():
    assert E.regularity(1.0, 2) is None and E.regularity(None, 5) is None
    assert E.regularity(0.0, 5)["score"] == 100 and E.regularity(8.0, 5)["score"] == 0
