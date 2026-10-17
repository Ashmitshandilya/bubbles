"""First-run setup: which questions each body and age sees, validation, the experience profile, and the API with a fake database."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import onboarding as ob  # noqa: E402
from fake_db import FakeDB  # noqa: E402

TODAY = date(2026, 10, 15)
PERIOD_Q = ("periods", "periods_reason", "last_period", "pregnancy_plans", "due_date", "baby_birth_date", "midlife_changes", "cervical_screen")


def born(age: int) -> str:
    return date(TODAY.year - age, 1, 1).isoformat()


def base(body="female", age=32, **more):
    return {"preferred_name": "Riya", "birth_date": born(age), "body": body, "language": "english", "main_goal": "sleep", "conditions_any": "no",
            "sleep_pattern": "seven_eight", "stress_level": "sometimes", **({"periods": "regular"} if body == "female" else {}), **more}


def shown(answers):
    return set(ob.visible_ids(answers, TODAY))


# --- the bank -----------------------------------------------------------------------------------------------------------------

def test_the_bank_is_well_formed():
    for q in ob.QUESTIONS:
        assert q["type"] in {"text", "date", "single", "multi", "slider", "faces", "number_pair"}, q["id"]
        if q["type"] in ("single", "multi"):
            ids = [o["id"] for o in q["options"]]
            assert len(ids) == len(set(ids)) >= 2, q["id"]
            assert set(q.get("exclusive", [])) <= set(ids), q["id"]
        assert q["step"] in {s["id"] for s in ob.STEPS}, q["id"]
        assert q["required"] == (q["id"] in ob.REQUIRED)
    assert set(ob.REQUIRED) == {"body", "language", "birth_date", "preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level"}
    assert ob.QUESTIONS[0]["id"] == "body", "gender is the first thing a person sees"
    assert "ai_consent" not in ob.BY_ID, "consent is never bundled into the questions"
    assert [q["id"] for q in ob.QUESTIONS if q["step"] == "core"][:2] == ["body", "language"]
    assert {q["step"] for q in ob.QUESTIONS} <= {s["id"] for s in ob.STEPS}


def test_questions_that_share_a_screen_share_a_step_and_titled_screens_exist():
    groups: dict[str, list[dict]] = {}
    for q in ob.QUESTIONS:
        if q.get("screen"):
            groups.setdefault(q["screen"], []).append(q)
    assert groups, "grouping keeps the optional stage short"
    for screen, members in groups.items():
        assert len({m["step"] for m in members}) == 1, screen
        assert len(members) >= 2, screen
        assert screen in ob.SCREENS or screen in {"first", "conditions"}, screen
        assert [m["id"] for m in members] == [q["id"] for q in ob.QUESTIONS if q.get("screen") == screen]
    assert [m["id"] for m in groups["first"]] == ["body", "language"] and [m["id"] for m in groups["about"]] == ["birth_date", "preferred_name"]
    for key in ("diet_style", "recent_blood_test"):
        assert ob.BY_ID[key]["step"] == "extras", "the nutrition lane reads these two keys"


def test_a_scripted_run_that_answers_only_required_questions_is_at_most_eight_taps():
    # the language is filled in from the browser (not a tap); every other required question is one tap or one field
    for body in ob.BODIES:
        need = [q for q in ob.required_missing({"body": body, "birth_date": born(32)}, TODAY) if q != "language"]
        assert 2 + len(need) <= 8, (body, need)           # body and date of birth, then the rest
    assert ob.required_missing({"body": "female", "birth_date": born(32)}, TODAY) == [
        "language", "preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level", "periods"]
    assert "periods" not in ob.required_missing({"body": "male", "birth_date": born(32)}, TODAY)
    other = {"body": "other", "birth_date": born(32)}
    assert "periods" in shown(other) and "periods" not in ob.required_missing(other, TODAY), "periods is required for a female body only"


def test_no_visible_words_use_banned_style():
    text = " ".join(f"{q['title']} {q['why']} " + " ".join(o["label"] for o in q.get("options", [])) for q in ob.QUESTIONS)
    assert "—" not in text and "–" not in text
    for banned in ("diagnos", "disorder", "healthy", "lonely", "friends do you have"):
        assert banned not in text.lower(), banned


# --- age and body decide what is asked ---------------------------------------------------------------------------------------

def test_a_male_body_is_never_asked_about_periods_pregnancy_or_cervical_screening():
    for age in (18, 32, 45, 60, 80):
        a = base("male", age)
        assert not shown(a) & set(PERIOD_Q), age
        goals = {o["id"] for o in ob.visible_options(ob.BY_ID["main_goal"], a, TODAY)}
        assert "cycle" not in goals
        assert "periods" not in {o["id"] for o in ob.visible_options(ob.BY_ID["avoid_topics"], a, TODAY)}
        assert "pcos" not in {o["id"] for o in ob.visible_options(ob.BY_ID["conditions"], a, TODAY)}
    assert "urinary_changes" in shown(base("male", 50)) and "urinary_changes" not in shown(base("male", 40))


def test_a_female_body_gets_every_cycle_question_that_fits_her_age():
    assert {"periods", "pregnancy_plans"} <= shown(base("female", 28)) and "cervical_screen" not in shown(base("female", 28))
    assert "cervical_screen" in shown(base("female", 30)) and "cervical_screen" in shown(base("female", 65)) and "cervical_screen" not in shown(base("female", 66))
    assert "midlife_changes" not in shown(base("female", 39)) and "midlife_changes" in shown(base("female", 40))
    assert "periods" in shown(base("female", 55)) and "periods" not in shown(base("female", 56))
    assert "pregnancy_plans" in shown(base("female", 50)) and "pregnancy_plans" not in shown(base("female", 51))
    assert "urinary_changes" not in shown(base("female", 60))


def test_bp_and_sugar_checks_start_at_thirty_for_everyone():
    assert "bp_sugar_check" not in shown(base("male", 29)) and "bp_sugar_check" in shown(base("male", 30))


def test_other_prefer_not_and_trans_are_asked_about_periods_but_never_assumed():
    for body in ("other", "prefer_not", "trans"):
        a = base(body, 32)
        assert "periods" in shown(a)
        assert not shown(a) & {"pregnancy_plans", "cervical_screen", "midlife_changes"}
        opts = {o["id"] for o in ob.visible_options(ob.BY_ID["periods"], a, TODAY)}
        assert {"none", "prefer_not"} <= opts                 # "I don't get periods" is an answer


def test_pregnancy_follow_ups_appear_only_when_they_apply():
    a = base("female", 30, periods="not_now", periods_reason="pregnant")
    assert {"due_date"} <= shown(a) and not shown(a) & {"pregnancy_plans", "last_period", "baby_birth_date"}
    b = base("female", 30, periods="regular")
    assert "last_period" in shown(b) and "periods_reason" not in shown(b)


def test_condition_follow_ups_appear_only_after_a_yes():
    assert not shown(base()) & {"conditions", "conditions_other"}
    assert "conditions" in shown(base(conditions_any="yes")) and "conditions_other" not in shown(base(conditions_any="yes"))
    assert "conditions_other" in shown(base(conditions_any="yes", conditions=["other"]))
    assert not {"none", "prefer_not"} & {o["id"] for o in ob.BY_ID["conditions"]["options"]}, "the yes / no question carries those"


def test_the_screening_questions_are_not_part_of_the_first_run():
    first_run = {q["id"] for q in ob.QUESTIONS if q["step"] in ("core", "extras")}
    for gone in ("bp_sugar_check", "cervical_screen", "midlife_changes", "urinary_changes", "tobacco", "last_eye_exam", "screen_hours"):
        assert gone not in first_run and ob.BY_ID[gone]["step"] == "later", gone
    for dropped in ("family_history", "alcohol_freq", "alcohol_amount", "alcohol_heavy", "eyes", "feeling_lately", "mind_check", "mind_note", "helps", "sleep_hours", "goals"):
        assert dropped not in ob.BY_ID, dropped


def test_answers_from_the_longer_bank_carry_over_only_where_they_still_mean_the_same_thing():
    old = {"preferred_name": "Riya", "birth_date": born(30), "body": "female", "language": "english", "goals": ["pregnancy", "food", "sleep"],
           "conditions": ["none"], "sleep_hours": 5.5, "family_history": ["cancer"], "ai_consent": "yes", "tone": "calm_direct"}
    out = ob.migrate_legacy(old)
    assert out["main_goal"] == "food" and out["conditions_any"] == "no" and "conditions" not in out and out["sleep_pattern"] == "under_6"
    assert out["tone"] == "calm_direct" and not set(out) & {"family_history", "ai_consent", "goals", "sleep_hours"}
    assert ob.migrate_legacy({"conditions": ["diabetes"], "sleep_hours": 8})["conditions_any"] == "yes"
    assert ob.migrate_legacy({"conditions": ["prefer_not"]})["conditions_any"] == "prefer_not"
    assert ob.migrate_legacy({"sleep_hours": 8})["sleep_pattern"] == "seven_eight" and ob.migrate_legacy({"sleep_hours": 9})["sleep_pattern"] == "over_8"


# --- validation ---------------------------------------------------------------------------------------------------------------

def test_required_questions_are_the_only_ones_that_cannot_be_skipped():
    assert ob.required_missing({}, TODAY) == list(ob.REQUIRED)
    assert ob.required_missing(base(), TODAY) == []
    for qid in ("stress_level", "periods"):
        with pytest.raises(ob.AnswerError):
            ob.apply_answers(base(), {qid: None}, TODAY)
    answers, _d, skipped = ob.apply_answers(base(), {"activity": "light", "recent_blood_test": None, "tone": None}, TODAY)
    assert answers["activity"] == "light" and skipped == ["recent_blood_test", "tone"]
    male, _d, _s = ob.apply_answers(base("male"), {"stress_level": "often"}, TODAY)
    assert male["stress_level"] == "often"


@pytest.mark.parametrize("qid,value", [
    ("body", "robot"), ("main_goal", "pregnancy"), ("main_goal", ["sleep"]), ("conditions_any", "maybe"), ("sleep_pattern", 7), ("sleep_pattern", "nine"),
    ("stress_level", "extreme"), ("screen_hours", 30), ("conditions", ["diabetes"]),
    ("birth_date", "2026-13-40"), ("birth_date", "1800-01-01"), ("birth_date", "2999-01-01"), ("preferred_name", ""), ("preferred_name", "x" * 41),
    ("height_weight", {"height_cm": 20}), ("height_weight", {"colour": 1}), ("conditions", "diabetes"), ("tone", "angry"),
])
def test_bad_answers_are_refused(qid, value):
    with pytest.raises(ob.AnswerError):
        ob.apply_answers(base(), {qid: value}, TODAY)


def test_html_and_control_characters_never_reach_storage():
    answers, *_ = ob.apply_answers(base(), {"preferred_name": "  <b>Riya</b>\u0000  Sen "}, TODAY)
    assert answers["preferred_name"] == "bRiya/b Sen" or "<" not in answers["preferred_name"]


def test_none_of_these_stands_alone():
    answers, *_ = ob.apply_answers(base(), {"avoid_topics": ["weight", "none"]}, TODAY)
    assert answers["avoid_topics"] == ["none"]
    picked, *_ = ob.apply_answers(base(conditions_any="yes"), {"conditions": ["diabetes", "thyroid"]}, TODAY)
    assert picked["conditions"] == ["diabetes", "thyroid"]


def test_a_question_that_does_not_apply_is_refused():
    with pytest.raises(ob.AnswerError):
        ob.apply_answers(base("male"), {"periods": "regular"}, TODAY)


def test_changing_the_body_drops_answers_that_no_longer_apply_all_the_way_down():
    a = base("female", 32, periods="not_now", periods_reason="pregnant", due_date=(TODAY + timedelta(days=90)).isoformat(), main_goal="cycle", avoid_topics=["periods", "weight"])
    out, dropped, _ = ob.apply_answers(a, {"body": "male"}, TODAY)
    gone = {"periods", "periods_reason", "due_date", "main_goal"}
    assert not set(out) & gone and gone <= set(dropped)
    assert out["avoid_topics"] == ["weight"]                      # only the options that no longer apply were removed


def test_dates_are_checked_against_their_own_window():
    ok, *_ = ob.apply_answers(base(periods="regular"), {"last_period": (TODAY - timedelta(days=20)).isoformat()}, TODAY)
    assert ok["last_period"]
    for qid, value, extra in (("last_period", (TODAY - timedelta(days=200)).isoformat(), {"periods": "regular"}),
                              ("last_period", (TODAY + timedelta(days=2)).isoformat(), {"periods": "regular"}),
                              ("due_date", (TODAY - timedelta(days=2)).isoformat(), {"periods": "not_now", "periods_reason": "pregnant"})):
        with pytest.raises(ob.AnswerError):
            ob.apply_answers(base(**extra), {qid: value}, TODAY)


# --- the experience profile ----------------------------------------------------------------------------------------------------

def test_each_body_gets_the_right_map_and_menu():
    f = ob.build_experience(base("female"), TODAY)
    assert f["body_map"] == {"visible": True, "anatomy": "female", "reproductive": "uterus_ovaries"} and "cycle" in f["sections"]["visible"]
    m = ob.build_experience(base("male"), TODAY)
    assert m["body_map"] == {"visible": True, "anatomy": "male", "reproductive": "none"} and m["sections"]["hidden"] == ["cycle"] and m["cycle"]["visible"] is False
    for body in ("other", "prefer_not"):
        e = ob.build_experience(base(body), TODAY)
        assert e["body_map"] == {"visible": True, "anatomy": "neutral", "reproductive": "by_use"} and "cycle" in e["sections"]["visible"]
    t = ob.build_experience(base("trans"), TODAY)
    assert t["body_map"]["visible"] is False and "cycle" in t["sections"]["visible"]


def test_cycle_mode_follows_what_she_told_us():
    assert ob.build_experience(base(periods="regular"), TODAY)["cycle"]["mode"] == "track"
    for reason, mode in (("pregnant", "pregnancy"), ("recently_gave_birth", "postpartum"), ("breastfeeding", "postpartum"), ("contraception", "birth_control"), ("menopause", "perimenopause")):
        assert ob.build_experience(base(periods="not_now", periods_reason=reason), TODAY)["cycle"]["mode"] == mode
    assert ob.build_experience(base(pregnancy_plans="trying"), TODAY)["cycle"]["mode"] == "conceive"


def test_weight_and_calorie_numbers_stay_hidden_when_asked_or_when_pregnant():
    assert ob.build_experience(base(avoid_topics=["weight"]), TODAY)["fitness"] == {"formula_basis": "female", "deficits_allowed": False, "hide_numbers": True}
    assert ob.build_experience(base(periods="not_now", periods_reason="pregnant"), TODAY)["fitness"]["deficits_allowed"] is False
    assert ob.build_experience(base(), TODAY)["fitness"]["deficits_allowed"] is True
    assert ob.build_experience(base("male"), TODAY)["fitness"]["formula_basis"] == "male"
    assert ob.build_experience(base("prefer_not"), TODAY)["fitness"]["formula_basis"] == "average"


def test_the_care_checklist_follows_age_body_and_answers_and_is_worded_as_a_suggestion():
    e = ob.build_experience(base("female", 34, bp_sugar_check="longer_or_never", cervical_screen="never", tobacco=["chew"]), TODAY)
    assert {i["id"] for i in e["care_checklist"]} == {"bp_sugar", "cervical_screening", "oral_check"}
    assert all("worth" in i["why"] for i in e["care_checklist"]) and not any("diagnos" in i["why"].lower() for i in e["care_checklist"])
    assert ob.build_experience(base("female", 34, bp_sugar_check="within_year", cervical_screen="last_5_years"), TODAY)["care_checklist"] == []
    assert not [i for i in ob.build_experience(base("male", 34, bp_sugar_check="not_sure"), TODAY)["care_checklist"] if "cervical" in i["id"]]
    d = ob.build_experience(base(conditions_any="yes", conditions=["diabetes"], last_eye_exam="longer"), TODAY)
    assert "eye_exam_diabetes" in {i["id"] for i in d["care_checklist"]}
    assert "eye_exam_diabetes" not in {i["id"] for i in ob.build_experience(base(conditions_any="yes", conditions=["diabetes"], last_eye_exam="within_year"), TODAY)["care_checklist"]}
    text = " ".join(i["why"] + i["source"] for i in e["care_checklist"] + d["care_checklist"])
    for name in ("NP-NCD", "ADA", "Guidelines", "national screening"):
        assert name not in text, name


def test_body_map_focus_and_trackers_come_from_what_was_said_not_inferred():
    e = ob.build_experience(base(conditions_any="yes", conditions=["diabetes", "high_bp"], screen_hours=8, tobacco=["smoke"], main_goal="stress_mood"), TODAY)
    assert e["body_map_focus"][:2] == ["pancreas", "eyes"] and "lungs" in e["body_map_focus"]
    assert [t["tracker"] for t in e["trackers_suggested"]][:2] == ["mood", "mind"] and "eyes" in {t["tracker"] for t in e["trackers_suggested"]}
    assert e["goal"] == "stress_mood" and e["mind"]["offer_checkin"] is True
    quiet = ob.build_experience(base(), TODAY)
    assert quiet["body_map_focus"] == [] and quiet["care_checklist"] == []


def test_a_male_body_is_never_offered_the_cycle_tracker():
    e = ob.build_experience(base("male"), TODAY)
    assert "cycle" not in {t["tracker"] for t in e["trackers_suggested"]}


def test_sleep_and_stress_answers_move_the_trackers_and_the_mind_check_in():
    short = ob.build_experience(base(main_goal="food", sleep_pattern="under_6", stress_level="most_days", takes_medicines="yes"), TODAY)
    names = [t["tracker"] for t in short["trackers_suggested"]]
    assert names[:2] == ["nutrition", "hydration"] and {"sleep", "mood", "medications"} <= set(names)
    assert short["mind"]["offer_checkin"] is True
    calm = ob.build_experience(base(main_goal="food", sleep_pattern="over_8", stress_level="low"), TODAY)
    assert "sleep" not in {t["tracker"] for t in calm["trackers_suggested"]} and calm["mind"]["offer_checkin"] is False


def test_setup_lines_only_say_what_the_profile_does():
    lines = ob.setup_lines(ob.build_experience(base("male", language="hinglish", tone="calm_direct", avoid_topics=["weight"]), TODAY))
    text = " | ".join(lines)
    assert "male body" in text and "Cycle and period tracking are tucked away" in text and "calmly and directly in Hinglish" in text and "Weight and calorie numbers stay out of sight" in text
    assert "Cycle tracking is on" not in text
    assert "switched off" in " | ".join(ob.setup_lines(ob.build_experience(base("trans"), TODAY)))


# --- the API -------------------------------------------------------------------------------------------------------------------

USER = "00000000-0000-0000-0000-0000000000aa"
H = {"Authorization": "Bearer tok"}


@pytest.fixture()
def api():
    import onboarding_api
    db = FakeDB({"tok": USER})

    def get_user(authorization):
        if authorization != "Bearer tok":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid token")
        return SimpleNamespace(id=USER)

    app = FastAPI()
    app.include_router(onboarding_api.build_router(get_user, db))
    return TestClient(app), db


def put(client, answers, **extra):
    return client.put("/onboarding/answers", json={"answers": answers, **extra}, headers=H)


def test_every_route_needs_a_sign_in(api):
    client, _ = api
    for method, path in (("get", "/onboarding/questions"), ("get", "/onboarding/state"), ("put", "/onboarding/answers"), ("post", "/onboarding/complete"), ("get", "/experience")):
        assert getattr(client, method)(path, **({"json": {"answers": {}}} if method == "put" else {})).status_code == 401, path


def test_the_bank_is_served_with_its_rules(api):
    client, _ = api
    body = client.get("/onboarding/questions", headers=H).json()
    assert body["status"] == "success" and body["required"] == list(ob.REQUIRED) and len(body["questions"]) == len(ob.QUESTIONS) and body["min_age"] == 18 and body["screens"] == ob.SCREENS


def test_a_new_person_starts_empty_and_resumes_where_they_left_off(api):
    client, _ = api
    s = client.get("/onboarding/state", headers=H).json()
    assert s["complete"] is False and s["answers"] == {} and s["required_missing"] == list(ob.REQUIRED)
    assert s["visible"][:3] == ["body", "language", "birth_date"]
    r = put(client, {"body": "female", "birth_date": born(32), "preferred_name": "Riya"}, step=1)
    assert r.status_code == 200
    again = client.get("/onboarding/state", headers=H).json()
    assert again["step"] == 1 and again["answers"]["body"] == "female" and "periods" in again["visible"]
    assert again["required_missing"] == ["language", "main_goal", "conditions_any", "sleep_pattern", "stress_level", "periods"]


def test_a_skipped_optional_question_is_recorded_and_a_bad_answer_names_the_field(api):
    client, _ = api
    put(client, {"preferred_name": "Riya", "birth_date": born(32), "body": "male"})
    assert put(client, {"tone": None}).json()["skipped"] == ["tone"]
    bad = put(client, {"periods": "regular"})
    assert bad.status_code == 422 and bad.json()["detail"]["field"] == "periods"
    assert put(client, {"mystery": 1}).status_code == 422


def test_changing_the_body_drops_the_answers_that_no_longer_apply(api):
    client, _ = api
    put(client, {"preferred_name": "Riya", "birth_date": born(32), "body": "female", "periods": "regular"})
    r = put(client, {"body": "male"}).json()
    assert "periods" in r["dropped"] and "periods" not in r["answers"]


def test_under_eighteen_stores_nothing_but_the_gate(api):
    client, db = api
    r = put(client, {"preferred_name": "Sam"})
    assert r.status_code == 422 and r.json()["detail"]["field"] == "birth_date"
    r = put(client, {"birth_date": born(16), "body": "male", "preferred_name": "Sam"}).json()
    assert r == {"status": "success", "under_18": True}
    state = client.get("/onboarding/state", headers=H).json()
    assert state["under_18"] is True and state["answers"] == {} and state["complete"] is False
    assert put(client, {"language": "english"}).status_code == 403
    assert client.post("/onboarding/complete", headers=H).status_code == 403
    import doc_store
    stored = doc_store.get(db, USER, "onboarding", "v1")
    assert set(stored) == {"age_gate", "at", "bank_version"}


def test_crisis_words_in_free_text_are_answered_and_never_stored(api):
    client, _ = api
    put(client, {"preferred_name": "Riya", "birth_date": born(32), "body": "female"})
    r = put(client, {"conditions_any": "yes", "conditions": ["other"], "conditions_other": "I want to end my life tonight"}).json()
    assert r["safety"]["field"] == "conditions_other" and "findahelpline" in r["safety"]["message"] or "988" in r["safety"]["message"]
    assert "conditions_other" not in client.get("/onboarding/state", headers=H).json()["answers"]
    fine = put(client, {"conditions_other": "Migraines on and off"}).json()
    assert fine["safety"] is None and fine["answers"]["conditions_other"] == "Migraines on and off"


def test_completing_needs_every_required_answer(api):
    client, _ = api
    put(client, {"preferred_name": "Riya", "birth_date": born(32)})
    r = client.post("/onboarding/complete", headers=H)
    assert r.status_code == 422 and set(r.json()["detail"]["missing"]) == {"body", "language", "main_goal", "conditions_any", "sleep_pattern", "stress_level"}


def finish(client, **more):
    answers = base(**more) if more else base()
    put(client, answers)
    return client.post("/onboarding/complete", headers=H)


def test_completing_a_female_profile_sets_up_cycle_conditions_and_the_body_profile(api):
    client, db = api
    import doc_store
    answers = base("female", 32, periods="regular", conditions_any="yes", conditions=["diabetes", "pcos"], allergies="yes", allergy_types=["food"],
                   height_weight={"height_cm": 160, "weight_kg": 58}, activity="light", diet_style="vegetarian", tone="calm_direct", language="hinglish")
    put(client, answers)
    out = client.post("/onboarding/complete", headers=H)
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["status"] == "success" and body["experience"]["body_map"]["anatomy"] == "female" and body["applied"]
    assert any("female body" in a["label"] for a in body["applied"])
    assert client.get("/onboarding/state", headers=H).json()["complete"] is True
    assert client.get("/experience", headers=H).json()["experience"]["version"] == ob.BANK_VERSION
    profile = doc_store.get(db, USER, "profile", "me")
    assert profile["formula_basis"] == "female" and profile["height_cm"] == 160 and profile["menstruating"] is True and profile["diet_style"] == "vegetarian"
    assert doc_store.get(db, USER, "cycle_settings", "main")["mode"] == "track"
    import consent
    assert consent.has_ai_consent(db, USER) is False, "setup never switches a consent on: the Your choices step does that"
    names = sorted(r["condition_name"] for r in db.tables.get("medical_conditions", [])) if hasattr(db, "tables") else None
    if names is not None:
        assert names == ["Diabetes", "PCOS or PCOD"]


def test_a_male_profile_gets_no_cycle_setup_and_running_setup_twice_changes_nothing(api):
    client, db = api
    import doc_store
    put(client, base("male", 40))
    first = client.post("/onboarding/complete", headers=H).json()
    second = client.post("/onboarding/complete", headers=H).json()
    assert first["experience"]["sections"]["hidden"] == ["cycle"] and first["experience"] == second["experience"]
    assert doc_store.get(db, USER, "cycle_settings", "main") is None


def test_a_trans_profile_turns_the_body_map_off_and_a_prefer_not_profile_keeps_the_general_body(api):
    client, _ = api
    put(client, base("trans", 30))
    assert client.post("/onboarding/complete", headers=H).json()["experience"]["body_map"]["visible"] is False
    put(client, {"body": "prefer_not"})
    again = client.post("/onboarding/complete", headers=H).json()["experience"]["body_map"]
    assert again == {"visible": True, "anatomy": "neutral", "reproductive": "by_use"}


def test_setup_documents_are_exported_and_deleted_with_the_rest(api):
    client, db = api
    import data_rights
    import doc_store
    put(client, base("male", 40))
    client.post("/onboarding/complete", headers=H)
    kinds = {d["kind"] for d in data_rights.export_documents(db, USER)}
    assert {"onboarding", "experience"} <= kinds
    doc_store.delete_everything(db, USER)
    assert doc_store.get(db, USER, "onboarding", "v1") is None and doc_store.get(db, USER, "experience", "main") is None


# --- the tour, the age gate and the old bank --------------------------------------------------------------------------------------

def test_the_tour_is_remembered_once_seen_and_skipping_is_recorded(api):
    client, db = api
    assert client.get("/onboarding/tour", headers=H).json() == {"status": "success", "seen": False, "skipped": False, "at": None}
    first = client.put("/onboarding/tour", json={}, headers=H).json()
    assert first["seen"] is True and first["skipped"] is False and first["at"]
    skipped = client.put("/onboarding/tour", json={"skipped": True}, headers=H).json()
    assert skipped["skipped"] is True and skipped["at"] == first["at"]
    assert client.get("/onboarding/tour", headers=H).json()["seen"] is True
    assert client.put("/onboarding/tour", json={"skipped": "yes"}, headers=H).status_code == 422
    import doc_store
    assert set(doc_store.get(db, USER, "tour", "v1")) == {"seen", "at", "skipped"}


def test_the_tour_routes_need_a_sign_in(api):
    client, _ = api
    assert client.get("/onboarding/tour").status_code == 401
    assert client.put("/onboarding/tour", json={}).status_code == 401


def test_nothing_is_stored_before_the_age_is_known_and_a_known_young_age_blocks_everything(api):
    client, db = api
    import doc_store
    r = put(client, {"body": "female", "preferred_name": "Sam"})
    assert r.status_code == 422 and r.json()["detail"]["field"] == "birth_date"
    assert doc_store.get(db, USER, "onboarding", "v1") is None
    # body and date of birth in one request: the gate runs on the date, then everything is stored together
    ok = put(client, {"body": "male", "birth_date": born(30), "language": "hinglish"})
    assert ok.status_code == 200 and ok.json()["answers"]["body"] == "male"
    assert put(client, {"body": "female", "birth_date": born(15)}).json() == {"status": "success", "under_18": True}
    assert set(doc_store.get(db, USER, "onboarding", "v1")) == {"age_gate", "at", "bank_version"}


def test_someone_who_finished_setup_under_the_longer_bank_is_not_sent_back(api):
    client, db = api
    import doc_store
    old = {"preferred_name": "Riya", "birth_date": born(32), "body": "female", "language": "english", "goals": ["sleep"], "conditions": ["none"], "tone": "gentle_warm",
           "ai_consent": "yes", "family_history": ["cancer"]}
    doc_store.put(db, USER, "onboarding", "v1", {"answers": old, "completed_at": "2026-10-01T00:00:00+00:00", "bank_version": "2026-10a", "step": 9})
    state = client.get("/onboarding/state", headers=H).json()
    assert state["complete"] is True and state["bank_changed"] is True
    assert state["answers"]["main_goal"] == "sleep" and state["answers"]["conditions_any"] == "no" and "ai_consent" not in state["answers"]
    assert "family_history" not in state["answers"]
    # saving anything again writes the cleaned answers and drops the old bundled consent answer
    assert put(client, {"activity": "light"}).status_code == 200
    stored = doc_store.get(db, USER, "onboarding", "v1")["answers"]
    assert "ai_consent" not in stored and "goals" not in stored and stored["activity"] == "light"


def test_running_setup_again_never_turns_a_consent_on_from_an_old_answer(api):
    client, db = api
    import consent
    import doc_store
    doc_store.put(db, USER, "onboarding", "v1", {"answers": {**base("male", 40), "ai_consent": "yes"}, "completed_at": "2026-10-01T00:00:00+00:00", "bank_version": "2026-10a"})
    assert client.post("/onboarding/complete", headers=H).status_code == 200
    assert consent.has_ai_consent(db, USER) is False


# --- the browser mirrors these rules --------------------------------------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[2] / "frontend" / "app" / "onboarding" / "bank.fixture.json"


def _parity_fixture() -> dict:
    """The bank plus cases the browser's rule evaluator must reproduce exactly (frontend/app/onboarding/flow.test.ts)."""
    cases = []
    today = TODAY
    for body in (None, "female", "male", "trans", "other", "prefer_not"):
        for age in (17, 18, 30, 40, 45, 51, 56, 66):
            for extra in ({}, {"periods": "not_now", "periods_reason": "pregnant"}, {"periods": "regular"}, {"conditions_any": "yes"}, {"conditions_any": "yes", "conditions": ["other"]},
                          {"allergies": "yes"}, {"drains": ["something_else"]}):
                answers = {k: v for k, v in {"birth_date": born(age), "body": body, **extra}.items() if v is not None}
                options = {q["id"]: [o["id"] for o in ob.visible_options(q, answers, today)] for q in ob.QUESTIONS if any(o.get("show_if") for o in q.get("options", []))}
                cases.append({"answers": answers, "visible": ob.visible_ids(answers, today), "options": options})
    return {"today": today.isoformat(), "steps": ob.STEPS, "screens": ob.SCREENS, "questions": ob.QUESTIONS, "titles_hi": ob.TITLES_HI, "cases": cases}


