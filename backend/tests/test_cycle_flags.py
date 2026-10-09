"""cycle_flags: the clinician-prompt matrix from the review packet (section 9), the kind wording, and the safety gate for notes."""
from __future__ import annotations

from datetime import date, timedelta as td

import pytest

import clinical_constants as K
import cycle_engine as E
from cycle_flags import assess_notes, compute_flags, day_flags

TODAY = date(2026, 10, 8)


def run(starts, *, mode="track", age_group="adult", extra=None, period_days=4, **kw):
    logs = {}
    for s in starts:
        for i in range(period_days):
            logs[s + td(days=i)] = {"flow": "medium", "period_start": i == 0}
    for d, v in (extra or {}).items():
        logs.setdefault(d, {}).update(v)
    state = E.analyse(logs, today=TODAY, mode=mode, **kw)
    state["age_group"] = age_group
    return compute_flags(state, logs), state


def chain(lengths, ago=5):
    starts = [TODAY - td(days=ago)]
    for n in reversed(lengths):
        starts.insert(0, starts[0] - td(days=n))
    return starts


def ids(flags):
    return {f["id"] for f in flags}


# ---- cycle length ------------------------------------------------------------------------------------

@pytest.mark.parametrize("length,flagged", [(19, True), (20, True), (21, False), (28, False), (35, False), (36, True), (50, True)])
def test_cycle_length_outside_21_to_35_prompts_a_clinician(length, flagged):
    flags, _ = run(chain([28, 28, 28, length]))
    assert ("cycle_length" in ids(flags)) is flagged
    if flagged:
        f = next(f for f in flags if f["id"] == "cycle_length")
        assert f["severity"] == "talk" and str(length) in f["message"]


def test_teen_range_is_wider():
    adult, _ = run(chain([28, 28, 28, 40]))
    teen, _ = run(chain([28, 28, 28, 40]), age_group="teen")
    assert "cycle_length" in ids(adult) and "cycle_length" not in ids(teen)
    assert "cycle_length" in ids(run(chain([28, 28, 28, 47]), age_group="teen")[0])


@pytest.mark.parametrize("mode", ["postpartum", "perimenopause", "birth_control"])
def test_cycle_length_is_only_a_note_in_modes_where_cycles_change(mode):
    flags, _ = run(chain([28, 28, 28, 45]), mode=mode)
    assert next(f for f in flags if f["id"] == "cycle_length")["severity"] == "info"


def test_sudden_change_within_the_normal_range_is_a_gentle_note():
    flags, _ = run(chain([22, 22, 22, 22, 34]))
    f = next(f for f in flags if f["id"] == "sudden_change")
    assert f["severity"] == "info"


# ---- period length / bleeding -----------------------------------------------------------------------------

@pytest.mark.parametrize("days,flagged", [(5, False), (7, False), (8, True), (10, True)])
def test_period_longer_than_seven_days(days, flagged):
    starts = chain([28, 28, 28], ago=40)
    flags, _ = run(starts, period_days=days)
    assert ("long_period" in ids(flags)) is flagged


def test_soaking_a_pad_every_hour_is_urgent_and_comes_first():
    flags, _ = run(chain([28] * 4), extra={TODAY: {"soaking_hourly": True, "pain_level": 9}})
    assert flags[0]["id"] == "heavy_bleeding" and flags[0]["severity"] == "urgent"
    msg = flags[0]["message"].lower()
    assert "urgent" in msg and "emergency" in msg and "two hours" in msg
    assert day_flags({"soaking_hourly": True})[0]["severity"] == "urgent"


def test_old_soaking_log_does_not_stay_urgent():
    flags, _ = run(chain([28] * 4), extra={TODAY - td(days=5): {"soaking_hourly": True}})
    assert "heavy_bleeding" not in ids(flags)


@pytest.mark.parametrize("pain,flagged", [(7, False), (8, True), (10, True)])
def test_severe_pain(pain, flagged):
    flags, _ = run(chain([28] * 4), extra={TODAY - td(days=1): {"pain_level": pain}})
    assert ("severe_pain" in ids(flags)) is flagged
    assert bool(day_flags({"pain_level": pain})) is flagged


def test_bleeding_between_periods_is_flagged_and_softer_on_birth_control():
    starts = [TODAY - td(days=100), TODAY - td(days=72), TODAY - td(days=44), TODAY - td(days=16), TODAY - td(days=4)]
    flags, _ = run(starts)
    assert next(f for f in flags if f["id"] == "bleeding_between_periods")["severity"] == "talk"
    flags, _ = run(starts, mode="birth_control")
    assert next(f for f in flags if f["id"] == "bleeding_between_periods")["severity"] == "info"


def test_spotting_between_periods_is_only_an_info_note():
    starts = chain([28, 28, 28], ago=14)
    flags, _ = run(starts, extra={TODAY - td(days=3): {"flow": "spotting"}, TODAY - td(days=2): {"flow": "spotting"}})
    assert next(f for f in flags if f["id"] == "spotting_between")["severity"] == "info"
    flags, _ = run(starts, extra={TODAY - td(days=3): {"flow": "spotting"}})
    assert "spotting_between" not in ids(flags)


