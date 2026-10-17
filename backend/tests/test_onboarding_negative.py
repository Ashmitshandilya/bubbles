"""C1 negative cases: what the setup refuses, and proof that a refused request changes nothing."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import doc_store  # noqa: E402
import onboarding as ob  # noqa: E402
import onboarding_api  # noqa: E402
from calc_core import local_today  # noqa: E402
from fake_db import FakeDB  # noqa: E402
from test_onboarding import base, born  # noqa: E402

A = "00000000-0000-0000-0000-0000000000aa"
B = "00000000-0000-0000-0000-0000000000bb"
HA = {"Authorization": "Bearer a"}
HB = {"Authorization": "Bearer b"}


@pytest.fixture()
def api():
    db = FakeDB({"a": A, "b": B})

    def get_user(authorization):
        uid = {"Bearer a": A, "Bearer b": B}.get(authorization or "")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        return SimpleNamespace(id=uid)

    app = FastAPI()
    app.include_router(onboarding_api.build_router(get_user, db))
    return TestClient(app), db


def put(c, answers, h=HA, **extra):
    return c.put("/onboarding/answers", json={"answers": answers, **extra}, headers=h)


def stored(db, uid=A):
    return doc_store.get(db, uid, "onboarding", "v1")


# --- the 18+ gate runs before anything is stored ---------------------------------------------------------------------------

def test_body_alone_first_is_refused_and_nothing_is_stored(api):
    c, db = api
    r = put(c, {"body": "female"})
    assert r.status_code == 422 and r.json()["detail"]["field"] == "birth_date"
    assert stored(db) is None


def test_under_18_in_the_same_save_as_the_body_stores_no_answer(api):
    c, db = api
    # key order must not matter: body first in the object, date second
    r = put(c, {"body": "female", "preferred_name": "Sam", "birth_date": born(17), "language": "hindi"})
    assert r.json() == {"status": "success", "under_18": True}
    assert set(stored(db)) == {"age_gate", "at", "bank_version"}
    assert put(c, {"body": "male"}).status_code == 403
    assert c.get("/onboarding/state", headers=HA).json()["answers"] == {}


def test_exactly_18_today_is_in_and_one_day_short_is_out(api):
    c, _ = api
    t = local_today()
    eighteen = t.replace(year=t.year - 18, day=28) if (t.month, t.day) == (2, 29) else t.replace(year=t.year - 18)
    assert put(c, {"body": "male", "birth_date": eighteen.isoformat()}).status_code == 200
    one_day_short = eighteen + timedelta(days=1)
    assert put(c, {"body": "male", "birth_date": one_day_short.isoformat()}, h=HB).json().get("under_18") is True


@pytest.mark.parametrize("bad", [12345, 20000101, ["2000-01-01"], {"d": "2000-01-01"}, True, "tomorrow", "2000-02-30", "", "0000-00-00", "2999-01-01", "1800-01-01"])
def test_a_garbage_birth_date_is_a_clean_422_and_stores_nothing(api, bad):
    c, db = api
    r = put(c, {"body": "female", "birth_date": bad})
    assert r.status_code == 422, r.text
    assert stored(db) is None


def test_a_null_birth_date_with_other_answers_is_refused(api):
    c, db = api
    r = put(c, {"body": "female", "birth_date": None})
    assert r.status_code == 422 and stored(db) is None


# --- malformed requests -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [{}, {"answers": None}, {"answers": []}, {"answers": "body"}, {"answers": 5}, {"answers": [{"body": "male"}]}])
def test_answers_must_be_an_object(api, payload):
    c, db = api
    assert c.put("/onboarding/answers", json=payload, headers=HA).status_code == 422
    assert stored(db) is None


def test_a_non_object_body_is_refused(api):
    c, _ = api
    assert c.put("/onboarding/answers", json=[1, 2], headers=HA).status_code == 422
    assert c.put("/onboarding/answers", content=b"not json", headers={**HA, "Content-Type": "application/json"}).status_code == 422


def test_too_many_keys_are_refused(api):
    c, db = api
    r = put(c, {f"k{i}": 1 for i in range(41)})
    assert r.status_code == 422 and stored(db) is None


def test_unknown_keys_are_refused_and_the_valid_ones_beside_them_are_not_kept(api):
    c, db = api
    assert put(c, {"body": "male", "birth_date": born(30)}).status_code == 200
    before = stored(db)
    for key in ("mystery", "is_admin", "ai_consent", "goals", "tone2", "__proto__", "diet_style "):
        r = put(c, {"sleep_pattern": "seven_eight", key: "x"})
        assert r.status_code == 422, key
    assert stored(db) == before                                # all-or-nothing: the valid sleep answer was not kept


@pytest.mark.parametrize("qid,value", [
    ("body", ["female"]), ("body", {"id": "female"}), ("body", 1), ("body", True), ("preferred_name", 123), ("preferred_name", ["Riya"]), ("preferred_name", {"a": 1}),
    ("preferred_name", "   "), ("preferred_name", "x" * 5000), ("language", "klingon"), ("language", None), ("main_goal", ["sleep", "mood"]),
    ("sleep_pattern", None), ("stress_level", None), ("stress_level", 3), ("conditions_any", True), ("height_weight", "180/70"), ("height_weight", [180, 70]),
    ("height_weight", {"height_cm": "tall"}), ("height_weight", {"height_cm": 1e9}), ("diet_style", "carnivore"), ("diet_style", ["veg"]),
    ("recent_blood_test", "maybe"), ("recent_blood_test", 1), ("recent_blood_test", {"yes": True}), ("avoid_topics", "weight"), ("avoid_topics", [1, 2]),
    ("avoid_topics", ["x"] * 500), ("drains_other", "y" * 5000), ("last_period", "yesterday"), ("last_period", 20261001),
])
def test_wrong_type_missing_or_oversized_answers_are_a_422_not_a_500(api, qid, value):
    c, db = api
    put(c, {"body": "female", "birth_date": born(30)})
    before = stored(db)
    r = put(c, {qid: value})
    assert r.status_code == 422, (qid, value, r.status_code, r.text[:200])
    assert stored(db) == before


def test_a_bad_answer_in_the_middle_of_a_patch_saves_none_of_the_patch(api):
    c, db = api
    r = put(c, {"body": "male", "birth_date": born(30), "language": "english", "stress_level": "extreme"})
    assert r.status_code == 422 and r.json()["detail"]["field"] == "stress_level"
    assert stored(db) is None


def test_the_step_marker_cannot_be_abused(api):
    c, db = api
    for step in ("abc", -1, 99, 1.5, [1], None, True):
        r = put(c, {"body": "male", "birth_date": born(30)}, step=step)
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert 0 <= stored(db).get("step", 0) <= len(ob.STEPS)


# --- skipping required items ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("qid", ["body", "language", "birth_date", "preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level"])
def test_a_required_answer_cannot_be_skipped_with_null(api, qid):
    c, db = api
    assert put(c, base("male")).status_code == 200
    before = stored(db)
    assert put(c, {qid: None}).status_code == 422, qid
    assert stored(db) == before


def test_periods_is_required_for_a_female_body_only(api):
    c, _ = api
    assert put(c, base("female")).status_code == 200
    assert put(c, {"periods": None}).status_code == 422
    assert put(c, base("male"), h=HB).status_code == 200
    assert put(c, {"periods": "regular"}, h=HB).status_code == 422          # a male body is refused the question outright


def test_complete_is_refused_until_every_required_answer_is_there(api):
    c, db = api
    put(c, {"body": "female", "birth_date": born(30)})
    r = c.post("/onboarding/complete", headers=HA)
    assert r.status_code == 422 and "stress_level" in r.json()["detail"]["missing"] and "periods" in r.json()["detail"]["missing"]
    assert "completed_at" not in stored(db)
    assert doc_store.get(db, A, "experience", "main") is None
    assert db.tables.get("profiles", []) == []                # nothing was written to the profile either


def test_complete_with_no_setup_at_all_is_refused(api):
    c, db = api
    assert c.post("/onboarding/complete", headers=HA).status_code == 422
    assert doc_store.get(db, A, "experience", "main") is None


# --- double submit ----------------------------------------------------------------------------------------------------------

def test_completing_twice_gives_the_same_result_and_no_duplicate_records(api):
    c, db = api
    answers = base("female", 30, conditions_any="yes", conditions=["diabetes", "thyroid"], allergies="yes", allergy_types=["food"], diet_style="vegetarian", recent_blood_test="yes")
    assert put(c, answers).status_code == 200
    one = c.post("/onboarding/complete", headers=HA)
    two = c.post("/onboarding/complete", headers=HA)
    assert one.status_code == two.status_code == 200
    assert one.json()["experience"] == two.json()["experience"] and one.json()["applied"] == two.json()["applied"]
    from health_logs import DOMAINS, list_domain
    names = [e["condition_name"] for e in list_domain(db, "conditions", DOMAINS["conditions"], A, 730)["entries"]]
    assert sorted(names) == ["Diabetes", "Thyroid condition"]
    assert len(list_domain(db, "allergies", DOMAINS["allergies"], A, 730)["entries"]) == 1


def test_saving_the_same_answers_twice_is_harmless(api):
    c, _ = api
    one = put(c, base("male")).json()
    two = put(c, base("male")).json()
    assert one["answers"] == two["answers"] and two["dropped"] == []


# --- other people ----------------------------------------------------------------------------------------------------------

def test_one_person_cannot_see_or_change_anothers_setup(api):
    c, db = api
    put(c, base("female", preferred_name="Riya"))
    theirs = c.get("/onboarding/state", headers=HB).json()
    assert theirs["answers"] == {} and theirs["complete"] is False
    assert put(c, {"stress_level": "often"}, h=HB).status_code == 422            # B has no date of birth yet: nothing of A's is borrowed
    c.post("/onboarding/complete", headers=HA)
    assert c.get("/experience", headers=HB).json()["experience"] is None
    assert c.get("/experience", headers=HA).json()["experience"] is not None
    assert stored(db, B) is None


def test_an_under_18_flag_belongs_to_that_person_only(api):
    c, _ = api
    put(c, {"body": "male", "birth_date": born(15)})
    assert c.get("/onboarding/state", headers=HA).json()["under_18"] is True
    assert c.get("/onboarding/state", headers=HB).json()["under_18"] is False
    assert put(c, base("male"), h=HB).status_code == 200


@pytest.mark.parametrize("method,path", [("get", "/onboarding/tour"), ("put", "/onboarding/tour"), ("get", "/onboarding/state"), ("post", "/onboarding/complete"),
                                         ("get", "/experience"), ("get", "/onboarding/questions")])
def test_a_bad_or_missing_token_is_refused_everywhere(api, method, path):
    c, _ = api
    assert getattr(c, method)(path).status_code == 401
    assert getattr(c, method)(path, headers={"Authorization": "Bearer nope"}).status_code == 401


# --- the tour ---------------------------------------------------------------------------------------------------------------

def test_the_tour_flag_is_per_person_and_replay_never_resets_it(api):
    c, _ = api
    c.put("/onboarding/tour", json={"skipped": True}, headers=HA)
    assert c.get("/onboarding/tour", headers=HB).json()["seen"] is False
    first = c.get("/onboarding/tour", headers=HA).json()
    again = c.put("/onboarding/tour", json={}, headers=HA).json()                  # replayed and finished again without a choice
    assert again["seen"] is True and again["at"] == first["at"] and again["skipped"] is True
    done = c.put("/onboarding/tour", json={"skipped": False}, headers=HA).json()
    assert done["skipped"] is False and done["at"] == first["at"]


@pytest.mark.parametrize("payload", [{"skipped": "yes"}, {"skipped": 1}, {"skipped": 0}, {"skipped": []}, {"skipped": {}}, [True], "true", 5])
def test_a_bad_tour_body_is_refused_and_changes_nothing(api, payload):
    c, db = api
    assert c.put("/onboarding/tour", json=payload, headers=HA).status_code == 422
    assert doc_store.get(db, A, "tour", "v1") is None


def test_the_tour_document_holds_no_answers(api):
    c, db = api
    c.put("/onboarding/tour", json={"skipped": False, "body": "female", "name": "Riya"}, headers=HA)
    assert set(doc_store.get(db, A, "tour", "v1")) == {"seen", "at", "skipped"}


# --- keys other lanes read, and consent ---------------------------------------------------------------------------------------

def test_diet_style_and_recent_blood_test_are_kept_for_the_deficiency_work(api):
    c, db = api
    assert {"diet_style", "recent_blood_test"} <= set(ob.BY_ID)
    assert not ob.BY_ID["diet_style"]["required"] and not ob.BY_ID["recent_blood_test"]["required"]
    put(c, base("male", diet_style="vegan", recent_blood_test="no"))
    assert stored(db)["answers"]["diet_style"] == "vegan" and stored(db)["answers"]["recent_blood_test"] == "no"
    c.post("/onboarding/complete", headers=HA)
    assert doc_store.get(db, A, "profile", "me")["diet_style"] == "vegan"


def test_setup_never_writes_a_consent(api):
    c, db = api
    put(c, base("male"))
    c.post("/onboarding/complete", headers=HA)
    assert "ai_consent" not in ob.BY_ID
    for name, rows in db.tables.items():
        assert "consent" not in name or rows == [], name
    assert put(c, {"ai_consent": "yes"}).status_code == 422


def test_crisis_text_in_a_free_field_is_not_stored(api):
    c, db = api
    put(c, base("male"))
    r = put(c, {"conditions_any": "yes", "conditions": ["other"], "conditions_other": "I want to kill myself"}).json()
    assert r["safety"] and "conditions_other" not in r["answers"]
    assert "kill myself" not in str(stored(db))
