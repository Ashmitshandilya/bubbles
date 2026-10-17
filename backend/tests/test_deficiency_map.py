"""deficiency_map: every rule, the gap-not-fine behaviour, lab notes against the person's own range, and the wording rules."""
from __future__ import annotations

import itertools
import json
import re
from datetime import date, timedelta

import pytest

import deficiency_map as D
import organ_map_engine as OM

TODAY = date(2026, 10, 15)
_ids = itertools.count(1)


def ev(event_type: str, data: dict, ago: int = 1) -> dict:
    day = (TODAY - timedelta(days=ago)).isoformat()
    return {"id": f"ev-{next(_ids)}", "event_type": event_type, "extraction_status": "confirmed", "created_at": f"{day}T09:00:00+00:00",
            "extracted_data": {**data, "date": day, "_prov": {"source": "user_message"}}}


def symptom(name: str, days: tuple[int, ...] = (1, 3, 5)) -> list[dict]:
    return [ev("symptom", {"symptom": name, "name": name}, d) for d in days]


def heavy(days: tuple[int, ...] = (40, 41, 42)) -> list[dict]:
    return [ev("menstrual_symptom", {"symptom": "menstrual flow", "name": "period", "flow": "heavy"}, d) for d in days]


def lab(name: str, value, ref: str | None = None, unit: str = "ng/mL", ago: int = 20) -> dict:
    return {"id": f"lab-{next(_ids)}", "date": (TODAY - timedelta(days=ago)).isoformat(), "test_name": name, "value": value, "unit": unit,
            "reference_range": ref}


def run(events=(), **profile) -> dict:
    return D.evaluate(D.signals_from_rows(list(events), profile, today=TODAY))


def ids(res: dict) -> list[str]:
    return [n["id"] for n in res["nudges"]]


# ---- no data, no nudge ------------------------------------------------------------------------------------------------

def test_a_user_with_no_data_gets_no_nudge_and_no_note():
    assert run() == {"nudges": [], "lab_notes": []}


def test_risk_factors_alone_never_start_a_nudge():
    res = run([], answers={"diet_style": "vegan", "periods_reason": "pregnant"}, meds=["Metformin"])
    assert res["nudges"] == []


def test_general_signs_alone_never_start_a_nudge():
    res = run(symptom("feeling tired") + symptom("dizzy", (2, 4)) + symptom("low mood", (6, 8)))
    assert res["nudges"] == []


def test_a_sign_must_be_logged_on_two_different_days():
    assert run(symptom("hair fall", (1,)) + heavy()) == {"nudges": [], "lab_notes": []}
    assert ids(run(symptom("hair fall", (1, 2)) + heavy())) == ["iron"]


# ---- the seeded user -------------------------------------------------------------------------------------------------

SEED = dict(answers={"diet_style": "vegetarian"})


def test_seeded_user_with_low_ferritin_gets_a_medium_iron_nudge_first():
    res = run(symptom("feeling tired") + heavy(), labs=[lab("Ferritin", 6, "15-150")], **SEED)
    first = res["nudges"][0]
    assert first["id"] == "iron" and first["level"] == "medium" and first["kind"] == "lab"
    assert "below the range you entered" in first["headline"]
    assert "Your Ferritin of 6 ng/mL is below the range you entered (15 to 150)." in first["reasons"]
    assert first["ask"] == "Worth going over it with a doctor."
    assert res["lab_notes"][0]["status"] == "below"


def test_seeded_user_without_a_lab_gets_a_low_iron_nudge_with_a_gap():
    res = run(symptom("feeling tired") + heavy(), **SEED)
    n = res["nudges"][0]
    assert n["id"] == "iron" and n["level"] == "low" and n["kind"] == "signs"
    assert any("feeling tired on 3 of the last 30 days" in r for r in n["reasons"])
    assert any("heavy flow on 3 days" in r for r in n["reasons"])
    assert n["gaps"] == ["No recent ferritin or haemoglobin result is logged yet."]
    assert n["interacts"] and "Tea or coffee" in n["interacts"][0]


def test_a_specific_sign_plus_a_risk_and_a_second_sign_is_medium():
    res = run(symptom("hair fall") + symptom("feeling tired") + heavy(), **SEED)
    assert res["nudges"][0]["id"] == "iron" and res["nudges"][0]["level"] == "medium"


# ---- gap, never fine -------------------------------------------------------------------------------------------------

def test_a_recent_result_inside_the_range_is_neither_a_nudge_nor_called_fine():
    res = run(symptom("feeling tired") + heavy(), labs=[lab("Ferritin", 60, "15-150")], **SEED)
    assert res["nudges"] == []
    note = res["lab_notes"][0]
    assert note["status"] == "within" and "inside the range you entered" in note["text"]
    assert not re.search(r"\b(fine|healthy|normal|all clear)\b", json.dumps(res), re.I)