# ---- missed periods and long gaps ----------------------------------------------------------------------------

@pytest.mark.parametrize("ago,flagged", [(60, False), (90, False), (96, True), (130, True)])
def test_three_missed_periods_prompt_a_clinician(ago, flagged):
    starts = [TODAY - td(days=ago + 28 * k) for k in (3, 2, 1, 0)]
    flags, _ = run(starts)
    assert ("missed_periods" in ids(flags)) is flagged
    if flagged:
        f = next(f for f in flags if f["id"] == "missed_periods")
        assert f["severity"] == "talk" and "not pregnant" in f["message"] and "have not logged" in f["message"]


@pytest.mark.parametrize("mode", ["pregnancy", "birth_control", "postpartum", "perimenopause"])
def test_missed_periods_are_not_flagged_when_it_is_expected(mode):
    starts = [TODAY - td(days=150 + 28 * k) for k in (3, 2, 1, 0)]
    kw = {"lmp": TODAY - td(days=60)} if mode == "pregnancy" else {}
    flags, _ = run(starts, mode=mode, **kw)
    assert "missed_periods" not in ids(flags)


def test_bleeding_after_twelve_months_without_a_period():
    flags, _ = run([TODAY - td(days=420), TODAY - td(days=5)])
    f = next(f for f in flags if f["id"] == "bleeding_after_long_gap")
    assert f["severity"] == "talk"
    assert "bleeding_after_long_gap" not in ids(run([TODAY - td(days=300), TODAY - td(days=5)])[0])
    assert "bleeding_after_long_gap" not in ids(run([TODAY - td(days=420), TODAY - td(days=5)], mode="postpartum")[0])


def test_perimenopause_gets_a_gentle_note_for_a_year_without_a_period():
    flags, _ = run([TODAY - td(days=400)], mode="perimenopause")
    assert next(f for f in flags if f["id"] == "long_gap_perimenopause")["severity"] == "info"


# ---- pregnancy ------------------------------------------------------------------------------------------------

def test_pregnancy_bleeding_asks_for_same_day_contact_and_nothing_else_cyclic():
    flags, _ = run([], mode="pregnancy", lmp=TODAY - td(days=70), extra={TODAY: {"flow": "light"}})
    assert ids(flags) == {"pregnancy_bleeding"}
    assert "today" in flags[0]["message"]


def test_positive_test_outside_pregnancy_mode_is_offered_a_mode_switch():
    flags, _ = run(chain([28] * 4), extra={TODAY - td(days=1): {"pregnancy_test": "positive"}})
    assert "positive_pregnancy_test" in ids(flags)
    flags, _ = run([], mode="pregnancy", lmp=TODAY - td(days=70), extra={TODAY: {"pregnancy_test": "positive"}})
    assert "positive_pregnancy_test" not in ids(flags)


# ---- tone ----------------------------------------------------------------------------------------------------------

def test_every_flag_message_is_kind_and_never_diagnoses():
    everything = []
    everything += run(chain([28, 28, 28, 19]), extra={TODAY: {"soaking_hourly": True, "pain_level": 9, "pregnancy_test": "positive"}})[0]
    everything += run(chain([22, 22, 22, 22, 34]), period_days=9)[0]
    everything += run([TODAY - td(days=420), TODAY - td(days=12), TODAY - td(days=5)])[0]
    everything += run([TODAY - td(days=150 + 28 * k) for k in (3, 2, 1, 0)])[0]
    everything += run([], mode="pregnancy", lmp=TODAY - td(days=70), extra={TODAY: {"flow": "light"}})[0]
    assert len(ids(everything)) >= 8
    for f in everything:
        text = (f["title"] + " " + f["message"] + " " + (f["detail"] or "")).lower()
        assert f["severity"] in {"info", "talk", "urgent"}
        assert not any(p in text for p in K.FORBIDDEN_ADVICE), text
        assert "you have pcos" not in text and "you are pregnant" not in text.replace("if you are pregnant", "") and "abnormal" not in text and "diagnos" not in text
        assert "clinician" in text or "doctor" in text or "midwife" in text or "emergency" in text or "pregnancy" in text


def test_flags_are_sorted_urgent_first_and_unique():
    flags, _ = run(chain([28, 28, 28, 19]), extra={TODAY: {"soaking_hourly": True, "pain_level": 9}})
    order = [f["severity"] for f in flags]
    assert order == sorted(order, key={"urgent": 0, "talk": 1, "info": 2}.get)
    assert len(ids(flags)) == len(flags)


# ---- notes go through the safety engine ----------------------------------------------------------------------------

def test_urgent_notes_return_the_deterministic_response():
    result = assess_notes("I have crushing chest pain right now")
    assert result["state"] == "EMERGENCY" and result["level"] == "RED" and "urgent medical help" in result["message"]
    assert "cycle" not in result["message"].lower()


@pytest.mark.parametrize("text", ["", None, "cramps were worse today, felt tired", "light flow, slept badly"])
def test_ordinary_notes_pass(text):
    assert assess_notes(text) is None


def test_notes_are_combined_across_fields_and_none_values_are_skipped():
    assert assess_notes(None, "fine", "I want to end my life")["state"] == "EMERGENCY"