def test_the_browser_fixture_matches_the_server_bank():
    import json
    import os
    fresh = json.dumps(_parity_fixture(), separators=(",", ":"), sort_keys=True)
    if os.environ.get("UPDATE_FIXTURE") == "1" or not FIXTURE.exists():
        FIXTURE.write_text(fresh + "\n", encoding="utf-8")
    assert FIXTURE.read_text(encoding="utf-8").strip() == fresh.strip(), "run: UPDATE_FIXTURE=1 python -m pytest tests/test_onboarding.py -k fixture"


# --- how the companion is told to talk ---------------------------------------------------------------------------------------------

def test_the_companion_style_block_carries_only_style():
    e = ob.build_experience(base(tone="calm_direct", reply_length="detailed", language="hinglish", avoid_topics=["weight", "periods"],
                                 conditions=["diabetes"], drains=["money"], support_people=["mostly_on_my_own"]), TODAY)
    block = ob.style_block(e)
    assert "calm and direct" in block and "160 words" in block and "Hinglish" in block and "their weight" in block and "periods" in block
    for private in ("diabetes", "money", "alone", "Riya", "1994"):
        assert private.lower() not in block.lower()
    assert ob.style_block(None) == "" and ob.style_block({}) == ""


def test_a_default_style_still_says_how_long_to_reply_and_names_nothing_to_avoid():
    block = ob.style_block(ob.build_experience(base(), TODAY))
    assert "short" in block and "Do not bring up" not in block and "Language" not in block


def test_the_chat_prompt_gets_the_style_after_setup_and_nothing_before(api):
    client, db = api
    import onboarding_api
    assert onboarding_api.style_block_for(db, USER) == ""
    put(client, base("female", 32, tone="cheerful_playful"))
    client.post("/onboarding/complete", headers=H)
    assert "cheerful" in onboarding_api.style_block_for(db, USER)
