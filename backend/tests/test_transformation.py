"""Strict Transformation mode: exclusion matrix, plan creation, weekly check-in, safety monitors, lifecycle."""
from datetime import date, timedelta

import pytest

import clinical_constants as K
import transformation as T

TODAY = date(2026, 3, 1)
PROFILE = dict(age=32, height_cm=165, weight_kg=80, target_weight_kg=68, formula_basis="female", activity_level="light",
               conditions=[], medications=[], allergies=[], diet_style="vegetarian")
SCOFF_OK = [False] * 5


def screen(profile=None, scoff=SCOFF_OK, **kw):
    return T.screen({**PROFILE, **(profile or {})}, scoff, today=TODAY, **kw)


def codes(result):
    return {e["code"] for e in result["exclusions"]}


def test_healthy_adult_is_allowed():
    r = screen()
    assert r["decision"] == "allowed" and r["exclusions"] == [] and r["alternative"] is None


EXCLUSION_MATRIX = [
    ("under_18", dict(profile=dict(age=16))),
    ("pregnancy", dict(profile=dict(pregnant=True))),
    ("pregnancy", dict(profile=dict(breastfeeding=True))),
    ("pregnancy", dict(profile=dict(trying_to_conceive=True))),
    ("pregnancy", dict(profile=dict(conditions=["pregnancy"]))),
    ("eating_concern", dict(scoff=[True, True, False, False, False])),
    ("eating_concern", dict(profile=dict(conditions=["anorexia"]))),
    ("eating_concern", dict(profile=dict(eating_disorder_history=True))),
    ("scoff_missing", dict(scoff=None)),
    ("target_low", dict(profile=dict(target_weight_kg=48))),
    ("not_loss", dict(profile=dict(target_weight_kg=80))),
    ("underweight", dict(profile=dict(weight_kg=48, target_weight_kg=46))),
    ("missed_periods", dict(months_since_period=4)),
    ("recent_red_flag", dict(red_flag_days_ago=3)),
    ("age_70", dict(profile=dict(age=72))),
    ("surgery_injury", dict(recent_surgery_or_injury=True)),
    ("condition:type_1_diabetes", dict(profile=dict(conditions=["Type 1 diabetes"]))),
    ("condition:insulin_or_sulfonylurea", dict(profile=dict(medications=["Insulin glargine"]))),
    ("condition:insulin_or_sulfonylurea", dict(profile=dict(medications=["glimepiride"]))),
    ("condition:kidney_disease", dict(profile=dict(conditions=["chronic kidney disease"]))),
    ("condition:heart_disease", dict(profile=dict(conditions=["heart failure"]))),
    ("condition:uncontrolled_hypertension", dict(profile=dict(conditions=["uncontrolled hypertension"]))),
    ("condition:liver_disease", dict(profile=dict(conditions=["cirrhosis"]))),
    ("condition:cancer_treatment", dict(profile=dict(conditions=["chemotherapy"]))),
    ("condition:anticoagulant_(diet_vitamin_k_changes)", dict(profile=dict(medications=["Warfarin"]))),
    ("condition:lithium", dict(profile=dict(medications=["Lithium"]))),
]


@pytest.mark.parametrize("code,kwargs", EXCLUSION_MATRIX)
def test_exclusion_matrix(code, kwargs):
    r = screen(**kwargs)
    assert r["decision"] in ("refused", "incomplete"), r
    assert code in codes(r), (code, codes(r))
    assert r["message"]


def test_refusals_are_kind_and_offer_something():
    for kwargs in [dict(profile=dict(age=16)), dict(scoff=[True, True, True, False, False]), dict(profile=dict(conditions=["heart failure"]))]:
        r = screen(**kwargs)
        text = " ".join(e["message"] for e in r["exclusions"]).lower()
        assert not any(w in text for w in ("fat", "lazy", "failure", "disgust", "guilt")) or "heart failure" in text.replace("heart failure", "heart failure")
        assert "doctor" in text or "bubbles" in text or "dietitian" in text
    assert screen(scoff=[True, True, False, False, False])["alternative"] == "support"
    assert screen(profile=dict(conditions=["heart failure"]))["alternative"] == "clinician"


