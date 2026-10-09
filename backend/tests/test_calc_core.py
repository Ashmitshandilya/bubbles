"""Known-value and missing-data tests for calc_core (deterministic, no database)."""
from datetime import datetime, timezone

import calc_core as c


def test_bmi_known_value_and_provenance():
    r = c.calc_bmi(70, 170)  # 70 / 1.7^2 = 24.22
    d = r.to_dict()
    assert r.status == "ok" and r.value == 24.2 and d["version"] == "1.0" and d["inputs"]["height_cm"] == 170 and d["method"]


def test_bmi_not_applicable_for_children_and_pregnancy_and_invalid_inputs():
    assert c.calc_bmi(40, 150, age_years=12).status == "not_applicable"
    assert c.calc_bmi(70, 170, pregnant=True).status == "not_applicable"
    assert c.calc_bmi(70, 20).status == "invalid_input"          # implausible height
    assert c.calc_bmi("abc", 170).status == "invalid_input"


def test_missing_is_never_zero():
    r = c.mean_logged([7, None, "", 6, "x"], unit="h")
    assert r.value == 6.5 and r.inputs == {"n_logged": 2, "n_missing": 3}
    assert c.mean_logged([None, None]).status == "insufficient_data"
    assert c.mean_logged([True, 8]).value == 8.0                 # booleans are not numbers


def test_cycle_length_abstains_below_minimum_and_reports_above():
    assert c.cycle_length_summary([28, 30]).status == "insufficient_data"
    r = c.cycle_length_summary([28, 30, 29])
    assert r.status == "ok" and r.value["n"] == 3 and r.value["min"] == 28


def test_hydration_no_entries_is_not_zero():
    r = c.hydration_day_total([], "2026-10-09")
    assert r.status == "insufficient_data" and r.value is None


def test_local_today_uses_user_day_not_utc():
    t = datetime(2026, 10, 8, 22, 7, tzinfo=timezone.utc)       # 03:37 on 9 Oct in India
    assert c.local_today(330, t).isoformat() == "2026-10-09"
    assert c.local_today(0, t).isoformat() == "2026-10-08"
    assert c.local_today(99999, t).isoformat() in ("2026-10-09", "2026-10-10")  # offset is clamped


def test_every_formula_is_registered_and_versioned():
    for k, v in c.FORMULAS.items():
        assert v["version"] and v["source"] and v["unit"], k

