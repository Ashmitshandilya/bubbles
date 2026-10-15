"""organ_map_engine: every organ rule with no data, normal, edge and urgent cases, plus the shared contract."""
from __future__ import annotations

import itertools
import json
from datetime import date, timedelta

import pytest

import clinical_constants as K
import organ_map_engine as E

TODAY = date(2026, 10, 15)
_ids = itertools.count(1)


def ev(event_type: str, data: dict, ago: int = 1, source: str = "tracker", status: str = "confirmed", **prov) -> dict:
    day = (TODAY - timedelta(days=ago)).isoformat()
    return {"id": f"ev-{next(_ids)}", "event_type": event_type, "extraction_status": status, "created_at": f"{day}T09:00:00+00:00",
            "extracted_data": {**data, "date": day, "_prov": {"source": source, **prov}}}


def symptom(name: str, ago: int = 1, **extra) -> dict:
    return ev("symptom", {"symptom": name, "name": name, **extra}, ago, source="user_message")


def bp(sys_bp: int, dia_bp: int, ago: int = 1) -> dict:
    return ev("vital_sign", {"systolic_bp": sys_bp, "diastolic_bp": dia_bp}, ago)


def run(events=(), labs=(), conditions=(), cycle=None, window=30) -> dict:
    result = E.build_organ_map(list(events), labs=labs, conditions=conditions, cycle=cycle, today=TODAY, window_days=window)
    json.dumps(result)  # the API returns it as is
    return {o["organ_id"]: o for o in result["organs"]}


def organ(organ_id: str, events=(), labs=(), conditions=(), cycle=None, window=30) -> dict:
    """One organ's assessment, opt-in organs included (the map itself may leave those out)."""
    obs = E.observations(list(events), labs, conditions, today=TODAY, window_days=window)
    result = E.assess_organ(organ_id, obs, today=TODAY, window_days=window, cycle=cycle)
    json.dumps(result)
    return result


ALWAYS = [o for o in E.ORGANS if o not in E.OPT_IN_ORGANS]


# ---- shared contract ------------------------------------------------------------------------------------------------

def test_every_organ_is_present_in_a_fixed_order_with_the_full_shape():
    result = E.build_organ_map([], today=TODAY)
    assert [o["organ_id"] for o in result["organs"]] == ALWAYS
    assert result["not_a_diagnosis"] is True and result["window_days"] == K.ORGAN_WINDOW_DEFAULT_DAYS
    for o in result["organs"]:
        assert list(o)[0] == "safety"  # safety guidance always comes first
        assert {"organ_id", "name", "status", "summary", "reasons", "evidence", "evidence_count", "confidence", "missing", "notes",
                "next_step", "not_a_diagnosis", "updated_at", "chat_prompt"} <= set(o)
        assert o["not_a_diagnosis"] is True and o["status"] in E.STATUSES


@pytest.mark.parametrize("organ_id", list(E.ORGANS))
def test_no_data_is_a_gap_never_steady(organ_id):
    o = organ(organ_id)
    assert o["status"] == "no_data" and o["evidence"] == [] and o["updated_at"] is None and o["safety"] is None
    assert o["confidence"]["level"] == "low" and o["confidence"]["reason"]
    assert "gap" in o["summary"] and "all is well" in o["summary"]
    assert o["missing"], "a gap must say what would fill it"
    assert o["next_step"]


def test_user_copy_never_diagnoses_and_has_no_em_dashes():
    events = [bp(185, 125), symptom("chest pain"), symptom("thoughts of suicide"), symptom("blood in urine")]
    for o in run(events, labs=[{"id": "l", "date": "2026-10-01", "test_name": "TSH", "value": 12}]).values():
        copy = " ".join([o["summary"], o["next_step"], *o["reasons"], *o["notes"], (o["safety"] or {}).get("message") or ""])
        assert "diagnos" not in copy.lower() and "—" not in copy
        assert "you have a" not in copy.lower() and "healthy" not in copy.lower()