def test_clearance_unlocks_clearable_exclusions_only_while_valid():
    cleared = {"cleared": True, "date": "2026-01-10", "areas": ["heart disease", "uncontrolled hypertension"]}
    assert screen(profile=dict(conditions=["coronary artery disease"], clinician_clearance=cleared))["decision"] != "refused"
    stale = {**cleared, "date": "2024-01-10"}
    assert "condition:heart_disease" in codes(screen(profile=dict(conditions=["coronary artery disease"], clinician_clearance=stale)))
    # clearance for one area never unlocks a different one, and never unlocks non-clearable exclusions
    assert "condition:kidney_disease" in codes(screen(profile=dict(conditions=["ckd"], clinician_clearance=cleared)))
    assert "pregnancy" in codes(screen(profile=dict(pregnant=True, clinician_clearance={"cleared": True, "date": "2026-02-01"})))
    assert "eating_concern" in codes(screen(scoff=[True, True, True, True, True], profile=dict(clinician_clearance={"cleared": True, "date": "2026-02-01"})))


def test_cautions_do_not_block():
    r = screen(profile=dict(conditions=["PCOS", "hypothyroidism"], medications=["Ozempic"]))
    assert r["decision"] == "allowed_with_cautions" and {"pcos", "thyroid condition", "GLP-1 medicine"} <= set(r["cautions"])


def test_incomplete_profile_is_not_a_crash():
    r = T.screen({"age": 30}, SCOFF_OK, today=TODAY)
    assert r["decision"] == "incomplete"


# --- plan creation ------------------------------------------------------------------------------------

def test_make_plan_requires_allowed_screening_and_acknowledgement():
    s = screen()
    with pytest.raises(ValueError, match="accept"):
        T.make_plan(PROFILE, {}, s, False, TODAY)
    with pytest.raises(ValueError, match="not available"):
        T.make_plan(PROFILE, {}, screen(profile=dict(age=16)), True, TODAY)
    plan = T.make_plan(PROFILE, {"foods": ["rajma"], "diet_style": "vegetarian"}, s, True, TODAY)
    t = plan["targets"]
    assert plan["status"] == "active" and plan["constants_status"] == K.REVIEW_STATUS and plan["acknowledged_at"]
    assert t["kcal"] >= t["floor_kcal"] and t["pace_kg_per_week"] <= K.HARD_CAP_KG_PER_WEEK and plan["history"][0]["event"] == "started"


def test_preview_syncs_diet_exercise_and_targets():
    pv = T.preview(PROFILE, {"foods": ["rajma", "paneer"], "equipment": "home", "level": 2, "days_per_week": 4,
                             "exercise_screen": {"mode": "full", "message": "", "cleared": True}})
    t = pv["targets"]
    assert all(t["kcal"] <= d["totals"]["kcal"] <= t["kcal"] * 1.06 for d in pv["diet"]["days"])
    assert pv["exercise"]["ok"] and len(pv["exercise"]["sessions"]) == 4
    assert any("kcal" in line for line in pv["good_day"]) and any("off-plan" in line for line in pv["good_day"])
    text = " ".join(pv["commit_text"])
    assert "not medical advice" in text and "chest pain" in text and str(round(t["floor_kcal"])) in text


def test_commit_and_good_day_copy_never_shames_or_gives_drug_advice():
    pv = T.preview(PROFILE, {})
    blob = " ".join(pv["commit_text"] + pv["good_day"]).lower()
    for word in ("lazy", "fat ", "cheat", "guilt", "sinful", "supplement", "dose", "prescri"):
        assert word not in blob


# --- today ----------------------------------------------------------------------------------------------

def test_today_view_is_neutral_when_over():
    plan = T.make_plan(PROFILE, {}, screen(), True, TODAY)
    v = T.today_view(plan, {"kcal": plan["targets"]["kcal"] + 300, "protein_g": 50}, 1000, 200, 5000)
    assert v["budget"]["over"] and "okay" in v["message"] and "!" not in v["message"] and v["budget"]["exercise_credit_kcal"] == 100


# --- safety monitors ----------------------------------------------------------------------------------------

def days(values, start=TODAY - timedelta(days=6)):
    return [{"date": (start + timedelta(days=i)).isoformat(), "kcal": v} for i, v in enumerate(values)]


@pytest.fixture
def plan():
    return T.make_plan(PROFILE, {}, screen(), True, TODAY)


def test_monitors_quiet_on_a_normal_week(plan):
    assert T.safety_monitors(plan, intake_days=days([1500, 1600, 1550, 1500, 1650, 1600, 1580]), exercise_min_week=200, trend_rate_kg_week=-0.4) == []


