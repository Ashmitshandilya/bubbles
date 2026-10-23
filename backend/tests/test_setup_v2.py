"""Setup v2 (renovation plan 8.1, 8.2): country, state, how they describe themselves, relationship and living situation.

Country picks the emergency wording. India (and "never said", which includes everyone who set up before these questions existed) keeps the
original text byte for byte; any other country gets "your local emergency number" and no number at all.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import locale_support  # noqa: E402
import onboarding as ob  # noqa: E402
import safety_engine  # noqa: E402
from response_formatter import response_style_instruction  # noqa: E402

TODAY = date(2026, 10, 23)

#: the crisis text as it was before setup v2, copied here on purpose: this must never change for people in India
OLD_CRISIS_LINES = (
    "In India, call 112 for emergency help, or Tele-MANAS, the free 24x7 mental health line, on 14416 or 1-800-891-4416. "
    "Outside India, call your local emergency number, or find a free local line at findahelpline.com."
)


def answers(**more):
    return {"preferred_name": "Riya", "birth_date": "1994-01-01", "body": "female", "language": "english", "main_goal": "sleep", "conditions_any": "no",
            "sleep_pattern": "seven_eight", "stress_level": "sometimes", "periods": "regular", **more}


def crisis():
    return safety_engine.assess_safety("I want to end my life tonight")


# --- locale: India unchanged, everywhere else honest ----------------------------------------------------------------------------------

def test_india_crisis_text_is_byte_identical_to_before():
    assert safety_engine.CRISIS_LINES == OLD_CRISIS_LINES
    a = crisis()
    assert OLD_CRISIS_LINES in safety_engine.emergency_response(a)
    for c in (None, "", "in", "IN", "India"):
        assert safety_engine.emergency_response(a, c) == safety_engine.emergency_response(a)
        assert safety_engine.clarification_response(a, c) == safety_engine.clarification_response(a)


def test_another_country_gets_the_local_emergency_number_and_no_number():
    a = crisis()
    for c in ("other", "us", "uk", "ca", "au", "ae", "sg"):
        text = safety_engine.emergency_response(a, c)
        assert "your local emergency number" in text and "findahelpline.com" in text
        assert "112" not in text and "Tele-MANAS" not in text and "India" not in text, c
        assert "112" not in safety_engine.clarification_response(a, c)
    assert locale_support.emergency_number("other") == "your local emergency number"
    assert locale_support.emergency_number(None) == "112"


def test_the_style_line_follows_the_country():
    assert "the emergency number is 112" in response_style_instruction()
    assert response_style_instruction(None) == response_style_instruction("in")
    elsewhere = response_style_instruction("us")
    assert "the emergency number is 112" not in elsewhere and "your local emergency number" in elsewhere and "{LOCAL}" not in elsewhere


def test_the_same_style_text_is_otherwise_unchanged():
    base, elsewhere = response_style_instruction(), response_style_instruction("other")
    assert [l for l in base.splitlines() if "LOCAL" not in l] == [l for l in elsewhere.splitlines() if "LOCAL" not in l]


# --- the questions ------------------------------------------------------------------------------------------------------------------

def test_none_of_the_new_questions_is_required():
    for qid in ("country", "region", "gender", "gender_other", "relationship_status", "living_with", "chronotype"):
        assert qid in ob.BY_ID and not ob.BY_ID[qid]["required"], qid
    assert ob.required_missing(answers(), TODAY) == [], "skipping every new question still completes setup"


def test_country_sits_on_the_first_core_screen_and_the_rest_are_extras():
    assert ob.BY_ID["country"]["step"] == "core" and ob.BY_ID["country"]["screen"] == "first"
    for qid in ("region", "gender", "relationship_status", "living_with"):
        assert ob.BY_ID[qid]["step"] == "extras", qid
    assert ob.BY_ID["chronotype"]["step"] == "later"


def test_state_is_asked_only_in_india_and_the_self_description_only_when_chosen():
    assert "region" not in ob.visible_ids(answers(), TODAY)
    assert "region" in ob.visible_ids(answers(country="in"), TODAY)
    assert "region" not in ob.visible_ids(answers(country="us"), TODAY)
    assert "gender_other" not in ob.visible_ids(answers(gender="woman"), TODAY)
    assert "gender_other" in ob.visible_ids(answers(gender="self_describe"), TODAY)
    assert "gender_other" in ob.FREE_TEXT, "the self-description goes through the safety engine like any free text"
    assert ob.BY_ID["gender_other"]["maxlength"] == 30


def test_changing_country_drops_the_state_and_changing_gender_drops_the_self_description():
    merged, dropped, _ = ob.apply_answers(answers(country="in", region="kerala"), {"country": "us"}, TODAY)
    assert "region" not in merged and "region" in dropped
    merged, dropped, _ = ob.apply_answers(answers(gender="self_describe", gender_other="agender"), {"gender": "woman"}, TODAY)
    assert "gender_other" not in merged


def test_every_indian_state_and_territory_is_an_option_with_a_unique_id():
    ids = [o["id"] for o in ob.BY_ID["region"]["options"]]
    assert len(ids) == len(set(ids)) == 36
    assert "west_bengal" in ids and "delhi" in ids and "andaman_and_nicobar_islands" in ids


def test_living_alone_and_prefer_not_stand_alone():
    q = ob.BY_ID["living_with"]
    assert ob.clean_answer(q, ["alone", "partner"], answers(), TODAY) == ["alone"]
    assert ob.clean_answer(q, ["partner", "in_laws", "children"], answers(), TODAY) == ["partner", "in_laws", "children"]
    assert ob.clean_answer(q, ["family", "prefer_not"], answers(), TODAY) == ["prefer_not"]


def test_a_made_up_country_or_gender_is_refused():
    import pytest
    for qid, bad in (("country", "mars"), ("gender", "robot"), ("relationship_status", "yes")):
        with pytest.raises(ob.AnswerError):
            ob.clean_answer(ob.BY_ID[qid], bad, answers(), TODAY)


# --- the experience profile --------------------------------------------------------------------------------------------------------

def test_experience_carries_identity_and_orbit():
    exp = ob.build_experience(answers(country="in", region="kerala", gender="woman", relationship_status="married", living_with=["partner", "in_laws"]), TODAY)
    assert exp["identity"] == {"country": "in", "region": "kerala", "gender": "woman"}
    assert exp["orbit"] == {"status": "married", "living_with": ["partner", "in_laws"]}
    assert exp["version"] == ob.BANK_VERSION


def test_an_older_person_with_no_new_answers_gets_empty_identity_not_a_guess():
    exp = ob.build_experience(answers(), TODAY)
    assert exp["identity"] == {"country": None, "region": None, "gender": None}
    assert exp["orbit"] == {"status": None, "living_with": []}
    assert exp["anatomy"] and exp["companion"], "the rest of the profile is untouched"


def test_gender_never_changes_the_body_map():
    for g in ("woman", "man", "nonbinary", "self_describe", "prefer_not"):
        assert ob.build_experience(answers(gender=g), TODAY)["body_map"] == ob.build_experience(answers(), TODAY)["body_map"], g


def test_gender_and_country_choose_the_support_lines_only_through_locale_support():
    exp = ob.build_experience(answers(country="in", gender="man"), TODAY)
    numbers = [r["number"] for r in locale_support.resources_for(exp["identity"]["country"], exp["identity"]["gender"])]
    assert "181" not in numbers and "14416" in numbers
    exp = ob.build_experience(answers(country="other", gender="woman"), TODAY)
    assert [r["number"] for r in locale_support.resources_for(exp["identity"]["country"], exp["identity"]["gender"])] == [""]


# --- through the API ------------------------------------------------------------------------------------------------------------------

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from fake_db import FakeDB  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000ee"
H = {"Authorization": "Bearer tok"}


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "test-key")   # a lazy import during setup completion can load .env and change the fallback key mid-test
    import onboarding_api
    db = FakeDB({"tok": USER})
    app = FastAPI()
    app.include_router(onboarding_api.build_router(lambda a: SimpleNamespace(id=USER), db))
    return TestClient(app), db


def put(client, patch):
    return client.put("/onboarding/answers", json={"answers": patch}, headers=H)


def test_a_self_description_with_crisis_words_is_answered_and_never_stored(api):
    client, _ = api
    put(client, {"preferred_name": "Riya", "birth_date": "1994-01-01"})
    r = put(client, {"gender": "self_describe", "gender_other": "I want to end my life tonight"}).json()
    assert r["safety"]["field"] == "gender_other" and "findahelpline" in r["safety"]["message"]
    assert "gender_other" not in client.get("/onboarding/state", headers=H).json()["answers"]
    fine = put(client, {"gender_other": "agender"}).json()
    assert fine["safety"] is None and fine["answers"]["gender_other"] == "agender"


def test_completing_setup_saves_identity_and_orbit_and_get_experience_returns_them(api):
    client, db = api
    put(client, answers(country="in", region="kerala", gender="woman", relationship_status="dating", living_with=["partner"]))
    out = client.post("/onboarding/complete", headers=H)
    assert out.status_code == 200, out.text
    exp = out.json()["experience"]
    assert exp["identity"] == {"country": "in", "region": "kerala", "gender": "woman"} and exp["orbit"]["status"] == "dating"
    import doc_store
    saved = doc_store.get(db, USER, "experience", "main")
    assert saved["identity"]["country"] == "in"


def test_someone_who_finished_setup_before_these_questions_is_not_sent_back(api):
    client, db = api
    import doc_store
    old = {"preferred_name": "Riya", "birth_date": "1994-01-01", "body": "female", "language": "english", "main_goal": "sleep", "conditions_any": "no",
           "sleep_pattern": "seven_eight", "stress_level": "sometimes", "periods": "regular"}
    doc_store.put(db, USER, "onboarding", "v1", {"answers": old, "completed_at": "2026-10-10T00:00:00+00:00", "bank_version": "2026-10b", "step": 3})
    state = client.get("/onboarding/state", headers=H).json()
    assert state["complete"] is True and state["required_missing"] == [] and state["bank_changed"] is True


def test_identity_for_reads_country_and_gender_only(api):
    import doc_store, onboarding_api
    _, db = api
    assert onboarding_api.identity_for(db, USER) == {}
    doc_store.put(db, USER, "experience", "main", {"identity": {"country": "uk", "region": None, "gender": "man"}, "companion": {"name": "Riya"}})
    assert onboarding_api.identity_for(db, USER) == {"country": "uk", "gender": "man"}