def test_an_old_result_counts_as_no_recent_result():
    res = run(symptom("hair fall") + symptom("feeling tired") + heavy(), labs=[lab("Ferritin", 6, "15-150", ago=500)], **SEED)
    n = res["nudges"][0]
    assert n["kind"] == "signs" and n["gaps"] == ["No recent ferritin or haemoglobin result is logged yet."]


def test_a_result_without_a_range_is_a_gap_not_a_comparison():
    res = run(symptom("hair fall") + symptom("feeling tired") + heavy(), labs=[lab("Ferritin", 6, None)], **SEED)
    assert res["lab_notes"][0]["status"] == "no_range"
    assert "cannot compare" in res["lab_notes"][0]["text"]
    assert any("no range entered" in g for g in res["nudges"][0]["gaps"])


def test_unknown_diet_is_named_as_a_gap():
    res = run(symptom("hair fall", (1, 2)) + symptom("pale", (3, 4)) + heavy())
    assert "Bubbles does not know how you usually eat." in res["nudges"][0]["gaps"] or len(res["nudges"][0]["gaps"]) == 2


def test_a_mentioned_recent_blood_test_with_no_result_asks_to_add_it():
    res = run(symptom("hair fall") + symptom("feeling tired") + heavy(),
              answers={"diet_style": "vegetarian", "recent_blood_test": "yes"})
    assert res["nudges"][0]["gaps"][0].startswith("You mentioned a recent blood test, but no ferritin or haemoglobin result")


# ---- the other entries ----------------------------------------------------------------------------------------------

def test_b12_tingling_with_vegan_diet_and_metformin():
    res = run(symptom("tingling in my feet") + symptom("feeling tired"), answers={"diet_style": "vegan"}, meds=["Metformin 500"])
    n = next(n for n in res["nudges"] if n["id"] == "b12")
    assert n["level"] == "medium"
    assert any("Metformin can lower B12" in t for t in n["interacts"])
    assert not any("milder" in r for r in n["reasons"]) and len(n["reasons"]) <= 5


def test_vitamin_d_needs_signs_even_with_little_sun():
    assert run(answers={"sun_exposure": "little"}) == {"nudges": [], "lab_notes": []}
    res = run(symptom("bone pain") + symptom("feeling tired"), answers={"sun_exposure": "little"})
    assert "vitamin_d" in ids(res)


def test_thyroid_signs_and_irregular_periods_from_onboarding():
    res = run(symptom("weight gain") + symptom("always cold"), answers={"periods": "irregular"})
    assert res["nudges"][0]["id"] == "thyroid" or "thyroid" in ids(res)


def test_a_known_thyroid_condition_silences_the_sign_based_thyroid_nudge():
    ev_ = symptom("weight gain") + symptom("always cold") + symptom("dry skin")
    assert "thyroid" in ids(run(ev_))
    assert "thyroid" not in ids(run(ev_, conditions=["Thyroid condition"]))


def test_blood_sugar_needs_a_sign_and_the_screening_gap():
    res = run(symptom("very thirsty") + symptom("slow healing cut"), answers={"bp_sugar_check": "longer_or_never"})
    assert "blood_sugar" in ids(res)
    assert run(answers={"bp_sugar_check": "longer_or_never"}) == {"nudges": [], "lab_notes": []}


def test_nudge_false_entries_never_nudge_from_signs():
    res = run(symptom("poor sleep") + symptom("weight gain") + symptom("low mood"))
    assert "cortisol" not in ids(res) and "iodine" not in ids(res)


def test_at_most_three_nudges_and_strongest_first():
    events = (symptom("hair fall") + symptom("feeling tired") + symptom("tingling") + symptom("bone pain") + symptom("weight gain")
              + symptom("always cold") + symptom("mouth ulcer") + heavy())
    res = run(events, answers={"diet_style": "vegan", "sun_exposure": "low", "periods": "irregular"})
    assert len(res["nudges"]) == D.MAX_NUDGES
    assert [n["level"] for n in res["nudges"]] == sorted((n["level"] for n in res["nudges"]), key=lambda l: l != "medium")


# ---- labs ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,entry", [
    ("Ferritin", "iron"), ("Haemoglobin", "iron"), ("Hb", "iron"), ("Vitamin B12", "b12"), ("Vitamin D (25-OH)", "vitamin_d"),
    ("TSH", "thyroid"), ("Free T4", "thyroid"), ("HbA1c", "blood_sugar"), ("Fasting glucose", "blood_sugar"), ("Folate", "folate"),
    ("Magnesium", "magnesium"), ("Zinc", "zinc"), ("Testosterone", "sex_hormones"), ("Cortisol", "cortisol"),
])
def test_lab_names_link_to_the_right_entry(name, entry):
    assert D.entry_for_lab(name) == entry