@pytest.mark.parametrize("name,kwargs,expected", [
    ("low intake", dict(intake_days=days([1000, 1100, 900, 1500, 1500, 1500, 1500])), "low_intake"),
    ("rapid loss", dict(intake_days=days([1500] * 7), recent_rates=[-1.5, -1.4]), "rapid_loss"),
    ("low energy availability", dict(intake_days=days([1250] * 7), exercise_min_week=500), "low_energy_availability"),
    ("missed periods", dict(intake_days=days([1500] * 7), months_without_period=3), "missed_periods"),
    ("dizzy", dict(intake_days=days([1500] * 7), symptoms={"dizzy": True}), "symptom"),
    ("chest pain", dict(intake_days=days([1500] * 7), symptoms={"chest_pain": True}), "symptom"),
    ("restriction language", dict(intake_days=days([1500] * 7), restriction_codes=["starve"]), "restriction_language"),
])
def test_pause_monitors(plan, name, kwargs, expected):
    out = T.safety_monitors(plan, **kwargs)
    hit = [m for m in out if m["code"] == expected]
    assert hit and hit[0]["action"] == "pause", name
    assert not any(w in hit[0]["message"].lower() for w in ("fail", "lazy", "guilt", "fat "))


def test_check_in_monitors_do_not_pause(plan):
    out = T.safety_monitors(plan, intake_days=days([1500] * 7), week_change_kg=2.5)
    assert [m["action"] for m in out] == ["check_in"] and out[0]["code"] == "regain_spike"
    swings = T.safety_monitors(plan, intake_days=days([2800, 1300, 2700, 1350, 2500, 1500, 2000]))
    assert any(m["code"] == "intake_swings" and m["action"] == "check_in" for m in swings)


@pytest.mark.parametrize("text,expected", [
    ("I want to starve myself until I fit the dress", ["starve"]), ("I made myself throw up after dinner", ["purge"]),
    ("I can't stop thinking about food", ["control"]), ("I binged again last night", ["control"]), ("I'm going to skip all my meals tomorrow", ["skip_all"]),
    ("I had a lovely dinner of dal and rice", []), ("my friend starved in the story", []), ("what's a healthy breakfast?", []),
])
def test_restriction_language(text, expected):
    assert T.restriction_language(text) == expected


@pytest.mark.parametrize("text,value", [("I want to eat 800 calories a day", 800), ("my diet target is 900 kcal", 900), ("I will live on 600 cal", 600),
                                         ("a banana has 105 calories", None), ("I want to eat 1800 calories", None), ("", None)])
def test_below_floor_requests(text, value):
    assert T.below_floor_request(text, 1200) == value


# --- weekly check-in ----------------------------------------------------------------------------------------

def weights(rate_per_week, start=80.0, n=21, noise=0.0, end=TODAY):
    return [((end - timedelta(days=n - 1 - i)).isoformat(), start + rate_per_week * i / 7.0 + (noise if i % 2 else -noise)) for i in range(n)]


def intake(kcal, n=14, end=TODAY):
    return [{"date": (end - timedelta(days=n - 1 - i)).isoformat(), "kcal": kcal} for i in range(n)]


def test_not_enough_data_changes_nothing(plan):
    r = T.weekly_checkin(plan, weights(-0.5, n=2), intake(1500, 2), today=TODAY)
    assert r["decision"] == "insufficient_data" and r["change_kcal"] == 0 and r["new_kcal"] == plan["targets"]["kcal"]


def test_on_track_week_continues(plan):
    pace = plan["targets"]["pace_kg_per_week"]
    r = T.weekly_checkin(plan, weights(-pace), intake(plan["targets"]["kcal"]), today=TODAY)
    assert r["decision"] in ("continue", "adjust") and abs(r["change_kcal"]) <= K.MAX_WEEKLY_CALORIE_CHANGE
    assert r["new_kcal"] >= plan["targets"]["floor_kcal"] and r["reasoning"]


def test_slow_progress_lowers_calories_within_the_weekly_cap(plan):
    r = T.weekly_checkin(plan, weights(-0.05), intake(plan["targets"]["kcal"]), today=TODAY)
    assert r["decision"] == "adjust" and -K.MAX_WEEKLY_CALORIE_CHANGE <= r["change_kcal"] < 0 and r["new_kcal"] >= plan["targets"]["floor_kcal"]


