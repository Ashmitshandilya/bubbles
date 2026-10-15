"""The body systems beyond the original nine: eyes (see test_eyes), ears, mouth, thyroid, bladder, skin and breasts, plus the words
that reach them from chat and the two new urgent-assessment rules."""
from datetime import datetime, timedelta, timezone

import pytest

from health_semantics import analyze
from organ_intelligence import build_body_system_intelligence, symptom_day_snapshot
from organ_tracker import DIRECT_EVIDENCE_FIELDS, ORGANS, RISK_FACTORS, SYMPTOM_DAY_KEYS, assess_all, assess_organ
from safety_engine import assess_safety

NOW = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)
NEW = ("ears", "mouth", "thyroid", "bladder", "skin", "breasts")


def symptom(offset, name, **prov):
    day = (NOW.date() - timedelta(days=offset)).isoformat()
    return {"id": f"{name}-{offset}", "event_type": "symptom", "extraction_status": "confirmed",
            "extracted_data": {"date": day, "name": name, "symptom": name, "_prov": {"assertion": "present", **prov}}}


def test_every_new_system_is_known_and_starts_as_not_enough_data():
    for organ in NEW:
        assert organ in ORGANS
        a = assess_organ(organ, {})
        assert (a.status, a.score, a.confidence, a.signals) == ("unknown", None, 0.0, []), organ
        assert any("not mean the organ is healthy" in text for text in a.limitations), organ
    assert len(assess_all({})) == len(ORGANS) == len(set(ORGANS)) == 16


def test_every_system_names_the_evidence_it_would_need_and_visit_dates_are_not_evidence():
    for organ in ORGANS:
        assert DIRECT_EVIDENCE_FIELDS[organ], organ
    flat = {field for fields in DIRECT_EVIDENCE_FIELDS.values() for field in fields}
    assert not {"last_eye_exam", "dental_visit", "hearing_test", "mammogram", "breast_exam", "urine_test"} & flat


def test_risk_weights_only_point_at_real_systems_and_stay_modest():
    for factor, weights in RISK_FACTORS.items():
        for organ, weight in weights.items():
            assert organ in ORGANS, (factor, organ)
            assert 0 < weight <= 0.3, (factor, organ)


@pytest.mark.parametrize("factor,system,names", [
    ("frequent_ear_symptoms", "ears", ["ear pain", "ringing in the ears", "hearing loss"]),
    ("frequent_mouth_symptoms", "mouth", ["toothache", "mouth ulcers", "bleeding gums"]),
    ("frequent_urinary_symptoms", "bladder", ["burning when urinating", "frequent urination", "frequent urination"]),
    ("frequent_skin_symptoms", "skin", ["rash", "rash", "rash"]),
    ("frequent_breast_symptoms", "breasts", ["breast pain", "breast pain", "breast pain"]),
])
def test_three_symptom_days_in_two_weeks_make_a_system_worth_watching_only_one_signal(factor, system, names):
    events = [symptom(i + 1, name) for i, name in enumerate(names)]
    snapshot = symptom_day_snapshot(events, NOW)
    assert snapshot == {f"{system}_symptom_days": 3}
    a = assess_organ(system, snapshot)
    assert [s.factor for s in a.signals] == [factor] and a.status == "no_major_risk_signal"
    assert SYMPTOM_DAY_KEYS[factor] in snapshot
    assert any("mentioning to a clinician" in text for text in a.recommended_actions)


def test_two_days_is_not_a_pattern_and_missing_is_never_zero():
    assert symptom_day_snapshot([symptom(1, "toothache"), symptom(2, "toothache")], NOW) == {"mouth_symptom_days": 2}
    assert assess_organ("mouth", {"mouth_symptom_days": 2}).signals == []
    assert symptom_day_snapshot([], NOW) == {}
    assert symptom_day_snapshot([symptom(1, "headache")], NOW) == {}