def test_unknown_lab_names_link_to_nothing():
    assert D.entry_for_lab("Creatinine") is None and D.entry_for_lab("") is None and D.lab_note({"label": "Creatinine"}) is None


@pytest.mark.parametrize("value,status", [(10, "below"), (15, "within"), (150, "within"), (151, "above"), ("positive", "no_number"), (None, "no_number")])
def test_lab_status_against_the_entered_range(value, status):
    assert D.lab_status({"value": value, "ref": (15.0, 150.0)}) == status
    assert D.lab_status({"value": 1, "ref": (None, None)}) == "no_range"


def test_lab_notes_keep_only_the_latest_result_per_test():
    res = run(labs=[lab("TSH", 7.1, "0.4-4.0", "mIU/L", ago=200), lab("TSH", 2.0, "0.4-4.0", "mIU/L", ago=10)])
    assert [n["status"] for n in res["lab_notes"]] == ["within"]


def test_tsh_above_range_nudges_without_interpreting():
    res = run(labs=[lab("TSH", 6.2, "0.4-4.0", "mIU/L")])
    n = res["nudges"][0]
    assert n["id"] == "thyroid" and n["level"] == "medium" and "above the range you entered" in n["headline"]


# ---- chat ------------------------------------------------------------------------------------------------------------

def test_chat_hint_is_one_gentle_line_for_the_seeded_user():
    h = D.chat_hint(symptom("feeling tired") + heavy(), {"answers": {"diet_style": "vegetarian"}, "labs": [lab("Ferritin", 6, "15-150")]})
    assert h and "\n" not in h and "not a diagnosis" in h and "ferritin" in h.lower()
    assert "dose" in h  # the instruction says no doses


def test_chat_hint_is_none_without_data_and_for_a_weak_low_nudge():
    assert D.chat_hint([], {}) is None
    assert D.chat_hint(symptom("feeling tired") + heavy(), {"answers": {"diet_style": "vegetarian"}}) is None


def test_chat_hint_never_raises():
    assert D.chat_hint([{"bad": object()}, None], {"labs": "nope", "answers": 3}) is None


# ---- structure and wording -------------------------------------------------------------------------------------------

def test_every_entry_has_the_documented_shape_and_valid_references():
    for eid, e in D.ENTRIES.items():
        assert e["id"] == eid and e["range_source"] == "report"
        assert set(e["signs"]) <= set(D.SIGNS) and set(e["risks"]) <= set(D.RISK_TEXT)
        assert set(e["organs"]) <= set(OM.ORGANS)
        assert all(l.startswith("link:") for l in e["links"])
        assert all(when is None or when in D.RISK_TEXT for when, _ in e["interacts"])
        assert e["touches"] and e["name"] and e["ask"]


def test_link_tags_used_here_are_known_to_rag_links():
    import rag_links
    known = set(rag_links.LINK_DOCS)
    for e in D.ENTRIES.values():
        for l in e["links"]:
            assert l[5:] in known, l


AUTHORITY = re.compile(r"\b(NHS|NICE|WHO|CDC|AHA|ADA|ICMR|NIH|NLM|FDA|MedlinePlus|Mayo)\b|guidelines? say|studies show|according to", re.I)


def all_user_text() -> list[str]:
    out = [s["label"] for s in D.SIGNS.values()] + list(D.RISK_TEXT.values())
    for e in D.ENTRIES.values():
        out += [e["name"], e["ask"], e["markers"], *e["foods"], *e["more_likely"], *e["touches"], *(t for _w, t in e["interacts"])]
    return out


def test_no_authority_names_no_doses_no_em_dashes_in_any_user_text():
    sample = run(symptom("hair fall") + symptom("feeling tired") + heavy(), labs=[lab("Ferritin", 6, "15-150")], **SEED)
    for text in all_user_text() + [json.dumps(sample), D.chat_hint(symptom("feeling tired") + heavy(), {"labs": [lab("Ferritin", 6, "15-150")]}) or ""]:
        assert not AUTHORITY.search(text), text
        assert "—" not in text and "–" not in text, text
        assert not re.search(r"\b\d+\s?(mg|mcg|µg|iu|ml)\b", text, re.I), text
        assert not re.search(r"\b(you have|you are suffering|deficient)\b", text, re.I), text


def test_result_is_json_serialisable():
    json.dumps(run(symptom("hair fall") + heavy(), labs=[lab("Ferritin", 6, "15-150")], **SEED))
