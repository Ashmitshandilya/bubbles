"""WP7.1: the Stars lens works out signs from files on the server, says when it cannot be sure, only claims a match when the person's own
evidence agrees, and deletes the birth details when it is turned off or consent is withdrawn."""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import consent  # noqa: E402
import doc_store  # noqa: E402
import person_model as pm  # noqa: E402
import stars_lens as sl  # noqa: E402
import understanding_api  # noqa: E402
from fake_db import FakeDB, grant_consent  # noqa: E402

U = "00000000-0000-0000-0000-00000000000a"
H = {"Authorization": "Bearer ta"}
NOW = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)


def delhi():
    return sl.city(sl.search_cities("delhi")[0]["id"])


# ---- places ----
def test_the_city_list_has_indian_cities_and_capitals_and_search_works():
    names = {c["name"] for c in sl._cities()}
    assert {"Mumbai", "Delhi", "Pune", "Kochi", "London", "Washington, D.C.", "Canberra"} <= names
    assert [p["name"] for p in sl.search_cities("pun")][:1] == ["Pune"]
    assert sl.search_cities("x") == [] and sl.search_cities("zzzzzz") == []
    ids = [c["id"] for c in sl._cities()]
    assert len(ids) == len(set(ids))


# ---- charts ----
def test_a_chart_with_a_time_names_moon_sun_and_ascendant():
    chart = sl.compute_chart(date(1999, 3, 14), "06:30", delhi())
    assert chart["time_known"] and chart["ascendant"]["rashi"] in sl.RASHI
    assert chart["moon"]["rashi"] == "Makara" and chart["moon"]["nakshatra"] == "Shravana" and 1 <= chart["moon"]["pada"] <= 4
    assert chart["sun"]["rashi"] == "Kumbha"          # the Sun is in the sidereal sign Aquarius in mid March


def test_without_a_time_it_says_which_it_could_have_been():
    chart = sl.compute_chart(date(1999, 3, 14), None, delhi())
    assert not chart["time_known"] and chart["ascendant"] is None
    assert chart["moon"]["nakshatra_options"] == ["Uttara Ashadha", "Shravana"] and chart["moon"]["cusp"] is True
    assert chart["moon"]["pada"] is None


def test_a_day_that_stays_in_one_sign_is_not_a_cusp():
    chart = sl.compute_chart(date(1999, 3, 14), None, delhi())
    assert chart["moon"]["rashi_options"] == ["Makara"] and chart["sun"]["rashi_options"] == ["Kumbha"]


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError):
        sl.compute_chart(date(1850, 1, 1), "06:30", delhi())
    with pytest.raises(ValueError):
        sl.compute_chart(date(1999, 3, 14), "25:99", delhi())


def test_the_ascendant_changes_with_the_birth_time():
    a = sl.compute_chart(date(1999, 3, 14), "06:30", delhi())["ascendant"]["rashi"]
    b = sl.compute_chart(date(1999, 3, 14), "18:30", delhi())["ascendant"]["rashi"]
    assert a != b


# ---- words and matching ----
def test_uncertain_placements_list_both_and_map_to_nothing():
    chart = sl.compute_chart(date(1999, 3, 14), None, delhi())
    assert all(a["maps_to"] is None for a in sl.associations(chart) if a["uncertain"])
    assert any(a["uncertain"] for a in sl.associations(chart))


def _chart_with_moon(rashi: str):
    return {"moon": {"rashi": rashi, "nakshatra": "Pushya", "rashi_options": [rashi], "nakshatra_options": ["Pushya"]},
            "sun": {"rashi": "Tula", "rashi_options": ["Tula"]}, "ascendant": None, "time_known": True, "place": {"name": "x", "country": "y"}}


def test_a_match_needs_the_persons_own_evidence_not_the_stars():
    model = pm.new_model()
    chart = _chart_with_moon("Karka")          # "feels things deeply" -> reassurance_need: high
    sl.apply_priors(model, chart, NOW)
    item = next(i for i in sl.view(chart, model, NOW)["items"] if i["text"] == "feels things deeply")
    assert item["match"] == "Not enough to tell"            # only a 0.2 prior so far: it cannot decide anything
    pm.add_evidence(model, "reassurance_need", "high", "orbit_checkin", "orbit_checkin", 3.0, NOW)
    assert next(i for i in sl.view(chart, model, NOW)["items"] if i["text"] == "feels things deeply")["match"] == "Matches what we've seen"
    model2 = pm.new_model()
    pm.add_evidence(model2, "reassurance_need", "usual", "orbit_checkin", "orbit_checkin", 3.0, NOW)
    assert next(i for i in sl.view(chart, model2, NOW)["items"] if i["text"] == "feels things deeply")["match"] == "Not what we've seen"