def test_chat_prompt_carries_the_same_evidence():
    o = organ("heart", [bp(150, 95), bp(120, 80, ago=2)])
    assert o["chat_prompt"]["text"] == "Explain my heart" and o["chat_prompt"]["evidence"] == o["evidence"]
    assert organ("stomach_intestines")["chat_prompt"]["text"] == "Explain my stomach and intestines"


def test_evidence_items_are_exact():
    o = organ("heart", [bp(150, 95, ago=3)])
    item = o["evidence"][0]
    assert item["date"] == (TODAY - timedelta(days=3)).isoformat() and item["value"] == "150/95" and item["unit"] == "mmHg"
    assert item["source"] == "tracker" and item["label"] == "Blood pressure" and item["id"].startswith("ev-")
    assert o["updated_at"] == item["date"]


def test_window_is_clamped_and_old_or_future_rows_are_ignored():
    assert E.build_organ_map([], today=TODAY, window_days=1)["window_days"] == K.ORGAN_WINDOW_DAYS[0]
    assert E.build_organ_map([], today=TODAY, window_days=999)["window_days"] == K.ORGAN_WINDOW_DAYS[1]
    assert organ("heart", [bp(120, 80, ago=31)])["status"] == "no_data"
    assert organ("heart", [bp(120, 80, ago=29)])["status"] == "steady"
    assert organ("heart", [bp(120, 80, ago=-3)])["status"] == "no_data"  # dated in the future
    assert organ("heart", [bp(120, 80, ago=60)], window=90)["status"] == "steady"


def test_only_live_positive_first_person_rows_count():
    dead = [ev("vital_sign", {"systolic_bp": 150, "diastolic_bp": 95}, status="rejected"),
            symptom("chest pain", present=False),
            ev("symptom", {"symptom": "chest pain"}, source="user_message", subject="other"),
            ev("symptom", {"symptom": "chest pain"}, source="user_message", assertion="possible"),
            ev("wellness_checkin", {"pertinent_negatives": ["chest pain"]})]
    assert organ("heart", dead)["status"] == "no_data"


def test_tracker_save_and_its_analytics_mirror_count_once():
    one, two = bp(150, 95), bp(150, 95)
    two["extracted_data"]["_prov"]["store"] = "mirror"
    o = organ("heart", [one, two])
    assert o["evidence_count"] == 1


def test_confidence_grows_with_entries_and_kinds():
    assert organ("heart", [bp(120, 80)])["confidence"]["level"] == "low"
    assert organ("heart", [bp(120, 80, ago=i) for i in range(1, 6)])["confidence"]["level"] == "medium"
    many = [bp(120, 80, ago=i) for i in range(1, 9)] + [ev("activity", {"name": "walk", "duration_minutes": 30}, ago=i) for i in range(1, 4)]
    assert organ("heart", many)["confidence"]["level"] == "high"


# ---- heart ----------------------------------------------------------------------------------------------------------

def test_heart_normal_readings_are_steady():
    o = organ("heart", [bp(118, 76, ago=i) for i in (1, 2, 3)] + [ev("vital_sign", {"heart_rate_bpm": 64})])
    assert o["status"] == "steady" and "below 140/90" in " ".join(o["reasons"])


@pytest.mark.parametrize("reading,status", [((139, 89), "steady"), ((140, 80), "worth_watching"), ((120, 90), "worth_watching"),
                                            ((179, 119), "worth_watching"), ((180, 100), "talk_to_doctor"), ((150, 120), "talk_to_doctor"),
                                            ((89, 60), "worth_watching"), ((90, 60), "steady")])
def test_heart_blood_pressure_edges(reading, status):
    assert organ("heart", [bp(*reading)])["status"] == status


def test_heart_repeated_high_readings_mean_talk_to_doctor():
    assert organ("heart", [bp(145, 92, ago=i) for i in (1, 2)])["status"] == "worth_watching"
    o = organ("heart", [bp(145, 92, ago=i) for i in (1, 2, 3)] + [bp(120, 80, ago=4)])
    assert o["status"] == "talk_to_doctor" and "3 of your 4 readings" in o["summary"]