def test_only_live_first_person_recent_symptoms_count():
    events = [symptom(1, "toothache", assertion="negated"), symptom(2, "toothache", subject="other"),
              {**symptom(3, "toothache"), "extraction_status": "rejected"}, symptom(30, "toothache"),
              {**symptom(4, "toothache"), "event_type": "nutrition"}]
    assert symptom_day_snapshot(events, NOW) == {}


def test_chewed_tobacco_and_smoking_raise_the_mouth_signal_with_dental_advice_not_a_diagnosis():
    a = assess_organ("mouth", {"tobacco_chewing": True})
    assert [s.factor for s in a.signals] == ["tobacco_chewing"]
    assert any("dental and oral check" in text for text in a.recommended_actions)
    assert not any("cancer" in text.lower() or "diagnos" in text.lower() for text in a.recommended_actions)
    assert assess_organ("mouth", {"tobacco_chewing": "no"}).signals == []


def test_a_thyroid_system_has_no_symptom_signals_only_results():
    assert not any("thyroid" in weights for weights in RISK_FACTORS.values())
    assert assess_organ("thyroid", {"tsh": 2.1}).signals[0].direction == "direct"


def test_the_report_lists_all_sixteen_systems_with_signals_where_logged():
    events = [symptom(i, "ear pain") for i in (1, 2, 3)]
    report = build_body_system_intelligence(events)
    by = {s["organ"]: s for s in report["systems"]}
    assert report["total_systems"] == 16 and by["ears"]["signals"] and by["thyroid"]["status"] == "unknown"


# --- chat words ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,concept", [
    ("I have a toothache", "toothache"), ("tooth ache since morning", "toothache"), ("my tooth hurts", "toothache"), ("dant dard hai", "toothache"),
    ("my gums are bleeding", "gum_bleeding"), ("I get mouth ulcers", "mouth_ulcer"), ("munh mein chhale hain", "mouth_ulcer"),
    ("my ear hurts", "ear_pain"), ("earache", "ear_pain"), ("kaan mein dard hai", "ear_pain"),
    ("ringing in my ears", "tinnitus"), ("kaanon mein siti bajti hai", "tinnitus"),
    ("I have trouble hearing", "hearing_loss"), ("I can't hear properly", "hearing_loss"),
    ("burning when I pee", "burning_urination"), ("painful urination", "burning_urination"), ("peshab mein jalan hai", "burning_urination"),
    ("I need to pee all the time", "frequent_urination"), ("baar baar peshab aata hai", "frequent_urination"),
    ("my breasts are sore", "breast_pain"), ("breast tenderness", "breast_pain"),
])
def test_everyday_words_become_symptoms(text, concept):
    assert concept in [f.concept for f in analyze(text) if f.experiencer == "self" and f.assertion == "present"]


@pytest.mark.parametrize("text", ["a lump in my throat", "I had a lump in my breast removed in 2019", "no toothache", "I went to the dentist", "my ears are pierced"])
def test_look_alikes_and_history_are_not_current_symptoms(text):
    assert not [f for f in analyze(text) if f.experiencer == "self" and f.assertion == "present" and f.temporal in {"current", "recent", "recurring", "unknown"}]


def test_a_new_breast_lump_and_sudden_hearing_loss_need_prompt_assessment_not_an_emergency_call():
    for text in ("I found a lump in my breast", "there is a hard lump on my left breast", "sudden hearing loss", "I suddenly lost my hearing in one ear",
                 "my hearing suddenly dropped overnight"):
        a = assess_safety(text)
        assert (a.level, a.state) == ("AMBER", "URGENT"), text


def test_those_rules_stay_quiet_for_other_people_denials_history_and_ordinary_hearing_trouble():
    for text in ("my mom found a lump in her breast", "no breast lump", "I had a lump in my breast removed in 2019", "I have trouble hearing the teacher",
                 "my grandfather has hearing loss", "ringing in my ears", "my breasts are sore"):
        assert assess_safety(text).state == "NO_REDFLAG", text
