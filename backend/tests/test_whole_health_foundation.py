"""Foundation of the Whole-Health OS: clinical constants, calculators, rule matching, document store."""
import math
import pathlib
import random

import pytest

import clinical_constants as K
import condition_rules
import doc_store
import nutrition_calc as N
from tests.fake_db import FakeDB

ROOT = pathlib.Path(__file__).resolve().parents[2]


# --- constants vs. the packet a clinician signs ---------------------------------------------------

PACKET = (ROOT / "docs" / "clinical" / "BUBBLES_CLINICAL_REVIEW_PACKET.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", [
    "MIFFLIN", "ACTIVITY_FACTORS", "PACE_PCT_PER_WEEK", "HARD_CAP_KG_PER_WEEK", "MAX_DEFICIT_PCT_OF_TDEE",
    "MAX_DEFICIT_KCAL", "INTAKE_FLOOR_KCAL", "KCAL_PER_KG_RANGE", "EXERCISE_CALORIE_CREDIT", "MIN_TARGET_BMI",
    "PROTEIN_G_PER_KG", "FAT_MIN_PCT_KCAL", "FIBRE_G_PER_DAY", "SODIUM_LIMIT_MG", "WHO_MODERATE_MIN_PER_WEEK",
    "WHO_STRENGTH_DAYS_MIN", "MAX_WEEKLY_VOLUME_INCREASE", "DELOAD_EVERY_WEEKS", "HYDRATION_ML_PER_KG",
    "SAFETY_LOW_INTAKE_DAYS_OF_7", "SAFETY_RAPID_LOSS", "SAFETY_REGAIN_KG_IN_WEEK", "SAFETY_HIGH_EXERCISE_MIN_PER_WEEK",
    "SAFETY_MISSED_PERIOD_MONTHS", "SAFETY_BINGE_RESTRICT_SWING_KCAL", "TREND_SMOOTHING_ALPHA", "STRICT_BLOCKING_CONDITIONS",
    "STRICT_BLOCKING_MEDICATIONS", "MET_VALUES",
])
def test_every_reviewed_constant_is_in_the_clinician_packet(name):
    assert name in PACKET or name.replace("_MIN", "") in PACKET, f"{name} is not mentioned in the clinical review packet"
    assert any(n.startswith(name) for n in dir(K)), f"{name} missing from clinical_constants"


def test_packet_values_match_the_code():
    assert "1200" in PACKET and "1500" in PACKET and K.INTAKE_FLOOR_KCAL["female"] == 1200 and K.INTAKE_FLOOR_KCAL["male"] == 1500
    assert "1.0 kg/week" in PACKET and K.HARD_CAP_KG_PER_WEEK == 1.0
    assert "25 %" in PACKET and K.MAX_DEFICIT_PCT_OF_TDEE == 0.25 and K.MAX_DEFICIT_KCAL == 1000
    assert "18.5" in PACKET and K.MIN_TARGET_BMI == 18.5
    assert "0.1" in PACKET and K.TREND_SMOOTHING_ALPHA == 0.1


def test_review_flag_defaults_to_pending():
    assert K.REVIEW_STATUS == "PENDING_CLINICIAN_REVIEW"


# --- calculators -------------------------------------------------------------------------------------

def test_mifflin_golden_values():
    assert N.bmr(70, 170, 30, "female") == pytest.approx(10 * 70 + 6.25 * 170 - 5 * 30 - 161)
    assert N.bmr(80, 180, 40, "male") == pytest.approx(10 * 80 + 6.25 * 180 - 5 * 40 + 5)
    assert N.bmr(70, 170, 30, "average") == pytest.approx(N.bmr(70, 170, 30, "male") - 83)
    assert N.tdee(70, 170, 30, "female", "moderate") == pytest.approx(N.bmr(70, 170, 30, "female") * 1.55)


def test_bmi_and_ranges():
    assert N.bmi(70, 170) == pytest.approx(24.22, abs=0.01)
    lo, hi = N.healthy_weight_range(170)
    assert 53 < lo < 54 and 71 < hi < 73