def test_heart_chat_blood_pressure_halves_are_paired():
    sys_e = ev("vital_sign", {"name": "systolic", "value": 152, "unit": "mmHg"}, source="user_message", message_id="m1")
    dia_e = ev("vital_sign", {"name": "diastolic", "value": 96, "unit": "mmHg"}, source="user_message", message_id="m1")
    o = organ("heart", [sys_e, dia_e])
    assert o["evidence"][0]["value"] == "152/96" and o["evidence"][0]["source"] == "chat" and o["status"] == "worth_watching"


@pytest.mark.parametrize("rates,status", [((64, 70, 72), "steady"), ((100, 100, 100), "steady"), ((104, 106, 108), "worth_watching"),
                                          ((45, 48, 47), "worth_watching"), ((125, 130, 128), "talk_to_doctor"), ((70, 72, 130), "worth_watching")])
def test_heart_rate_edges(rates, status):
    assert organ("heart", [ev("vital_sign", {"heart_rate_bpm": r}, ago=i) for i, r in enumerate(rates, 1)])["status"] == status


def test_heart_activity_alone_is_steady_but_says_so():
    o = organ("heart", [ev("activity", {"name": "walk", "duration_minutes": 30})])
    assert o["status"] == "steady" and o["confidence"]["level"] == "low"
    assert any("Only activity" in r for r in o["reasons"]) and "Blood pressure readings (a home cuff, sitting and rested)" in o["missing"]


def test_heart_chest_pain_is_urgent_with_safety_first():
    o = organ("heart", [bp(118, 76, ago=2), symptom("chest pain", ago=1)])
    assert o["status"] == "talk_to_doctor" and list(o)[0] == "safety"
    assert o["safety"]["state"] == "EMERGENCY" and "emergency" in o["safety"]["message"]
    assert o["evidence"][0]["label"] == "Chest pain" and o["confidence"]["level"] == "high"


def test_heart_old_chest_pain_is_watched_not_escalated():
    o = organ("heart", [symptom("chest pain", ago=K.ORGAN_RED_FLAG_LOOKBACK_DAYS + 2)])
    assert o["status"] == "worth_watching" and o["safety"] is None


def test_heart_resolved_chest_pain_is_not_an_emergency():
    o = organ("heart", [symptom("chest pain", details="(resolved)")])
    assert o["safety"] is None and o["status"] == "worth_watching"


def test_heart_palpitations_are_worth_watching():
    assert organ("heart", [symptom("palpitations")])["status"] == "worth_watching"


# ---- lungs ----------------------------------------------------------------------------------------------------------

def test_lungs_activity_without_symptoms_is_steady():
    assert organ("lungs", [ev("exercise", {"name": "run", "minutes": 25})])["status"] == "steady"


@pytest.mark.parametrize("spo2,status", [(98, "steady"), (95, "steady"), (94, "worth_watching"), (93, "worth_watching"), (92, "talk_to_doctor")])
def test_lungs_oxygen_edges(spo2, status):
    assert organ("lungs", [ev("vital_sign", {"name": "spo2", "value": spo2, "unit": "%"}, source="user_message")])["status"] == status


def test_lungs_cough_is_watched_and_a_three_week_cough_means_doctor():
    assert organ("lungs", [symptom("cough", ago=2), symptom("cough", ago=1)])["status"] == "worth_watching"
    assert organ("lungs", [symptom("cough", ago=20), symptom("cough", ago=1)])["status"] == "worth_watching"  # 20-day span
    o = organ("lungs", [symptom("cough", ago=21), symptom("cough", ago=1)])
    assert o["status"] == "talk_to_doctor" and "three weeks" in " ".join(o["reasons"])


def test_lungs_wheeze_free_text_is_recognised():
    assert organ("lungs", [ev("symptom", {"symptom": "Wheezing at night"})])["status"] == "worth_watching"


def test_lungs_breathlessness_is_urgent():
    o = organ("lungs", [symptom("shortness of breath")])
    assert o["status"] == "talk_to_doctor" and o["safety"]["state"] == "EMERGENCY"


# ---- brain ----------------------------------------------------------------------------------------------------------

def sleep(hours: float, ago: int) -> dict:
    return ev("sleep", {"hours": hours}, ago)


