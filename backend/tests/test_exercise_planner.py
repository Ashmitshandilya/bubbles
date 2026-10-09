"""Exercise library integrity, screening, condition-aware planning, progression and adaptation."""
import pytest

import clinical_constants as K
import exercise_planner as E
from exercise_library import LIB

PROF = dict(weight_kg=70, height_cm=168, age=32)
ALL_NO = {k: False for k, _q in K.PARQ_QUESTIONS}
OK = E.screen(ALL_NO)


def moves(plan):
    return [LIB[m["id"]] for s in plan["sessions"] for part in ("warmup", "main", "cooldown") for m in s.get(part, []) if m["id"] in LIB]


def plan(**kw):
    args = dict(profile=PROF, days_per_week=4, minutes=40, equipment="home", level=2, week_index=1, screen_result=OK)
    args.update(kw)
    return E.plan_week(**args)


def test_library_is_consistent():
    assert len(LIB) >= 150
    for m in LIB.values():
        assert m["cue"] and m["level"] in (1, 2, 3) and m["impact"] in (0, 1, 2)
        assert m["met"] in K.MET_VALUES, m["id"]
    assert {m["pattern"] for m in LIB.values()} >= {"squat", "hinge", "push", "pull", "core", "cardio", "mobility", "lunge"}


def test_screen_blocks_on_heart_and_chest_questions_until_cleared():
    r = E.screen({**ALL_NO, "chest": True})
    assert r["mode"] == "clinician_first" and "doctor" in r["message"] and not r["cleared"]
    assert E.screen({**ALL_NO, "chest": True}, clinician_cleared=True)["mode"] == "full"
    assert E.screen({**ALL_NO, "bone_joint": True})["adapt"] == ["bone_joint"]
    assert E.screen({**ALL_NO, "pregnant": True})["mode"] == "pregnancy"
    inc = E.screen({"heart": False})
    assert inc["mode"] == "incomplete" and inc["unanswered"]
    assert E.plan_week(PROF, screen_result=inc)["ok"] is False


def test_clinician_first_plans_only_walking_and_mobility():
    p = plan(screen_result=E.screen({**ALL_NO, "dizzy": True}))
    assert p["mode"] == "clinician_first" and p["notes"]
    for m in moves(p):
        assert m["category"] == "mobility" or m["id"] in ("walk-slow", "walk-brisk", "march", "chair-cardio")


def test_pregnancy_plan_excludes_risky_moves():
    p = plan(profile={**PROF, "pregnant": True}, screen_result=E.screen({**ALL_NO, "pregnant": True}))
    for m in moves(p):
        assert "pregnancy" not in m["avoid"] and m["impact"] < 2
    assert any("midwife" in n for n in p["notes"])


def test_high_bmi_and_joint_issues_get_low_impact():
    p = plan(profile={**PROF, "weight_kg": 105}, level=3, equipment="gym")
    assert all(m["impact"] < 2 for m in moves(p)) and "high_impact" in p["flags"]
    q = plan(profile={**PROF, "conditions": ["osteoarthritis"]}, level=3)
    assert all(m["impact"] < 2 for m in moves(q))


def test_condition_specific_avoidance():
    assert not any("hypertension" in m["avoid"] for m in moves(plan(profile={**PROF, "conditions": ["high blood pressure"]}, level=3)))
    assert not any("osteoporosis" in m["avoid"] for m in moves(plan(profile={**PROF, "conditions": ["osteoporosis"]}, level=3)))
    assert not any("knee" in m["avoid"] for m in moves(plan(injuries=["knee"], level=3)))
    assert not any("lower_back" in m["avoid"] for m in moves(plan(injuries=["back"], level=3)))


def test_older_adults_get_balance_work_and_no_high_impact():
    p = plan(profile={**PROF, "age": 66}, level=2)
    assert all(m["impact"] < 2 for m in moves(p)) and any("Balance" in n for n in p["notes"])


def test_equipment_is_respected():
    none = moves(plan(equipment="none", level=3))
    assert all(set(m["equipment"]) <= {"none", "mat", "chair", "step"} for m in none)
    gym = moves(plan(equipment="gym", level=3))
    assert any("gym" in m["equipment"] or "dumbbell" in m["equipment"] for m in gym)


def test_who_structure_over_a_typical_week():
    p = plan(days_per_week=5, minutes=45, current_active_min_per_week=160)
    assert p["summary"]["strength_days"] >= 2 and p["summary"]["cardio_minutes"] > 0
    assert len(p["sessions"]) == 5 and len(set(s["day"] for s in p["sessions"])) == 5
    for s in p["sessions"]:
        if s["type"] != "mobility":
            assert s["warmup"] and s["cooldown"]


def test_progression_never_jumps_more_than_ten_percent_between_build_weeks():
    prev = None
    for w in range(1, 25):
        p = plan(week_index=w)
        vol = E.weekly_volume(p)
        if p["deload"]:
            assert vol["strength"] < prev["strength"]
            continue
        if prev:
            assert vol["strength"] <= prev["strength"] * 1.11, (w, vol, prev)
            assert vol["cardio"] <= prev["cardio"] * 1.11 + 2, (w, vol, prev)
        prev = vol


def test_deload_every_fifth_week_and_cardio_caps_at_who_ceiling():
    flags = [plan(week_index=w)["deload"] for w in range(1, 11)]
    assert flags == [False] * 4 + [True] + [False] * 4 + [True]
    assert plan(week_index=80, current_active_min_per_week=200)["summary"]["cardio_minutes"] <= 300


def test_adapt_session_stops_for_red_flags_and_removes_painful_moves():
    base = plan(level=3, equipment="gym")["sessions"][0]
    stop = E.adapt_session(base, {"chest_pain": True})
    assert stop["stop"] and stop["session"]["main"] == [] and "medical help" in stop["messages"][0]
    assert E.adapt_session(base, {"pain": True, "pain_severity": 8})["stop"]
    hurt = E.adapt_session(base, {"pain": True, "pain_area": "shoulder", "pain_severity": 3})
    assert not any("shoulder" in LIB[m["id"]]["avoid"] for m in hurt["session"]["main"]) and not hurt["stop"]
    tired = E.adapt_session(base, {"low_energy": True, "poor_sleep": True})
    assert tired["session"]["main"][0]["sets"] <= base["main"][0]["sets"] and len(tired["messages"]) == 2
    assert E.adapt_session(base, {"rpe_avg": 9, "completed_pct": 100})["next_step"] == "regress"
    assert E.adapt_session(base, {"rpe_avg": 3, "completed_pct": 95})["next_step"] == "progress"
    assert any("period" in m for m in E.adapt_session(base, {"heavy_period": True})["messages"])


def test_time_box_shortens_without_dropping_to_nothing():
    base = plan(level=2)["sessions"][0]
    short = E.time_box(base, 20)
    assert 2 <= len(short["main"]) < len(base["main"]) and short["minutes"] == 20 and all(m["sets"] <= 2 for m in short["main"])
    cardio = E.time_box(plan()["sessions"][1], 15)
    assert cardio["main"][0]["minutes"] >= 5


@pytest.mark.parametrize("bad", [dict(weight_kg=None), dict(height_cm=10), dict(age=3)])
def test_bad_body_inputs_raise_calc_error(bad):
    import nutrition_calc
    with pytest.raises(nutrition_calc.CalcError):
        E.plan_week({**PROF, **bad}, screen_result=OK)
