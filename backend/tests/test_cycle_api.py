"""/cycle/* through a real FastAPI app with the stateful fake database: auth, ownership (IDOR), validation, safety, privacy."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta as td, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import clinical_constants as K  # noqa: E402
import cycle_api  # noqa: E402
import doc_store  # noqa: E402
from db_access import register_db_error_handlers  # noqa: E402
from fake_db import FakeDB, permission_denied  # noqa: E402

A, B = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
HA, HB = {"Authorization": "Bearer ta"}, {"Authorization": "Bearer tb"}
TODAY = datetime.now(timezone.utc).date()


def iso(d: date) -> str:
    return d.isoformat()


@pytest.fixture()
def env():
    db = FakeDB({"ta": A, "tb": B})
    app = FastAPI()
    register_db_error_handlers(app)

    def get_user(authorization):
        token = (authorization or "").removeprefix("Bearer ").strip()
        uid = db.auth.tokens.get(token)
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return type("U", (), {"id": uid})()

    app.include_router(cycle_api.build_router(get_user, db))
    client = TestClient(app, raise_server_exceptions=False)
    return client, db


def start_periods(client, headers, lengths, last_ago=5):
    days = [TODAY - td(days=last_ago)]
    for n in reversed(lengths):
        days.insert(0, days[0] - td(days=n))
    for d in days:
        r = client.post("/cycle/period/start", json={"date": iso(d)}, headers=headers)
        assert r.status_code == 200, r.text
    return days


def detail_is_text(response):
    body = response.json()
    assert isinstance(body.get("detail"), str), body


# ---- auth ------------------------------------------------------------------------------------------------------------

ROUTES = [("get", "/cycle/overview"), ("get", "/cycle/calendar?month=2026-10"), ("get", "/cycle/day/2026-10-01"), ("put", "/cycle/day/2026-10-01"),
          ("post", "/cycle/period/start"), ("post", "/cycle/period/end"), ("get", "/cycle/settings"), ("put", "/cycle/settings"),
          ("get", "/cycle/insights"), ("get", "/cycle/report"), ("get", "/cycle/factors"), ("get", "/cycle/education"),
          ("get", "/cycle/partner-view"), ("post", "/cycle/partner-view"), ("delete", "/cycle/data?confirm=yes")]


@pytest.mark.parametrize("method,path", ROUTES)
def test_every_owner_route_requires_a_valid_token(env, method, path):
    client, _ = env
    kwargs = {"json": {}} if method in ("put", "post") else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers={"Authorization": "Bearer nope"}, **kwargs).status_code == 401


# ---- overview / period start / end -------------------------------------------------------------------------------------

def test_zero_data_overview_is_friendly(env):
    client, _ = env
    r = client.get("/cycle/overview", headers=HA)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "success" and body["mode"] == "track"
    assert body["has_data"] is False and body["next_period"] is None and body["cycle_day"] is None
    assert "first day of your last period" in body["empty_state"]
    assert any("not birth control" in n for n in body["notices"])
    assert body["confidence"] == "learning" and body["urgent"] is None and body["flags"] == []


def test_one_tap_period_start_today_updates_overview_and_writes_tracker_and_analytics(env):
    client, db = env
    r = client.post("/cycle/period/start", headers=HA)
    body = r.json()
    assert r.status_code == 200 and body["log"]["period_start"] is True and body["saved"] is True
    ov = body["overview"]
    assert ov["cycle_day"] == 1 and ov["phase"]["id"] == "menstrual" and ov["last_period_start"] == iso(TODAY) and ov["has_data"]
    assert ov["next_period"]["date"] == iso(TODAY + td(days=K.CYCLE_DEFAULT_LENGTH_DAYS)) and ov["confidence"] == "learning"
    assert [r_["start_date"] for r_ in db.rows("menstrual_cycles", user_id=A)] == [iso(TODAY)]
    events = [e for e in db.rows("extracted_health_events", user_id=A) if e["event_type"] == "menstrual_symptom"]
    assert events and events[0]["extracted_data"]["is_start"] is True
    # idempotent: tapping again changes nothing
    client.post("/cycle/period/start", headers=HA)
    assert len(db.rows("menstrual_cycles", user_id=A)) == 1
    assert len(doc_store.list_docs(db, A, "cycle_day")) == 1


def test_period_start_can_be_backfilled_and_future_dates_are_rejected(env):
    client, _ = env
    r = client.post("/cycle/period/start", json={"date": iso(TODAY - td(days=40))}, headers=HA)
    assert r.status_code == 200 and r.json()["overview"]["last_period_start"] == iso(TODAY - td(days=40))
    for bad in (iso(TODAY + td(days=5)), "2026-13-01", "yesterday", "2026-1-5", 20261001):
        r = client.post("/cycle/period/start", json={"date": bad}, headers=HA)
        assert r.status_code == 422, bad
        detail_is_text(r)
    assert client.post("/cycle/period/start", json={"nonsense": 1}, headers=HA).status_code == 422


def test_history_builds_predictions_with_ranges_and_confidence(env):
    client, _ = env
    days = start_periods(client, HA, [28] * 6)
    ov = client.get("/cycle/overview", headers=HA).json()
    assert ov["confidence"] == "high" and ov["stats"]["cycles_used"] == 6 and ov["stats"]["average_length"] == 28.0
    nxt = ov["next_period"]
    assert nxt["date"] == iso(days[-1] + td(days=28)) and nxt["earliest"] < nxt["date"] < nxt["latest"]
    assert ov["ovulation"]["source"] == "calendar" and ov["fertile_window"]["start"] < ov["fertile_window"]["end"]
    assert ov["weather"]["tone"] in {"bright", "steady", "heavier"} and ov["pms"]["personal"] is False
    assert ov["stats"]["regularity"]["score"] == 100


def test_period_end_needs_a_recent_start_and_sets_period_length(env):
    client, _ = env
    r = client.post("/cycle/period/end", headers=HA)
    assert r.status_code == 422
    detail_is_text(r)
    client.post("/cycle/period/start", json={"date": iso(TODAY - td(days=4))}, headers=HA)
    r = client.post("/cycle/period/end", headers=HA)
    assert r.status_code == 200 and r.json()["log"]["period_end"] is True
    cal = client.get(f"/cycle/calendar?month={TODAY:%Y-%m}", headers=HA).json()["days"]
    logged = [d["date"] for d in cal if d["period"] == "logged"]
    assert iso(TODAY - td(days=4)) in logged


def test_unmarking_a_start_removes_it_even_if_the_old_tracker_has_it(env):
    client, _ = env
    client.post("/cycle/period/start", headers=HA)
    log = client.get(f"/cycle/day/{iso(TODAY)}", headers=HA).json()["log"]
    client.put(f"/cycle/day/{iso(TODAY)}", json={**log, "period_start": False}, headers=HA)
    ov = client.get("/cycle/overview", headers=HA).json()
    assert ov["last_period_start"] is None


def test_works_when_the_live_database_denies_the_tracker_table(env):
    client, db = env
    db.failures["menstrual_cycles"] = permission_denied("menstrual_cycles")
    r = client.post("/cycle/period/start", headers=HA)
    assert r.status_code == 200 and r.json()["overview"]["cycle_day"] == 1
    assert client.get("/cycle/overview", headers=HA).status_code == 200


# ---- day log -------------------------------------------------------------------------------------------------------------

FULL_LOG = {"flow": "medium", "products": ["pad", "tampon"], "soaking_hourly": False, "pain_level": 5, "pain_types": ["cramps", "lower_back"],
            "energy": 2, "sleep_quality": 3, "factors": ["bloating", "irritable"], "custom_factors": ["new yoga class"],
            "discharge": "creamy", "sex": {"had": True, "protection": "condom"}, "ovulation_test": "negative", "pregnancy_test": "negative",
            "bbt_c": 36.45, "medications": ["ibuprofen"], "birth_control_taken": None, "period_start": False, "period_end": False,
            "notes": "Slept badly but okay."}


def test_put_then_get_day_round_trips_and_defaults_missing_fields(env):
    client, _ = env
    day = iso(TODAY - td(days=1))
    r = client.put(f"/cycle/day/{day}", json=FULL_LOG, headers=HA)
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True and body["safety"] is None and body["log"] == FULL_LOG and body["overview"]["status"] == "success"
    assert client.get(f"/cycle/day/{day}", headers=HA).json()["log"] == FULL_LOG
    r = client.put(f"/cycle/day/{day}", json={"flow": "light"}, headers=HA)
    log = r.json()["log"]
    assert log["flow"] == "light" and log["pain_level"] is None and log["factors"] == [] and log["period_start"] is False
    assert client.get(f"/cycle/day/{iso(TODAY - td(days=9))}", headers=HA).json()["log"] is None


@pytest.mark.parametrize("patch", [
    {"flow": "torrential"}, {"products": ["pad", "hat"]}, {"pain_level": 11}, {"pain_level": -1}, {"pain_level": 2.5}, {"pain_level": "7"},
    {"energy": 0}, {"energy": 6}, {"sleep_quality": 9}, {"bbt_c": 45}, {"bbt_c": 20}, {"bbt_c": "warm"}, {"bbt_c": True},
    {"factors": ["not_a_real_factor"]}, {"factors": "bloating"}, {"factors": ["bloating"] * 41}, {"custom_factors": [["x"]]},
    {"custom_factors": [str(i) for i in range(11)]}, {"discharge": "x"}, {"sex": {"had": "yes"}}, {"sex": {"had": True, "extra": 1}}, {"sex": "yes"},
    {"ovulation_test": "maybe"}, {"pregnancy_test": "x"}, {"soaking_hourly": "true"}, {"period_start": 1}, {"birth_control_taken": "yes"},
    {"notes": {"a": 1}}, {"medications": "ibuprofen"}, {"unknown_field": 1}, {"pain_types": ["toenail"]},
])
def test_invalid_day_logs_are_422_with_a_plain_string(env, patch):
    client, _ = env
    r = client.put(f"/cycle/day/{iso(TODAY)}", json=patch, headers=HA)
    assert r.status_code == 422, patch
    detail_is_text(r)
    assert "Traceback" not in r.text and "pydantic" not in r.text.lower()


@pytest.mark.parametrize("path", ["/cycle/day/not-a-date", "/cycle/day/2026-02-30", f"/cycle/day/{iso(TODAY + td(days=3))}", "/cycle/day/1980-01-01"])
def test_invalid_day_paths(env, path):
    client, _ = env
    for r in (client.put(path, json={}, headers=HA), ):
        assert r.status_code == 422
        detail_is_text(r)
    if path.endswith(("not-a-date", "2026-02-30")):
        assert client.get(path, headers=HA).status_code == 422


def test_malformed_bodies_are_422_and_oversized_bodies_413(env):
    client, _ = env
    day = f"/cycle/day/{iso(TODAY)}"
    for raw in (b"{not json", b"[1,2]", b'"text"', b""):
        r = client.put(day, content=raw, headers={**HA, "Content-Type": "application/json"})
        assert r.status_code == 422, raw
        detail_is_text(r)
    r = client.put(day, content=b'{"notes": "' + b"a" * 50_000 + b'"}', headers={**HA, "Content-Type": "application/json"})
    assert r.status_code == 413


def test_text_is_bounded_and_cleaned(env):
    client, _ = env
    r = client.put(f"/cycle/day/{iso(TODAY)}", json={"notes": "x" * 5000 + "\u0000", "custom_factors": ["a" * 100], "medications": ["m" * 200]}, headers=HA)
    log = r.json()["log"]
    assert len(log["notes"]) == 2000 and len(log["custom_factors"][0]) == 40 and len(log["medications"][0]) == 60


def test_urgent_note_returns_the_safety_response_with_no_cycle_chatter(env):
    client, db = env
    r = client.put(f"/cycle/day/{iso(TODAY)}", json={"flow": "heavy", "notes": "I have crushing chest pain right now"}, headers=HA)
    body = r.json()
    assert r.status_code == 200 and body["saved"] is True
    assert body["safety"]["state"] == "EMERGENCY" and "urgent medical help" in body["safety"]["message"]
    assert body["overview"] is None and body["flags"] == []
    assert client.get(f"/cycle/day/{iso(TODAY)}", headers=HA).json()["log"]["flow"] == "heavy"   # their record is still kept


def test_soaking_hourly_is_urgent_in_the_day_response_and_the_overview(env):
    client, _ = env
    start_periods(client, HA, [28] * 3, last_ago=1)
    r = client.put(f"/cycle/day/{iso(TODAY)}", json={"flow": "heavy", "soaking_hourly": True}, headers=HA).json()
    assert r["flags"][0]["severity"] == "urgent" and r["overview"]["urgent"]["id"] == "heavy_bleeding"
    assert "emergency" in r["overview"]["urgent"]["message"].lower()


def test_logging_creates_one_idempotent_analytics_event_per_day(env):
    client, db = env
    day = iso(TODAY - td(days=1))
    for _ in range(3):
        client.put(f"/cycle/day/{day}", json={"factors": ["bloating", "cramps"], "pain_level": 4}, headers=HA)
    events = [e for e in db.rows("extracted_health_events", user_id=A) if e["extracted_data"].get("_prov", {}).get("key") == f"cycle_day:{day}"]
    assert len(events) == 1 and events[0]["extracted_data"]["symptoms"] == ["Bloating", "Cramps"]
    client.put(f"/cycle/day/{day}", json={"energy": 3}, headers=HA)   # nothing notable any more
    assert not [e for e in db.rows("extracted_health_events", user_id=A) if e["extracted_data"].get("_prov", {}).get("key") == f"cycle_day:{day}"]


# ---- ownership -----------------------------------------------------------------------------------------------------------

def test_user_b_cannot_read_or_change_user_a_cycle_data(env):
    client, db = env
    start_periods(client, HA, [28] * 4)
    client.put(f"/cycle/day/{iso(TODAY - td(days=2))}", json=FULL_LOG, headers=HA)
    day = iso(TODAY - td(days=2))
    assert client.get(f"/cycle/day/{day}", headers=HB).json()["log"] is None
    ov_b = client.get("/cycle/overview", headers=HB).json()
    assert ov_b["has_data"] is False and ov_b["next_period"] is None
    assert client.get(f"/cycle/calendar?month={TODAY:%Y-%m}", headers=HB).json()["days"][0]["has_log"] is False
    report_b = client.get("/cycle/report?include_notes=true", headers=HB).json()
    assert report_b["cycles"] == [] and report_b["notes"] == [] and report_b["medications"] == []
    assert "Slept badly" not in client.get("/cycle/report?include_notes=true", headers=HB).text
    # B writes the same date: A's record is untouched
    client.put(f"/cycle/day/{day}", json={"flow": "none", "notes": "B's note"}, headers=HB)
    assert client.get(f"/cycle/day/{day}", headers=HA).json()["log"]["notes"] == "Slept badly but okay."
    # B deleting everything does not touch A
    client.delete("/cycle/data?confirm=yes", headers=HB)
    assert client.get("/cycle/overview", headers=HA).json()["has_data"] is True
    assert not [r for r in db.tables.get("health_events", []) if r["user_id"] == B]


# ---- calendar ------------------------------------------------------------------------------------------------------------

def test_calendar_month_and_year(env):
    client, _ = env
    start_periods(client, HA, [28] * 4)
    month = client.get(f"/cycle/calendar?month={TODAY:%Y-%m}", headers=HA).json()
    assert month["month"] == f"{TODAY:%Y-%m}" and month["year"] is None and 28 <= len(month["days"]) <= 31
    assert [d["date"] for d in month["days"]] == sorted(d["date"] for d in month["days"]) and any(d["is_today"] for d in month["days"])
    assert month["days"][0].keys() >= {"cycle_day", "phase", "period", "fertile", "ovulation", "period_start", "flow", "has_log", "symptom_count"}
    year = client.get(f"/cycle/calendar?year={TODAY.year}", headers=HA).json()
    assert len(year["days"]) in (365, 366) and year["year"] == TODAY.year
    assert any(d["period"] == "logged" for d in year["days"])


@pytest.mark.parametrize("query", ["", "month=2026-13", "month=oct", "year=20", "year=2026&month=2026-10", "year=1800", "month=2026-1"])
def test_calendar_validation(env, query):
    client, _ = env
    r = client.get(f"/cycle/calendar?{query}", headers=HA)
    assert r.status_code == 422
    detail_is_text(r)


# ---- settings / modes / privacy --------------------------------------------------------------------------------------------

def test_settings_defaults_and_mode_switching_never_deletes_data(env):
    client, _ = env
    s = client.get("/cycle/settings", headers=HA).json()["settings"]
    assert s["mode"] == "track" and s["privacy"]["local_only"] is False and s["partner_share"]["enabled"] is False
    start_periods(client, HA, [28] * 4)
    client.put(f"/cycle/day/{iso(TODAY)}", json={"notes": "keep me"}, headers=HA)
    for mode in ("conceive", "birth_control", "perimenopause", "postpartum", "pregnancy", "track"):
        r = client.put("/cycle/settings", json={"mode": mode}, headers=HA)
        assert r.status_code == 200 and r.json()["settings"]["mode"] == mode and r.json()["overview"]["mode"] == mode
    assert client.get(f"/cycle/day/{iso(TODAY)}", headers=HA).json()["log"]["notes"] == "keep me"
    hist = client.get("/cycle/settings", headers=HA).json()["settings"]["mode_history"]
    assert [h["mode"] for h in hist] == ["conceive", "birth_control", "perimenopause", "postpartum", "pregnancy", "track"]
    assert client.get("/cycle/overview", headers=HA).json()["stats"]["cycles_used"] == 4


def test_mode_specific_overview_behaviour(env):
    client, _ = env
    start_periods(client, HA, [28] * 4)
    bc = client.put("/cycle/settings", json={"mode": "birth_control"}, headers=HA).json()["overview"]
    assert bc["fertile_window"] is None and bc["ovulation"] is None and "birth control" in bc["fertility_note"].lower()
    r = client.put("/cycle/settings", json={"mode": "pregnancy", "pregnancy": {"lmp": iso(TODAY - td(days=90))}}, headers=HA).json()["overview"]
    assert r["next_period"] is None and r["pregnancy"]["week"] == 12 and r["pregnancy"]["trimester"] == 1 and r["pregnancy"]["note"] and r["pregnancy"]["next_step"]
    assert r["cycle_day"] is None and r["phase"] is None
    pp = client.put("/cycle/settings", json={"mode": "postpartum", "postpartum": {"delivery_date": iso(TODAY - td(days=20)), "breastfeeding": True}},
                    headers=HA).json()["overview"]
    assert pp["postpartum"]["lochia_expected"] is True and pp["fertile_window"] is None and any("low-confidence" in n for n in pp["notices"])
    peri = client.put("/cycle/settings", json={"mode": "perimenopause"}, headers=HA).json()["overview"]
    assert peri["confidence"] == "low"


@pytest.mark.parametrize("patch", [
    {"mode": "everything"}, {"age_group": "child"}, {"temp_unit": "k"}, {"luteal_days": 5}, {"luteal_days": 30}, {"luteal_days": "ten"},
    {"privacy": {"local_only": "yes"}}, {"privacy": {"other": True}}, {"pregnancy": {"lmp": "soon"}}, {"pregnancy": {"lmp": "2040-01-01"}},
    {"pregnancy": {"due_date": "2020-01-01"}}, {"postpartum": {"delivery_date": "2999-01-01"}}, {"postpartum": {"breastfeeding": "maybe"}},
    {"partner_share": {"enabled": True}}, {"mode_history": []}, {"bogus": 1}, {"pregnancy": "x"},
])
def test_settings_validation(env, patch):
    client, _ = env
    r = client.put("/cycle/settings", json=patch, headers=HA)
    assert r.status_code == 422, patch
    detail_is_text(r)


def test_luteal_override_and_nested_merge(env):
    client, _ = env
    client.put("/cycle/settings", json={"luteal_days": 12, "privacy": {"local_only": False}}, headers=HA)
    client.put("/cycle/settings", json={"temp_unit": "f"}, headers=HA)
    s = client.get("/cycle/settings", headers=HA).json()["settings"]
    assert s["luteal_days"] == 12 and s["temp_unit"] == "f"
    assert client.put("/cycle/settings", json={"luteal_days": None}, headers=HA).json()["settings"]["luteal_days"] is None


def test_local_only_keeps_cycle_data_out_of_trackers_and_analytics(env):
    client, db = env
    client.post("/cycle/period/start", json={"date": iso(TODAY - td(days=30))}, headers=HA)
    client.put(f"/cycle/day/{iso(TODAY - td(days=30))}", json={"period_start": True, "factors": ["cramps"], "pain_level": 5}, headers=HA)
    assert [e for e in db.rows("extracted_health_events", user_id=A) if e["extracted_data"].get("_prov", {}).get("domain") == "cycle"]
    client.put("/cycle/settings", json={"privacy": {"local_only": True}}, headers=HA)
    assert not [e for e in db.rows("extracted_health_events", user_id=A) if e["extracted_data"].get("_prov", {}).get("store") == "mirror"]
    before = len(db.rows("menstrual_cycles", user_id=A))
    client.post("/cycle/period/start", json={"date": iso(TODAY)}, headers=HA)
    client.put(f"/cycle/day/{iso(TODAY - td(days=1))}", json={"factors": ["cramps"], "pain_level": 5}, headers=HA)
    assert len(db.rows("menstrual_cycles", user_id=A)) == before
    assert not [e for e in db.rows("extracted_health_events", user_id=A) if e["extracted_data"].get("_prov", {}).get("store") == "mirror"]
    ov = client.get("/cycle/overview", headers=HA).json()
    assert ov["privacy"]["local_only"] is True and ov["cycle_day"] == 1   # still works on the Cycle page itself


# ---- insights / report -----------------------------------------------------------------------------------------------------

def seed_history(db, uid, cycles=6, length=28):
    starts = [TODAY - td(days=10 + length * k) for k in range(cycles, -1, -1)]
    for s in starts:
        for o in range(length):
            d = s + td(days=o)
            if d > TODAY:
                continue
            log = {**cycle_api.normalize_day_log({}), "energy": 2 if o >= 20 else 4, "period_start": o == 0,
                   "flow": "medium" if o < 4 else None, "factors": ["bloating"] if o >= 22 else [], "medications": ["ibuprofen"] if o == 1 else [],
                   "notes": "note %d" % o if o == 3 else None, "pain_level": 6 if o < 2 else 1}
            doc_store.put(db, uid, "cycle_day", d.isoformat(), log, when=f"{d.isoformat()}T12:00:00+00:00")
    return starts


def test_insights_not_ready_then_ready(env):
    client, db = env
    r = client.get("/cycle/insights", headers=HA).json()
    assert r["ready"] is False and r["cycles_used"] == 0 and "still learning" in r["message"] and r["min_cycles"] == K.INSIGHT_MIN_CYCLES
    seed_history(db, A)
    r = client.get("/cycle/insights", headers=HA).json()
    assert r["ready"] is True and r["cycles_used"] >= 5
    energy = next(m for m in r["metrics"] if m["id"] == "energy")
    assert energy["ready"] and "not a cause" in energy["summary"] and {p["phase"] for p in energy["per_phase"]} == {"menstrual", "follicular", "ovulatory", "luteal"}
    assert any(s["id"] == "bloating" and s["most_common_phase"] == "luteal" for s in r["symptoms"])
    assert "not causes" in r["disclaimer"] or "not a cause" in r["disclaimer"] or "not causes" in r["disclaimer"].lower()
    assert client.get("/cycle/insights", headers=HB).json()["ready"] is False


def test_insights_use_sleep_mood_and_weight_trackers(env):
    client, db = env
    starts = seed_history(db, A)
    for s in starts[:-1]:
        for o in range(0, 28, 2):
            d = s + td(days=o)
            db.table("sleep_logs").insert({"user_id": A, "sleep_date": iso(d), "duration_minutes": 480 if o < 14 else 360, "sleep_quality": 6}).execute()
            db.table("weight_logs").insert({"user_id": A, "logged_at": f"{iso(d)}T07:00:00+00:00", "weight_kg": 60 + (0.8 if o >= 20 else 0)}).execute()
    r = client.get("/cycle/insights", headers=HA).json()
    sleep = next(m for m in r["metrics"] if m["id"] == "sleep_hours")
    weight = next(m for m in r["metrics"] if m["id"] == "weight")
    assert sleep["ready"] and "sleep tracker" in sleep["source"] and weight["ready"]


def test_report_structure_notes_are_opt_in_and_flags_become_questions(env):
    client, db = env
    seed_history(db, A)
    r = client.get("/cycle/report?months=6", headers=HA).json()
    assert r["status"] == "success" and r["notes"] is None and r["mode"] == "track"
    assert r["summary"]["cycles_tracked"] >= 4 and r["summary"]["average_length"] == 28.0 and r["cycles"][0].keys() >= {"start", "length", "period_days"}
    assert r["pain"]["logged_days"] > 0 and r["pain"]["maximum"] == 6 and "ibuprofen" in r["medications"]
    assert r["disclaimers"] and r["questions_for_clinician"] and any(s["label"] == "Bloating" for s in r["symptoms"])
    assert "note 3" not in str(r)
    with_notes = client.get("/cycle/report?months=6&include_notes=true", headers=HA).json()
    assert with_notes["notes"] and with_notes["notes"][0]["text"].startswith("note")
    for q in ("months=0", "months=25", "months=abc", "include_notes=maybe"):
        r = client.get(f"/cycle/report?{q}", headers=HA)
        assert r.status_code == 422
        detail_is_text(r)


# ---- factors / education -----------------------------------------------------------------------------------------------------

def test_factors_catalogue_is_grouped_and_searchable(env):
    client, _ = env
    r = client.get("/cycle/factors", headers=HA).json()
    assert r["total"] >= 100 and len(r["groups"]) >= 10 and r["query"] is None
    assert r["groups"][0].keys() >= {"id", "label", "chips"} and r["groups"][0]["chips"][0].keys() >= {"id", "label", "group", "keywords", "signal"}
    q = client.get("/cycle/factors?q=tummy", headers=HA).json()
    assert q["query"] == "tummy" and 0 < q["total"] < r["total"] and any(c["id"] == "bloating" for g in q["groups"] for c in g["chips"])
    assert client.get("/cycle/factors?group=mood", headers=HA).json()["groups"][0]["id"] == "mood"
    assert client.get("/cycle/factors?q=" + "x" * 80, headers=HA).status_code == 422
    assert client.get("/cycle/factors?group=nope", headers=HA).status_code == 422


def test_education_is_labelled_general_knowledge(env):
    client, _ = env
    r = client.get("/cycle/education", headers=HA).json()
    assert r["label"] == "General knowledge, not from your data" and len(r["articles"]) >= 16
    assert all(a["source_class"] == "EXTERNAL_KNOWLEDGE" and a["body"] for a in r["articles"])
    assert 0 < len(client.get("/cycle/education?mode=pregnancy", headers=HA).json()["articles"]) <= len(r["articles"])
    assert client.get("/cycle/education?mode=zzz", headers=HA).status_code == 422
    assert client.get("/cycle/education?topic=pain", headers=HA).json()["articles"]


# ---- partner view --------------------------------------------------------------------------------------------------------------

def test_partner_link_shows_predictions_only_and_can_be_revoked(env):
    client, _ = env
    start_periods(client, HA, [28] * 4)
    client.put(f"/cycle/day/{iso(TODAY)}", json={"notes": "private", "pain_level": 6}, headers=HA)
    r = client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).json()
    token = r["token"]
    assert r["enabled"] and r["share_path"] == f"/cycle/partner/{token}" and len(token) >= 30
    assert "token" not in client.get("/cycle/partner-view", headers=HA).json()
    public = client.get(f"/cycle/partner/{token}")           # no Authorization header at all
    body = public.json()
    assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
    assert set(body) == {"status", "label", "next_period", "phase_hint", "notice"} and set(body["next_period"]) == {"earliest", "latest"}
    assert "private" not in public.text and "fertile" not in public.text.lower() and "ovulation" not in public.text.lower()
    # rotating invalidates the old link
    new = client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).json()["token"]
    assert new != token and client.get(f"/cycle/partner/{token}").status_code == 404 and client.get(f"/cycle/partner/{new}").status_code == 200
    r = client.post("/cycle/partner-view", json={"action": "revoke"}, headers=HA).json()
    assert r["enabled"] is False and r["shares"] == []
    gone = client.get(f"/cycle/partner/{new}")
    assert gone.status_code == 404 and gone.json()["detail"] == "This link is no longer active."


def test_partner_link_edge_cases(env):
    client, _ = env
    for token in ("short", "x" * 30, "a" * 200, "../etc/passwd"):
        assert client.get(f"/cycle/partner/{token}").status_code in (404, 405)
    assert client.post("/cycle/partner-view", json={"action": "explode"}, headers=HA).status_code == 422
    assert client.post("/cycle/partner-view", json={}, headers=HA).status_code == 422
    # local-only blocks creating and silences existing links
    token = client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).json()["token"]
    client.put("/cycle/settings", json={"privacy": {"local_only": True}}, headers=HA)
    assert client.get(f"/cycle/partner/{token}").status_code == 404
    assert client.get("/cycle/partner-view", headers=HA).json()["enabled"] is False
    assert client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).status_code == 422
    # user B's revoke does not touch A's link
    client.put("/cycle/settings", json={"privacy": {"local_only": False}}, headers=HA)
    token = client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).json()["token"]
    client.post("/cycle/partner-view", json={"action": "revoke"}, headers=HB)
    assert client.get(f"/cycle/partner/{token}").status_code == 200


def test_partner_view_hides_pregnancy_and_postpartum(env):
    client, _ = env
    token = client.post("/cycle/partner-view", json={"action": "create"}, headers=HA).json()["token"]
    client.put("/cycle/settings", json={"mode": "pregnancy"}, headers=HA)
    assert client.get(f"/cycle/partner/{token}").json()["next_period"] is None


# ---- delete ----------------------------------------------------------------------------------------------------------------------

def test_delete_requires_confirmation_and_removes_everything(env):
    client, db = env
    start_periods(client, HA, [28] * 3)
    client.put("/cycle/settings", json={"mode": "conceive"}, headers=HA)
    client.post("/cycle/partner-view", json={"action": "create"}, headers=HA)
    start_periods(client, HB, [28] * 2)
    r = client.delete("/cycle/data", headers=HA)
    assert r.status_code == 422
    detail_is_text(r)
    assert client.delete("/cycle/data?confirm=no", headers=HA).status_code == 422
    r = client.delete("/cycle/data?confirm=yes", headers=HA).json()
    assert r["status"] == "success" and r["deleted"]["days"] == 4 and r["deleted"]["settings"] and r["deleted"]["partner"] and r["deleted"]["tracker_entries"] >= 4
    ov = client.get("/cycle/overview", headers=HA).json()
    assert ov["has_data"] is False and ov["mode"] == "track"
    assert not [r_ for r_ in db.tables.get("health_events", []) if r_["user_id"] == A]
    assert not db.rows("menstrual_cycles", user_id=A)
    assert client.get("/cycle/overview", headers=HB).json()["has_data"] is True      # B untouched
    assert client.delete("/cycle/data?confirm=yes", headers=HA).json()["deleted"]["days"] == 0   # idempotent


# ---- no raw exception text --------------------------------------------------------------------------------------------------------

def test_database_failures_never_leak_raw_text(env):
    client, db = env
    secret = APIError({"code": "XX000", "message": "internal secret detail: password=hunter2", "details": None, "hint": None})
    db.failures["health_events"] = secret
    for method, path, kw in (("get", "/cycle/overview", {}), ("put", f"/cycle/day/{iso(TODAY)}", {"json": {"flow": "light"}}), ("post", "/cycle/period/start", {})):
        r = getattr(client, method)(path, headers=HA, **kw)
        assert r.status_code >= 500 and "hunter2" not in r.text and "secret" not in r.text
    db.failures.clear()
    db.failures["menstrual_cycles"] = APIError({"code": "XX000", "message": "internal secret detail", "details": None, "hint": None})
    r = client.get("/cycle/overview", headers=HA)       # the old tracker being broken must not break the page
    assert r.status_code == 200 and "secret" not in r.text
    r = client.post("/cycle/period/start", headers=HA)
    assert r.status_code == 200 and "secret" not in r.text


def test_client_today_is_honoured_within_a_day_only(env):
    client, _ = env
    tomorrow = iso(TODAY + td(days=1))
    r = client.post("/cycle/period/start", json={"today": tomorrow, "date": iso(TODAY)}, headers=HA).json()
    assert r["overview"]["today"] == tomorrow and r["overview"]["cycle_day"] == 2
    assert client.get(f"/cycle/overview?today={iso(TODAY + td(days=40))}", headers=HA).json()["today"] == iso(TODAY)
    assert client.get("/cycle/overview?today=garbage", headers=HA).status_code == 422