def mood(score: int, ago: int) -> dict:
    return ev("mood", {"score": score}, ago)


def test_brain_good_sleep_and_mood_is_steady():
    o = organ("brain", [sleep(7.5, i) for i in (1, 2, 3)] + [mood(7, i) for i in (1, 2, 3)])
    assert o["status"] == "steady"


@pytest.mark.parametrize("hours,nights,status", [(7.0, 3, "steady"), (6.9, 3, "worth_watching"), (5.0, 2, "steady"), (5.0, 3, "worth_watching")])
def test_brain_sleep_edges(hours, nights, status):
    assert organ("brain", [sleep(hours, i) for i in range(1, nights + 1)])["status"] == status


def test_brain_mood_and_stress_averages():
    assert organ("brain", [mood(4, i) for i in (1, 2, 3)])["status"] == "worth_watching"
    assert organ("brain", [mood(5, i) for i in (1, 2, 3)])["status"] == "steady"
    assert organ("brain", [ev("stress", {"severity": 7}, i) for i in (1, 2, 3)])["status"] == "worth_watching"
    assert organ("brain", [ev("stress", {"severity": 6}, i) for i in (1, 2, 3)])["status"] == "steady"


def test_brain_many_low_mood_days_mean_doctor():
    assert organ("brain", [mood(3, i) for i in range(1, 10)])["status"] == "worth_watching"
    assert organ("brain", [mood(3, i) for i in range(1, 11)])["status"] == "talk_to_doctor"


@pytest.mark.parametrize("days,status", [(3, "steady"), (4, "worth_watching"), (14, "worth_watching"), (15, "talk_to_doctor")])
def test_brain_headache_days(days, status):
    assert organ("brain", [symptom("headache", ago=i) for i in range(K.ORGAN_RED_FLAG_LOOKBACK_DAYS + 1, K.ORGAN_RED_FLAG_LOOKBACK_DAYS + 1 + days)])["status"] == status


def test_brain_dizziness_is_watched():
    assert organ("brain", [symptom("dizziness")])["status"] == "worth_watching"


def test_brain_crisis_language_gets_crisis_guidance_first():
    o = organ("brain", [symptom("thoughts of suicide")])
    assert o["status"] == "talk_to_doctor" and "14416" in o["safety"]["message"] and "112" in o["safety"]["message"]


def test_brain_severe_headache_is_urgent():
    o = organ("brain", [symptom("headache", severity=9)])
    assert o["status"] == "talk_to_doctor" and o["safety"]["state"] == "URGENT"


# ---- stomach and intestines -----------------------------------------------------------------------------------------

def test_gut_meals_without_symptoms_are_steady():
    assert organ("stomach_intestines", [ev("food", {"name": "dal rice"}, source="user_message")])["status"] == "steady"


@pytest.mark.parametrize("days,status", [(2, "steady"), (3, "worth_watching"), (13, "worth_watching"), (14, "talk_to_doctor")])
def test_gut_symptom_days(days, status):
    names = ["bloating", "acidity", "constipation"]
    assert organ("stomach_intestines", [symptom(names[i % 3], ago=i) for i in range(1, days + 1)])["status"] == status


def test_gut_vomiting_blood_is_urgent():
    o = organ("stomach_intestines", [symptom("vomiting blood")])
    assert o["status"] == "talk_to_doctor" and o["safety"]["state"] == "URGENT"


# ---- liver and pancreas ---------------------------------------------------------------------------------------------

def test_liver_needs_food_logs():
    o = organ("liver_pancreas", [bp(120, 80)])
    assert o["status"] == "no_data"


def test_liver_meals_without_pattern_are_steady_and_gentle():
    o = organ("liver_pancreas", [ev("food", {"name": "dal rice"}, source="user_message")])
    assert o["status"] == "steady" and o["confidence"]["level"] == "low"


def test_liver_alcohol_days_per_week_edge():
    # 30-day window: 12 days = 2.8 a week, 13 days = 3.03 a week
    assert organ("liver_pancreas", [ev("food", {"name": "beer"}, i) for i in range(1, 13)])["status"] == "steady"
    assert organ("liver_pancreas", [ev("food", {"name": "beer"}, i) for i in range(1, 14)])["status"] == "worth_watching"