def test_priors_are_light_and_can_be_cleared():
    model = pm.new_model()
    assert sl.apply_priors(model, _chart_with_moon("Karka"), NOW) == 1
    ev = model["traits"]["reassurance_need"]["evidence"]
    assert ev[0]["weight"] == 0.2 and ev[0]["prior"] is True and ev[0]["source"] == "stars"
    reading = pm.resolve("reassurance_need", model["traits"]["reassurance_need"], NOW)
    assert reading["used"] is False                         # a prior alone is never used
    sl.clear_priors(model)
    assert "reassurance_need" not in model["traits"] or not model["traits"]["reassurance_need"]["evidence"]


def test_every_rashi_and_nakshatra_has_words_and_the_copy_is_calm():
    data = sl._traits()
    assert set(data["rashi"]) == set(sl.RASHI) and set(data["nakshatra"]) == set(sl.NAKSHATRA)
    text = repr(data).lower()
    for banned in ("will happen", "doom", "dosha", "bad period", "gemstone", "marry", "illness", "disease", "you will"):
        assert banned not in text
    for r in data["rashi"].values():
        for item in r["items"]:
            m = item["maps_to"]
            assert m is None or m["value"] in pm.TRAITS[m["trait"]]["values"]


# ---- the API ----
@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "stars-test-key")
    db = FakeDB({"ta": U})
    app = FastAPI()

    def get_user(authorization):
        uid = db.auth.tokens.get((authorization or "").removeprefix("Bearer ").strip())
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return type("U", (), {"id": uid})()

    app.include_router(understanding_api.build_router(get_user, db))
    pm.forget(U)
    return TestClient(app), db


BODY = {"birth_date": "1999-03-14", "birth_time": "06:30"}


def _place_id():
    return delhi()["id"]


def test_it_is_off_until_the_person_says_yes(api):
    c, db = api
    s = c.get("/me/stars", headers=H).json()
    assert s["enabled"] is False and s["consent"] is False and "traditional" in s["intro"].lower()
    assert c.put("/me/stars", json={**BODY, "city_id": _place_id()}, headers=H).status_code == 403
    assert doc_store.get(db, U, sl.KIND, sl.KEY) is None


def test_save_show_and_turn_off(api):
    c, db = api
    grant_consent(db, U, "stars_lens")
    r = c.put("/me/stars", json={**BODY, "city_id": _place_id()}, headers=H)
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["chart"]["moon"]["rashi"] == "Makara"
    assert all(i["match"] in ("Matches what we've seen", "Not what we've seen", "Not enough to tell") for i in r.json()["items"])
    off = c.delete("/me/stars", headers=H).json()
    assert off["enabled"] is False
    assert doc_store.get(db, U, sl.KIND, sl.KEY) is None


def test_withdrawing_consent_deletes_the_birth_details_and_the_hints(api):
    c, db = api
    grant_consent(db, U, "stars_lens")
    c.put("/me/stars", json={**BODY, "birth_date": "1999-07-02", "city_id": _place_id()}, headers=H)
    consent.set_purpose(db, U, "stars_lens", False)
    assert doc_store.get(db, U, sl.KIND, sl.KEY) is None
    pm.forget(U)
    model = pm.load(db, U, fresh=True)
    assert all(e.get("source") != "stars" for t in model["traits"].values() for e in t["evidence"])


def test_bad_inputs_get_plain_errors(api):
    c, db = api
    grant_consent(db, U, "stars_lens")
    pid = _place_id()
    assert c.put("/me/stars", json={"birth_date": "nope", "city_id": pid}, headers=H).status_code == 422
    assert c.put("/me/stars", json={"birth_date": "2999-01-01", "city_id": pid}, headers=H).status_code == 422
    assert c.put("/me/stars", json={**BODY, "city_id": "nowhere"}, headers=H).status_code == 422
    assert c.put("/me/stars", json={**BODY, "birth_time": "99:99", "city_id": pid}, headers=H).status_code == 422
    assert c.put("/me/stars", json={"birth_date": "1850-01-01", "city_id": pid}, headers=H).status_code == 422


def test_places_search_and_sign_in(api):
    c, _ = api
    assert [p["name"] for p in c.get("/me/stars/places?q=mumb", headers=H).json()["places"]][:1] == ["Mumbai"]
    assert c.get("/me/stars").status_code == 401 and c.get("/me/stars/places?q=mu").status_code == 401


def test_no_birth_time_means_no_ascendant_and_cusp_options(api):
    c, db = api
    grant_consent(db, U, "stars_lens")
    r = c.put("/me/stars", json={"birth_date": "1999-03-14", "city_id": _place_id()}, headers=H).json()
    assert r["chart"]["ascendant"] is None and r["chart"]["time_known"] is False
    assert len(r["chart"]["moon"]["nakshatra_options"]) == 2