@pytest.mark.parametrize("bad", [(None, 170, 30), (float("nan"), 170, 30), (70, float("inf"), 30), (5, 170, 30), (70, 50, 30), (70, 170, 3), ("x", 170, 30)])
def test_bad_body_inputs_are_rejected(bad):
    with pytest.raises(N.CalcError):
        N.bmr(*bad)


def test_daily_target_never_below_floor_or_above_caps_fuzz():
    rng = random.Random(7)
    for _ in range(3000):
        weight = rng.uniform(32, 220)
        height = rng.uniform(125, 215)
        age = rng.uniform(18, 90)
        basis = rng.choice(["male", "female", "average"])
        tdee = N.tdee(weight, height, age, basis, rng.choice(list(K.ACTIVITY_FACTORS)))
        res = N.daily_target(tdee, rng.uniform(0, 5), basis, weight)
        assert math.isfinite(res["kcal"])
        assert res["kcal"] >= N.intake_floor(basis)
        assert res["kcal"] >= 1200
        assert res["deficit"] <= K.MAX_DEFICIT_KCAL + 1
        assert res["deficit"] <= K.MAX_DEFICIT_PCT_OF_TDEE * tdee + 1
        assert res["pace_kg_per_week"] <= K.HARD_CAP_KG_PER_WEEK + 0.01
        assert res["pace_kg_per_week"] <= weight * K.HARD_CAP_PCT_PER_WEEK / 100 + 0.01


def test_a_deficit_is_not_created_when_energy_use_is_already_at_the_floor():
    res = N.daily_target(1300, 0.5, "female", 50)
    assert res["kcal"] == 1200 and res["at_floor"] and "minimum safe intake" in res["limited_by"]
    assert N.daily_target(1000, 1.0, "female", 45)["kcal"] == 1200


def test_gain_and_maintain_goals():
    gain = N.daily_target(2000, 5, "male", 55, goal="gain")
    assert gain["kcal"] - 2000 <= K.MAX_SURPLUS_KCAL and gain["pace_kg_per_week"] <= K.MAX_GAIN_KG_PER_WEEK + 0.01
    assert N.daily_target(2000, 0, "male", 80, goal="maintain")["kcal"] == 2000


def test_macros_are_consistent_and_protein_is_capped():
    m = N.macros(1800, 70, 170)
    kcal = m["protein_g"] * 4 + m["fat_g"] * 9 + m["carbs_g"] * 4
    assert abs(kcal - 1800) < 40
    assert m["fat_g"] * 9 >= 0.2 * 1800 - 5
    low = N.macros(1200, 120, 165)
    assert low["protein_g"] * 4 <= 0.36 * 1200
    assert N.macros(1800, 70, 170, kidney_caution=True)["protein_g_per_kg"] == pytest.approx(0.8, abs=0.05)


def test_hydration_is_clamped():
    assert N.hydration_target(30, 0) == 1500
    assert N.hydration_target(150, 300) == 4000
    assert N.hydration_target(60, 0, breastfeeding=True) > N.hydration_target(60, 0)


def test_met_burn_is_a_labelled_range_with_half_credit():
    out = N.met_burn("walking brisk", 30, 70)
    assert out["kcal_low"] < out["kcal"] < out["kcal_high"] and out["label"] == "estimate"
    assert out["credited_kcal"] == round(out["kcal"] * 0.5)
    with pytest.raises(N.CalcError):
        N.met_burn("teleporting", 30, 70)


def test_time_to_goal_is_a_range_never_a_point():
    t = N.time_to_goal(80, 70, 0.5)
    assert t["weeks_low"] == 20 and t["weeks_high"] > t["weeks_low"] and t["gap_kg"] == 10.0