def test_liver_sugary_days_and_food_table_sweets():
    assert organ("liver_pancreas", [ev("food", {"name": "gulab jamun", "foods": ["gulab jamun"]}, i) for i in range(1, 22)])["status"] == "steady"
    o = organ("liver_pancreas", [ev("food", {"name": "gulab jamun", "foods": ["gulab jamun"]}, i) for i in range(1, 23)])
    assert o["status"] == "worth_watching" and "gulab jamun" in o["evidence"][0]["label"]


def test_liver_patterns_never_escalate_to_doctor():
    o = organ("liver_pancreas", [ev("food", {"name": "whisky and cake"}, i) for i in range(1, 31)])
    assert o["status"] == "worth_watching" and o["safety"] is None


# ---- kidneys and bladder --------------------------------------------------------------------------------------------

def water(ml: int, ago: int) -> dict:
    return ev("hydration", {"amount_ml": ml}, ago)


def test_kidneys_enough_water_is_steady():
    assert organ("kidneys_bladder", [water(2000, i) for i in (1, 2, 3)])["status"] == "steady"


@pytest.mark.parametrize("ml,days,status", [(1200, 3, "steady"), (1199, 3, "worth_watching"), (500, 2, "steady")])
def test_kidneys_water_edges(ml, days, status):
    assert organ("kidneys_bladder", [water(ml, i) for i in range(1, days + 1)])["status"] == status


def test_kidneys_water_is_summed_per_day():
    assert organ("kidneys_bladder", [water(600, i) for i in (1, 2, 3)] + [water(700, i) for i in (1, 2, 3)])["status"] == "steady"


def test_kidneys_fluid_restriction_is_respected():
    o = organ("kidneys_bladder", [water(800, i) for i in (1, 2, 3)], conditions=[{"id": "c", "condition_name": "Chronic kidney disease (CKD)"}])
    assert o["status"] == "steady" and any("care team" in n for n in o["notes"])


def test_kidneys_urinary_symptoms():
    assert organ("kidneys_bladder", [ev("symptom", {"symptom": "burning urination"})])["status"] == "worth_watching"
    o = organ("kidneys_bladder", [ev("symptom", {"symptom": "blood in urine"})])
    assert o["status"] == "talk_to_doctor"


# ---- thyroid --------------------------------------------------------------------------------------------------------

def tsh(value, ago=40, reference_range=None) -> dict:
    return {"id": "lab-1", "date": (TODAY - timedelta(days=ago)).isoformat(), "test_name": "TSH", "value": value, "unit": "mIU/L",
            "reference_range": reference_range}


@pytest.mark.parametrize("value,status", [(2.0, "steady"), (4.0, "steady"), (0.4, "steady"), (4.5, "worth_watching"), (0.3, "worth_watching"),
                                          (10.0, "worth_watching"), (10.5, "talk_to_doctor"), (0.05, "talk_to_doctor")])
def test_thyroid_tsh_edges(value, status):
    o = organ("thyroid", labs=[tsh(value)])
    assert o["status"] == status and o["evidence"][0]["value"] == value


def test_thyroid_uses_the_labs_own_range_and_keeps_old_results():
    assert organ("thyroid", labs=[tsh(4.5, reference_range="0.5-5.0")])["status"] == "steady"
    old = organ("thyroid", labs=[tsh(2.0, ago=400)])
    assert old["status"] == "steady" and any("more than a year" in n for n in old["notes"])


def test_thyroid_condition_and_unreadable_result():
    assert organ("thyroid", conditions=[{"id": "c", "condition_name": "Hypothyroidism"}])["status"] == "worth_watching"
    o = organ("thyroid", labs=[tsh("pending")])
    assert o["status"] == "steady" and "no number" in o["summary"]


def test_thyroid_chat_lab_older_than_window_still_counts():
    lab = ev("lab_result", {"name": "TSH", "value": 12, "unit": "mIU/L"}, ago=100, source="user_message")
    assert organ("thyroid", [lab])["status"] == "talk_to_doctor"