def test_calorie_target_never_goes_below_floor_even_when_progress_stalls():
    p = T.make_plan({**PROFILE, "weight_kg": 58, "target_weight_kg": 52, "age": 50, "height_cm": 155, "activity_level": "sedentary"}, {},
                    T.screen({**PROFILE, "weight_kg": 58, "target_weight_kg": 52, "age": 50, "height_cm": 155}, SCOFF_OK, today=TODAY), True, TODAY)
    kcal = p["targets"]["kcal"]
    for _ in range(10):
        r = T.weekly_checkin(p, weights(0.0, start=58), intake(kcal), today=TODAY)
        assert r["new_kcal"] is None or r["new_kcal"] >= p["targets"]["floor_kcal"]
        if r["new_kcal"]:
            p["targets"] = {**p["targets"], "kcal": r["new_kcal"]}


def test_losing_too_fast_never_cuts_further(plan):
    r = T.weekly_checkin(plan, weights(-1.3), intake(plan["targets"]["kcal"]), today=TODAY, past_weekly_rates=[-1.4])
    assert r["decision"] == "pause" or r["change_kcal"] >= 0


def test_unsafe_week_pauses_with_kind_wording(plan):
    r = T.weekly_checkin(plan, weights(-0.4), intake(1000), today=TODAY)
    assert r["decision"] == "pause" and r["new_kcal"] is None and "clinician" in r["next_step"]
    r2 = T.weekly_checkin(plan, weights(-0.4), intake(1500), today=TODAY, restriction_codes=["purge"])
    assert r2["decision"] == "pause"


def test_luteal_water_retention_is_not_treated_as_failure(plan):
    r = T.weekly_checkin(plan, weights(+0.2), intake(plan["targets"]["kcal"]), today=TODAY, in_luteal_or_period=True)
    assert r["decision"] == "continue" and r["change_kcal"] == 0 and any("water" in m for m in r["messages"])


def test_plateau_offers_options_not_a_crash_diet(plan):
    r = T.weekly_checkin(plan, weights(0.0), intake(plan["targets"]["kcal"]), today=TODAY, past_weekly_rates=[0.02, -0.03, 0.01])
    assert r["plateau"] and any("break" in o for o in r["options"]) and r["new_kcal"] >= plan["targets"]["floor_kcal"]


def test_diet_break_suggested_after_twelve_weeks(plan):
    plan = {**plan, "weeks_on_plan": 13}
    r = T.weekly_checkin(plan, weights(-0.4), intake(plan["targets"]["kcal"]), today=TODAY)
    assert any("12 weeks" in o for o in r["options"])


# --- lifecycle ------------------------------------------------------------------------------------------------

def test_pause_resume_and_safety_cooldown(plan):
    paused = T.pause(plan, "illness")
    assert paused["status"] == "paused" and T.can_resume(paused, TODAY)[0]
    safe = T.pause(plan, "low intake", safety=True)
    safe["paused"]["since"] = TODAY.isoformat()
    ok, why = T.can_resume(safe, TODAY + timedelta(days=2))
    assert not ok and "wait" in why
    assert T.can_resume(safe, TODAY + timedelta(days=8))[0]
    with pytest.raises(ValueError):
        T.resume(safe, screen(), TODAY + timedelta(days=2))
    resumed = T.resume(safe, screen(), TODAY + timedelta(days=8))
    assert resumed["status"] == "active" and resumed["paused"] is None and resumed["history"][-1]["event"] == "resumed"
    with pytest.raises(ValueError):
        T.resume(T.pause(plan), screen(profile=dict(age=15)), TODAY)


def test_edit_goal_rechecks_the_bmi_floor(plan):
    new = T.edit_goal(PROFILE, plan, 70, screen())
    assert new["target_weight_kg"] == 70 and new["version"] == 2 and new["history"][-1]["event"] == "goal_changed"
    with pytest.raises(Exception):
        T.edit_goal(PROFILE, plan, 40, screen())


def test_finish_returns_to_maintenance_gradually(plan):
    done = T.finish(plan, 68.2, 2000)
    sched = done["maintenance"]
    assert done["status"] == "completed" and sched and sched[-1]["kcal"] == 2000
    assert all(b["kcal"] - a["kcal"] <= K.MAINTENANCE_RETURN_KCAL_PER_WEEK for a, b in zip(sched, sched[1:]))


def test_progress_report_is_facts_only(plan):
    rep = T.progress_report(plan, weights(-0.4), intake(1600))
    assert rep["days_logged"] == 14 and rep["avg_logged_kcal"] == 1600 and "diagnosis" in rep["note"]