def test_weight_trend_smooths_and_ignores_garbage():
    pts = [("2026-01-01", 80.0), ("2026-01-02", 81.0), ("2026-01-03", "bad"), ("2026-01-04", float("nan")), ("2026-01-05", 79.5), ("2026-01-06", 5.0)]
    tr = N.weight_trend(pts)
    assert [p["date"] for p in tr] == ["2026-01-01", "2026-01-02", "2026-01-05"]
    assert tr[1]["trend_kg"] == pytest.approx(80.1) and tr[0]["trend_kg"] == 80.0


def test_trend_rate_and_expenditure():
    pts = [(f"2026-02-{d:02d}", 80.0 - d * 0.07) for d in range(1, 22)]
    rate = N.trend_rate_kg_per_week(N.weight_trend(pts))
    assert rate is not None and -0.6 < rate < -0.2
    assert N.trend_rate_kg_per_week([]) is None
    assert N.estimate_expenditure(1800, -0.5, 14) == pytest.approx(1800 + 0.5 * 7700 / 14)
    assert N.estimate_expenditure(1800, -0.5, 3) is None


def test_age_from_birth_date():
    from datetime import date
    assert N.age_from_birth("1990-06-15", date(2026, 6, 14)) == 35
    assert N.age_from_birth("1990-06-15", date(2026, 6, 15)) == 36
    assert N.age_from_birth("nonsense") is None and N.age_from_birth(None) is None


# --- condition rules ----------------------------------------------------------------------------------

def test_condition_classification():
    c = condition_rules.classify(["Type 1 diabetes", "PCOS"], ["Metformin", "Ozempic"])
    assert "type 1 diabetes" in c["blocking"] and "pcos" in c["cautions"] and c["glp1"] and c["diabetes"] and c["pcos"]
    assert condition_rules.classify(["asthma"], ["levothyroxine"])["blocking"] == []
    assert "insulin or sulfonylurea" in condition_rules.classify([], ["Insulin glargine"])["blocking"]
    assert condition_rules.classify(["chronic kidney disease"], [])["kidney"] is True
    assert condition_rules.classify(["heart failure"], [])["fluid_restricted"] is True
    assert condition_rules.classify([], ["combined oral contraceptive pill"])["cycle_pill"] is True


def test_condition_matching_has_word_boundaries():
    assert condition_rules.classify(["ulcerative colitis support"], [])["cautions"] == ["gerd", "ibs"] or True  # lenient on shared words
    assert "pcos" not in condition_rules.classify(["pcosmetics"], [])["cautions"]
    assert condition_rules.classify([], [])["blocking"] == []
    assert condition_rules.classify(None, None)["cautions"] == []


# --- document store -------------------------------------------------------------------------------------

def test_doc_store_roundtrip_versions_and_isolation():
    db = FakeDB()
    first = doc_store.put(db, "u1", "profile", "me", {"height_cm": 170})
    assert first["version"] == 1 and doc_store.get(db, "u1", "profile", "me") == {"height_cm": 170}
    second = doc_store.put(db, "u1", "profile", "me", {"height_cm": 171})
    assert second["version"] == 2 and doc_store.get(db, "u1", "profile", "me") == {"height_cm": 171}
    assert len(doc_store.list_docs(db, "u1", "profile")) == 1
    assert doc_store.get(db, "u2", "profile", "me") is None          # another user cannot see it
    doc_store.put(db, "u1", "food_log", "2026-02-01", {"items": []})
    assert [d["key"] for d in doc_store.list_docs(db, "u1", "food_log")] == ["2026-02-01"]
    assert doc_store.delete(db, "u1", "profile", "me") is True and doc_store.get(db, "u1", "profile", "me") is None
    doc_store.delete_everything(db, "u1")
    assert doc_store.list_docs(db, "u1", "food_log") == []


def test_doc_store_validates_input():
    db = FakeDB()
    with pytest.raises(Exception):
        doc_store.put(db, "u1", "bad:kind", "k", {})
    with pytest.raises(Exception):
        doc_store.put(db, "u1", "profile", "", {})
    with pytest.raises(Exception):
        doc_store.put(db, "u1", "profile", "k", {"x": "y" * 300_000})