# ---- uterus and ovaries ---------------------------------------------------------------------------------------------

def test_uterus_phase_is_a_note_not_an_entry():
    # A predicted phase is dated today; as evidence it made "Last entry" claim today and padded the confidence count.
    o = organ("uterus_ovaries", cycle={"phase": "luteal", "cycle_day": 20, "flags": []})
    assert o["status"] == "no_data" and o["evidence"] == [] and o["evidence_count"] == 0 and o["updated_at"] is None
    assert any("luteal phase, day 20" in n and "estimate" in n for n in o["notes"])
    assert "Mark the first day" not in o["next_step"] and "Period start dates" not in " ".join(o["missing"])


def test_uterus_phase_does_not_move_last_entry_or_confidence():
    old = ev("menstrual_symptom", {"symptom": "cramps", "name": "cramps"}, ago=8, source="user_message")
    o = organ("uterus_ovaries", [old], cycle={"phase": "luteal", "cycle_day": 20, "flags": []})
    assert o["updated_at"] == (TODAY - timedelta(days=8)).isoformat() and o["evidence_count"] == 1


def test_uterus_shows_only_for_cycle_users_or_with_entries():
    assert "uterus_ovaries" not in run()
    assert "uterus_ovaries" not in run(cycle={"phase": None, "cycle_day": None, "flags": []})
    assert run(cycle={"phase": "follicular", "flags": []})["uterus_ovaries"]["status"] == "no_data"
    cramps = ev("menstrual_symptom", {"symptom": "cramps", "name": "cramps"}, source="user_message")
    assert run([cramps])["uterus_ovaries"]["status"] == "steady"
    result = E.build_organ_map([], today=TODAY)
    assert sum(result["counts"].values()) == len(result["organs"]) == len(ALWAYS)


def test_confidence_names_the_window_only_when_every_entry_is_inside_it():
    lab = {"id": "l1", "date": (TODAY - timedelta(days=31)).isoformat(), "test_name": "TSH", "value": 2.1, "unit": "mIU/L"}
    reason = organ("thyroid", labs=[lab])["confidence"]["reason"]
    assert "last 30 days" not in reason and "your records" in reason
    assert "last 30 days" in organ("heart", [bp(120, 80)])["confidence"]["reason"]


def test_uterus_cramps_are_common_not_alarming():
    o = organ("uterus_ovaries", [ev("menstrual_symptom", {"symptom": "cramps", "name": "cramps"}, source="user_message")])
    assert o["status"] == "steady" and "common around a period" in " ".join(o["reasons"])


def test_uterus_pcos_and_talk_flags_are_worth_watching():
    assert organ("uterus_ovaries", conditions=[{"id": "c", "condition_name": "PCOS"}])["status"] == "worth_watching"
    flag = {"id": "cycle_length", "severity": "talk", "title": "Your last cycle was outside the typical range", "message": "Your last cycle was 40 days."}
    assert organ("uterus_ovaries", cycle={"phase": None, "flags": [flag]})["status"] == "worth_watching"
    info = {"id": "spotting_between", "severity": "info", "title": "Spotting", "message": "You logged spotting between periods."}
    o = organ("uterus_ovaries", cycle={"phase": "follicular", "flags": [info]})
    assert o["status"] == "no_data" and info["message"] in o["notes"]  # an info flag is background, it never raises the status


def test_uterus_heavy_bleeding_flag_is_urgent_with_its_own_copy_first():
    from cycle_flags import URGENT_BLEEDING
    o = organ("uterus_ovaries", cycle={"phase": "menstrual", "cycle_day": 2, "flags": [URGENT_BLEEDING]})
    assert o["status"] == "talk_to_doctor" and list(o)[0] == "safety" and o["safety"]["message"] == URGENT_BLEEDING["message"]


def test_uterus_heavy_bleeding_in_chat_is_an_emergency():
    o = organ("uterus_ovaries", [ev("menstrual_symptom", {"symptom": "heavy bleeding", "name": "heavy bleeding"}, source="user_message")])
    assert o["status"] == "talk_to_doctor" and o["safety"]["state"] == "EMERGENCY"


def test_uterus_cycle_day_log_mirror_counts():
    log = ev("menstrual_symptom", {"name": "cycle day log", "flow": "medium", "symptoms": ["Cramps", "Bloating"], "severity": 4},
             feature="cycle_day", store="mirror")
    o = organ("uterus_ovaries", [log])
    assert o["status"] == "steady" and {e["source"] for e in o["evidence"]} == {"cycle log"}


# ---- bones and muscles ----------------------------------------------------------------------------------------------

def test_skeleton_workouts_are_steady():
    o = organ("skeleton_muscles", [ev("activity", {"name": "yoga", "duration_minutes": 40}, i) for i in (1, 3, 5)])
    assert o["status"] == "steady" and any("minutes of movement a week" in r for r in o["reasons"])


@pytest.mark.parametrize("days,status", [(3, "steady"), (4, "worth_watching")])
def test_skeleton_pain_days(days, status):
    assert organ("skeleton_muscles", [symptom("back pain", ago=i) for i in range(1, days + 1)])["status"] == status


def test_skeleton_severe_pain_is_urgent():
    o = organ("skeleton_muscles", [symptom("joint pain", severity=9)])
    assert o["status"] == "talk_to_doctor" and o["safety"]["state"] == "URGENT"
    assert organ("skeleton_muscles", [symptom("joint pain", severity=5)])["status"] == "steady"


# ---- skin -----------------------------------------------------------------------------------------------------------

def test_skin_without_mentions_is_no_data_and_says_why():
    o = organ("skin", [bp(120, 80), ev("food", {"name": "dal"})])
    assert o["status"] == "no_data" and "only knows about your skin" in o["next_step"]


def test_skin_rash_is_watched():
    assert organ("skin", [symptom("rash")])["status"] == "worth_watching"
    assert organ("skin", [ev("symptom", {"symptom": "acne breakout"})])["status"] == "worth_watching"


def test_skin_allergic_reaction_is_urgent():
    o = organ("skin", [symptom("allergic reaction")])
    assert o["status"] == "talk_to_doctor" and o["safety"] is not None


def test_a_cycle_day_pain_score_without_ticked_symptoms_still_counts_as_period_pain():
    log = ev("menstrual_symptom", {"name": "cycle day log", "flow": "heavy", "severity": 6}, 3, feature="cycle_day")
    o = organ("uterus_ovaries", [log])
    assert "Period pain: 6/10" in [f"{e['label']}: {e['value']}" for e in o["evidence"]]
    assert "Cramps, pain or flow on period days" not in o["missing"]


def test_a_condition_saved_by_the_tracker_and_mirrored_counts_once():
    mirror = ev("medical_condition", {"condition_name": "PCOS", "status": "Active"}, 8)
    o = organ("uterus_ovaries", [mirror], conditions=[{"id": "c", "condition_name": "PCOS", "status": "Active", "date": "2026-10-14"}])
    assert [e["label"] for e in o["evidence"]].count("PCOS") == 1


# --- the first-run setup decides who sees the reproductive organs ---------------------------------------------------------------

def _shown(**kw):
    return {o["organ_id"] for o in E.build_organ_map(today=TODAY, **kw)["organs"]}


def test_a_female_setup_always_shows_the_uterus_and_ovaries_even_with_nothing_logged():
    assert "uterus_ovaries" not in _shown()
    assert "uterus_ovaries" in _shown(reproductive="uterus_ovaries")


def test_a_male_setup_never_shows_them_even_with_cycle_data():
    cycle = {"phase": "luteal", "cycle_day": 20, "flags": []}
    assert "uterus_ovaries" in _shown(cycle=cycle)
    assert "uterus_ovaries" not in _shown(cycle=cycle, reproductive="none")


def test_any_other_setup_keeps_the_earlier_rule():
    cycle = {"phase": "luteal", "cycle_day": 20, "flags": []}
    assert _shown(reproductive=None) == _shown() and _shown(reproductive="by_use") == _shown()
    assert "uterus_ovaries" in _shown(cycle=cycle, reproductive="by_use")
