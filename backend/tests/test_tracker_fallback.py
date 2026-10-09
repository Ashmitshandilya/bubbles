"""Tracker compatibility store: /health/<domain> keeps working while the live database
denies the backend on the domain tables (Postgres 42501), and merges both stores.

Uses an in-memory fake Supabase that can refuse chosen tables with the exact
postgrest APIError the live project raises. Never touches the network.
"""
from __future__ import annotations

import copy
import itertools
import json
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from db_access import register_db_error_handlers
from event_filters import clean_data, counts_as_observation, is_live_positive
from health_logs import DOMAINS, LBS_PER_KG, build_router
from test_health_logs import FORM_BODIES, LIVE_COLUMNS

DOMAIN_TABLES = sorted({d["table"] for d in DOMAINS.values()})
# The 20 tables the live project refuses the service role on (the 15 tracker tables are among them).
LIVE_DENIED = set(DOMAIN_TABLES) | {"profiles", "rl_interactions", "rl_arm_stats", "organ_assessments", "exercise_logs"}
MODES = ("primary", "compat")
EVENT_TYPES = {"sleep": "sleep", "symptoms": "symptom", "activity": "activity", "cycle": "menstrual_symptom",
               "hydration": "hydration", "mood": "mood", "nutrition": "food", "weight": "weight", "vitals": "vital_sign",
               "medications": "medication", "conditions": "medical_condition", "allergies": "allergy",
               "labs": "lab_result", "visits": "doctor_visit", "reports": "lab_result"}
H1 = {"Authorization": "Bearer user-1"}
H2 = {"Authorization": "Bearer user-2"}
CREATED = "2026-10-06T00:00:00+00:00"


def denied_error(table: str) -> APIError:
    return APIError({"code": "42501", "message": f"permission denied for table {table}", "details": None, "hint": None})


def other_error() -> APIError:
    return APIError({"code": "XX000", "message": "internal secret detail", "details": None, "hint": None})


def _path(row: dict, key: str):
    """PostgREST json path: a->b->>c."""
    value: object = row
    for part in re.split(r"->>?", key):
        value = value.get(part) if isinstance(value, dict) else None
    return value


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.payload, self.filters, self.gte_filters, self.ordering, self.max = None, [], [], None, None

    def select(self, *_cols):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def gte(self, key, value):
        self.gte_filters.append((key, value))
        return self

    def order(self, key, desc=False):
        self.ordering = (key, desc)
        return self

    def limit(self, n):
        self.max = n
        return self

    def execute(self):
        db, name = self.db, self.table
        op = "insert" if self.payload is not None else "select"
        db.calls.append((name, op, list(self.filters), self.max))
        if name in db.denied:
            raise denied_error(name)
        if name in db.fail:
            raise db.fail[name]
        if op == "select" and db.fail_json_filter and any("->" in k for k, _ in self.filters):
            raise db.fail_json_filter
        if op == "insert":
            assert name in LIVE_COLUMNS, f"unexpected table {name}"
            unknown = set(self.payload) - LIVE_COLUMNS[name]
            assert not unknown, f"{name}: columns not in live schema: {sorted(unknown)}"
            stored = json.loads(json.dumps(self.payload, allow_nan=False))  # jsonb: no NaN/Infinity
            row = {"id": f"id-{next(db.ids)}", "created_at": CREATED, **stored}
            db.rows.setdefault(name, []).append(row)
            return SimpleNamespace(data=[copy.deepcopy(row)])
        def matches(row):
            for key, value in self.filters:
                got = _path(row, key) if "->" in key else row.get(key)
                if got is None or str(got) != str(value):
                    return False
            return all(str(row.get(k, "")) >= str(v) for k, v in self.gte_filters)

        rows = [r for r in db.rows.get(name, []) if matches(r)]
        if self.ordering:
            rows = sorted(rows, key=lambda r: str(r.get(self.ordering[0], "")), reverse=self.ordering[1])
        return SimpleNamespace(data=copy.deepcopy(rows[: self.max]))


class FakeDB:
    def __init__(self, denied=(), fail=None, fail_json_filter=None):
        self.rows, self.ids, self.calls = {}, itertools.count(1), []
        self.denied, self.fail, self.fail_json_filter = set(denied), fail or {}, fail_json_filter

    def table(self, name):
        return FakeQuery(self, name)


def make_client(mode="primary", **kwargs):
    db = FakeDB(denied=LIVE_DENIED if mode == "compat" else (), **kwargs)

    def get_user(authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing token")
        return SimpleNamespace(id=authorization.removeprefix("Bearer "))

    app = FastAPI()
    register_db_error_handlers(app)
    app.include_router(build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def events(db):
    return db.rows.get("extracted_health_events", [])


# --- both modes: identical contract ------------------------------------------------

def test_post_and_get_have_identical_shape_in_both_modes():
    seen = {}
    for mode in MODES:
        client, db = make_client(mode)
        for slug, body in FORM_BODIES.items():
            created = client.post(f"/health/{slug}", json=body, headers=H1)
            assert created.status_code == 201, (mode, slug, created.text)
            payload = created.json()
            assert set(payload) == {"status", "entry", "store"} and payload["status"] == "success"
            assert payload["store"] == ("primary" if mode == "primary" else "compat")
            listed = client.get(f"/health/{slug}?days=30", headers=H1).json()
            assert set(listed) == ({"status", "entries", "summary"} if slug == "cycle" else {"status", "entries"})
            assert listed["entries"] == [payload["entry"]], (mode, slug)
            assert payload["entry"]["id"] and payload["entry"]["date"]
            assert None not in payload["entry"].values() and "None" not in str(payload["entry"])
            seen[(mode, slug)] = {k: v for k, v in payload["entry"].items() if k != "id"}
    assert set(FORM_BODIES) == set(DOMAINS)
    for slug in FORM_BODIES:
        assert seen[("primary", slug)] == seen[("compat", slug)], slug


def test_compat_mode_writes_only_to_the_event_store_with_full_provenance():
    client, db = make_client("compat")
    for slug, body in FORM_BODIES.items():
        assert client.post(f"/health/{slug}", json=body, headers=H1).status_code == 201
    assert not any(db.rows.get(t) for t in DOMAIN_TABLES)  # nothing reached the denied tables
    assert len(events(db)) == len(DOMAINS)
    by_slug = {e["extracted_data"]["_prov"]["domain"]: e for e in events(db)}
    assert set(by_slug) == set(DOMAINS)
    for slug, event in by_slug.items():
        assert event["event_type"] == EVENT_TYPES[slug], slug
        assert (event["user_id"], event["confidence"], event["extraction_status"], event["user_confirmed"], event["message_id"]) == ("user-1", 1.0, "confirmed", True, None)
        data = event["extracted_data"]
        assert data["_prov"] == {"source": "tracker", "domain": slug, "store": "compat"}
        assert isinstance(data["_row"], dict) and data["_row"]
        assert "user_id" not in data["_row"] and "source" not in data["_row"]
        assert is_live_positive(event) and counts_as_observation(event), slug
        assert not [k for k in clean_data(data) if k.startswith("_")]
        assert clean_data(data).get("date"), slug  # analytics need a date on every event


def test_superset_keys_per_domain():
    client, db = make_client("compat")
    for slug, body in FORM_BODIES.items():
        client.post(f"/health/{slug}", json=body, headers=H1)
    data = {e["extracted_data"]["_prov"]["domain"]: e["extracted_data"] for e in events(db)}
    kg = round(140.5 / LBS_PER_KG, 2)
    expected = {
        "sleep": {"name": "sleep", "duration_minutes": 450, "hours": 7.5, "duration_hours": 7.5, "value": 7.5, "amount": 7.5, "unit": "hours", "severity": 6, "date": "2026-10-05"},
        "hydration": {"name": "water", "amount_ml": 500, "water_ml": 500, "amount": 500, "value": 500, "unit": "ml", "date": "2026-10-05"},
        "symptoms": {"symptom": "Headache", "name": "Headache", "severity": 4, "date": "2026-10-05"},
        "weight": {"name": "weight", "weight_kg": kg, "value": kg, "amount": kg, "unit": "kg", "date": "2026-10-05"},
        "mood": {"name": "mood", "score": 7, "mood_score": 7, "severity": 7, "date": "2026-10-05"},
        "activity": {"name": "Walk", "activity": "Walk", "duration_minutes": 30, "minutes": 30, "unit": "min", "date": "2026-10-05"},
        "cycle": {"name": "period", "symptom": "menstrual flow", "start_date": "2026-10-05", "date": "2026-10-05", "phase": "period"},
        "nutrition": {"name": "Dal and rice", "category": "lunch", "meal_type": "lunch", "calories": 450.0, "date": "2026-10-05"},
        "vitals": {"name": "vitals", "heart_rate_bpm": 72, "systolic_bp": 120, "diastolic_bp": 80, "temperature_c": 37.0, "date": "2026-10-05"},
        "medications": {"name": "Ibuprofen", "category": "medication", "dosage": "200mg", "reason": "pain"},
        "conditions": {"name": "Asthma", "category": "condition", "status": "managed", "diagnosed_date": "2020-01-02"},
        "allergies": {"name": "Peanuts", "allergen": "Peanuts", "category": "allergy", "reaction": "food", "severity_label": "severe"},
        "labs": {"name": "HbA1c", "test_name": "HbA1c", "value": 5.8, "unit": "%", "reference_min": 4.0, "reference_max": 6.0, "date": "2026-10-01"},
        "visits": {"name": "Dr Rao", "doctor_name": "Dr Rao", "specialty": "GP", "reason": "checkup", "date": "2026-10-02"},
        "reports": {"name": "Chest X-ray", "title": "Chest X-ray", "report_type": "imaging", "findings": "clear", "date": "2026-09-30"},
    }
    assert set(expected) == set(DOMAINS)
    for slug, want in expected.items():
        got = data[slug]
        assert want.items() <= got.items(), (slug, {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v})
    assert data["cycle"]["is_start"] is True  # a real bool: analytics test bool(is_start)
    assert "intensity" not in data["activity"] and data["activity"]["intensity_label"] == "moderate"  # numeric readers never see text
    assert "severity" not in data["allergies"]


def test_cycle_phases_other_than_period_are_not_period_starts():
    client, db = make_client("compat")
    client.post("/health/cycle", json={"phase": "luteal", "date": "2026-10-05T00:00:00Z"}, headers=H1)
    data = events(db)[0]["extracted_data"]
    assert data["is_start"] is False and data["phase"] == "luteal" and "symptom" not in data
    assert client.get("/health/cycle", headers=H1).json()["summary"] == {"period_start_count": 0}


def test_vitals_single_reading_carries_scalar_value_and_unit():
    client, db = make_client("compat")
    client.post("/health/vitals", json={"heart_rate": "60"}, headers=H1)
    client.post("/health/vitals", json={"temperature": "98.6"}, headers=H1)
    client.post("/health/vitals", json={"blood_pressure": "110/70"}, headers=H1)
    hr, temp, bp = (e["extracted_data"] for e in events(db))
    assert (hr["name"], hr["value"], hr["unit"]) == ("heart rate", 60, "bpm")
    assert (temp["name"], temp["value"], temp["unit"]) == ("temperature", 37.0, "C")
    assert (bp["name"], bp["systolic"], bp["diastolic"]) == ("blood pressure", 110, 70) and "value" not in bp
    entries = client.get("/health/vitals", headers=H1).json()["entries"]
    assert sorted(e.get("blood_pressure", "") for e in entries) == ["", "", "110/70"]


# --- merge, de-duplication, windowing ---------------------------------------------

def test_entries_saved_in_compat_mode_stay_visible_after_grants_are_applied():
    client, db = make_client("compat")
    old = client.post("/health/sleep", json={"duration": 6, "date": iso(3)}, headers=H1).json()["entry"]
    db.denied.clear()  # the owner applied the grants migration
    new = client.post("/health/sleep", json={"duration": 8, "date": iso(1)}, headers=H1).json()
    assert new["store"] == "primary"
    listed = client.get("/health/sleep?days=30", headers=H1).json()["entries"]
    assert [e["id"] for e in listed] == [new["entry"]["id"], old["id"]]  # newest first, both stores
    assert [e["duration"] for e in listed] == [8, 6]


def test_merge_deduplicates_by_id_and_sorts_by_date_desc():
    client, db = make_client("primary")
    client.post("/health/sleep", json={"duration": 7, "date": iso(5)}, headers=H1)
    db.denied |= {"sleep_logs"}
    compat = client.post("/health/sleep", json={"duration": 5, "date": iso(2)}, headers=H1).json()["entry"]
    db.denied.clear()
    # a primary row that (impossibly) shares the compat event's id must not appear twice
    db.rows["sleep_logs"].append({"id": compat["id"], "user_id": "user-1", "sleep_date": iso(2)[:10], "duration_minutes": 300, "created_at": CREATED})
    listed = client.get("/health/sleep", headers=H1).json()["entries"]
    ids = [e["id"] for e in listed]
    assert len(ids) == len(set(ids)) == 2
    assert [e["date"][:10] for e in listed] == sorted((e["date"][:10] for e in listed), reverse=True)


@pytest.mark.parametrize("mode", MODES)
def test_windowing_applies_to_the_entry_date(mode):
    client, db = make_client(mode)
    for days_ago in (5, 100):
        client.post("/health/sleep", json={"duration": 7, "date": iso(days_ago)}, headers=H1)
        client.post("/health/hydration", json={"volume": 250, "date": iso(days_ago)}, headers=H1)
        client.post("/health/cycle", json={"phase": "period", "date": iso(days_ago)}, headers=H1)
    client.post("/health/medications", json={"name": "Iron"}, headers=H1)
    for slug in ("sleep", "hydration", "cycle"):
        assert len(client.get(f"/health/{slug}?days=30", headers=H1).json()["entries"]) == 1, slug
        assert len(client.get(f"/health/{slug}?days=365", headers=H1).json()["entries"]) == 2, slug
    # non-windowed domains ignore `days`
    assert len(client.get("/health/medications?days=1", headers=H1).json()["entries"]) == 1


def test_compat_reads_are_scoped_to_the_user_and_the_domain():
    client, db = make_client("compat")
    client.post("/health/sleep", json={"duration": 7}, headers=H1)
    client.post("/health/sleep", json={"duration": 6}, headers=H2)
    client.post("/health/mood", json={"mood": 5}, headers=H1)
    assert [e["duration"] for e in client.get("/health/sleep", headers=H1).json()["entries"]] == [7]
    assert [e["duration"] for e in client.get("/health/sleep", headers=H2).json()["entries"]] == [6]
    assert len(client.get("/health/mood", headers=H2).json()["entries"]) == 0


def test_only_live_tracker_events_are_listed():
    client, db = make_client("compat")
    client.post("/health/symptoms", json={"symptom": "Cough"}, headers=H1)
    rows = db.rows["extracted_health_events"]
    base = {"user_id": "user-1", "created_at": CREATED, "extraction_status": "confirmed", "user_confirmed": True}
    rows += [  # chat-extracted symptom, rejected compat row, other domain's compat row, corrupt rows
        {**base, "id": "chat", "event_type": "symptom", "extracted_data": {"symptom": "Fever", "_prov": {"source": "user_message"}}},
        {**base, "id": "dead", "event_type": "symptom", "extraction_status": "rejected",
         "extracted_data": {"_prov": {"source": "tracker", "domain": "symptoms", "store": "compat"}, "_row": {"symptom_name": "Dead", "started_at": iso(0)}}},
        {**base, "id": "other", "event_type": "mood",
         "extracted_data": {"_prov": {"source": "tracker", "domain": "mood", "store": "compat"}, "_row": {"mood": "5/10", "intensity": 5, "logged_at": iso(0)}}},
        {**base, "id": "no-row", "event_type": "symptom", "extracted_data": {"_prov": {"source": "tracker", "domain": "symptoms", "store": "compat"}}},
        {**base, "id": "bad-row", "event_type": "symptom", "extracted_data": {"_prov": {"source": "tracker", "domain": "symptoms", "store": "compat"}, "_row": "oops"}},
        {**base, "id": "not-dict", "event_type": "symptom", "extracted_data": "text"},
    ]
    listed = client.get("/health/symptoms", headers=H1).json()["entries"]
    assert [e["symptom"] for e in listed] == ["Cough"]


# --- server-side json filter and its fallback --------------------------------------

def test_json_filter_is_sent_server_side_and_row_limit_applies_per_domain():
    client, db = make_client("compat")
    client.post("/health/sleep", json={"duration": 7}, headers=H1)
    db.calls.clear()
    client.get("/health/sleep", headers=H1)
    reads = [c for c in db.calls if c[0] == "extracted_health_events"]
    assert len(reads) == 1
    keys = dict(reads[0][2])
    assert keys["extracted_data->_prov->>domain"] == "sleep" and keys["extracted_data->_prov->>store"] == "compat"


def test_json_filter_failure_falls_back_to_python_filtering():
    client, db = make_client("compat", fail_json_filter=other_error())
    client.post("/health/sleep", json={"duration": 7}, headers=H1)
    client.post("/health/mood", json={"mood": 6}, headers=H1)
    db.rows["extracted_health_events"].append({"id": "chat", "user_id": "user-1", "event_type": "symptom", "created_at": CREATED,
                                               "extraction_status": "pending", "extracted_data": {"symptom": "Fever"}})
    listed = client.get("/health/sleep", headers=H1)
    assert listed.status_code == 200 and [e["duration"] for e in listed.json()["entries"]] == [7]
    assert client.get("/health/summary", headers=H1).json()["total_entries"] == 2
    unscoped = [c for c in db.calls if c[0] == "extracted_health_events" and c[1] == "select" and c[3] == 1000]
    assert unscoped  # the fallback scanned without the json filter


# --- summary -----------------------------------------------------------------------

def test_summary_counts_compat_rows_and_never_500s_on_denied_tables():
    client, db = make_client("compat")
    client.post("/health/sleep", json={"duration": 7}, headers=H1)
    client.post("/health/mood", json={"mood": 5}, headers=H1)
    client.post("/health/mood", json={"mood": 6}, headers=H1)
    client.post("/health/sleep", json={"duration": 7}, headers=H2)  # other user: not counted
    summary = client.get("/health/summary", headers=H1)
    assert summary.status_code == 200
    assert summary.json() == {"status": "success", "categories_with_data": 2, "total_entries": 3,
                              "days_tracked": 1, "last_update": CREATED}


def test_summary_merges_primary_and_compat():
    client, db = make_client("compat")
    client.post("/health/sleep", json={"duration": 7}, headers=H1)
    db.denied.clear()
    client.post("/health/sleep", json={"duration": 8}, headers=H1)
    client.post("/health/weight", json={"weight": "150"}, headers=H1)
    summary = client.get("/health/summary", headers=H1).json()
    assert (summary["categories_with_data"], summary["total_entries"]) == (2, 3)


def test_summary_is_empty_not_an_error_when_every_store_is_refused():
    client, db = make_client("compat")
    db.denied.add("extracted_health_events")
    response = client.get("/health/summary", headers=H1)
    assert response.status_code == 200
    assert response.json()["total_entries"] == 0 and response.json()["categories_with_data"] == 0


def test_cycle_summary_includes_compat_rows():
    client, db = make_client("compat")
    for day in ("2026-07-01", "2026-07-29"):
        client.post("/health/cycle", json={"phase": "period", "date": f"{day}T00:00:00Z"}, headers=H1)
    db.denied.clear()
    client.post("/health/cycle", json={"phase": "period", "date": "2026-08-27T00:00:00Z"}, headers=H1)
    summary = client.get("/health/cycle?days=365", headers=H1).json()["summary"]
    assert summary["period_start_count"] == 3 and summary["average_cycle_length"] == 28.5
    assert summary["last_period"] == "2026-08-27" and "next_predicted" in summary


# --- errors other than permission-denied are not swallowed ------------------------

@pytest.mark.parametrize("method", ("post", "get"))
def test_other_database_errors_surface_and_never_trigger_the_fallback(method):
    client, db = make_client("primary", fail={"sleep_logs": other_error()})
    response = (client.post("/health/sleep", json={"duration": 7}, headers=H1) if method == "post"
                else client.get("/health/sleep", headers=H1))
    assert response.status_code == 500
    assert response.json() == {"detail": "Database error", "code": "database_error"}
    assert "secret" not in response.text  # no internals leak
    assert not events(db)  # nothing was diverted into the event store


def test_summary_surfaces_other_errors():
    client, _ = make_client("primary", fail={"weight_logs": other_error()})
    assert client.get("/health/summary", headers=H1).status_code == 500


def test_compat_read_error_that_is_not_permission_surfaces_even_when_primary_works():
    client, _ = make_client("primary", fail={"extracted_health_events": other_error()})
    assert client.get("/health/sleep", headers=H1).status_code == 500


def test_compat_write_error_is_not_masked_as_a_permission_problem():
    client, _ = make_client("compat", fail={"extracted_health_events": other_error()})
    response = client.post("/health/sleep", json={"duration": 7}, headers=H1)
    assert response.status_code == 500 and response.json()["code"] == "database_error"


def test_both_stores_refused_reports_the_table_the_user_asked_for():
    client, db = make_client("compat")
    db.denied.add("extracted_health_events")
    for response in (client.post("/health/sleep", json={"duration": 7}, headers=H1), client.get("/health/sleep", headers=H1)):
        body = response.json()
        assert response.status_code == 503 and body["code"] == "database_permission_denied"
        assert body["table"] == "sleep_logs" and "20261006_coco_service_role_grants.sql" in body["detail"]


# --- malformed / absurd input is a 422 with a string detail, never a 500 ----------

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("content", [
    pytest.param(c, id=i) for i, c in {"list": b"[1, 2]", "string": b'"text"', "number": b"42", "null": b"null", "bool": b"true",
                                       "truncated": b"{", "garbage": b"not json", "empty": b"", "bad-utf8": b"\xff\xfe\x00",
                                       "deep-nesting": b"[" * 200000}.items()])
def test_non_object_or_malformed_bodies_are_422_with_string_detail(mode, content):
    client, db = make_client(mode)
    response = client.post("/health/sleep", content=content, headers={**H1, "content-type": "application/json"})
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], str)
    assert not events(db) and not db.rows.get("sleep_logs")


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("slug,body", [
    ("sleep", b'{"duration": 1e999}'),
    ("sleep", b'{"duration": -1e999}'),
    ("sleep", b'{"duration": NaN}'),
    ("sleep", b'{"duration": ' + b"9" * 400 + b"}"),
    ("sleep", b'{"duration": true}'),
    ("sleep", b'{"duration": [7]}'),
    ("sleep", b'{"duration": {"a": 1}}'),
    ("sleep", b'{"duration": 7, "date": "not-a-date"}'),
    ("sleep", b'{"duration": 7, "date": "2026-13-45"}'),
    ("sleep", b'{"duration": 7, "date": "3000-01-01"}'),
    ("sleep", b'{"duration": 7, "date": "0001-01-01"}'),
    ("sleep", b'{"duration": 7, "date": {"x": 1}}'),
    ("sleep", b'{"duration": 7, "quality": 1e999}'),
    ("symptoms", b'{"symptom": {"a": 1}}'),
    ("symptoms", b'{"symptom": ["a"]}'),
    ("symptoms", b'{"symptom": "   "}'),
    ("symptoms", b'{"symptom": "x", "severity": 1e308}'),
    ("weight", b'{"weight": 1e999}'),
    ("vitals", b'{"blood_pressure": "99999/99999"}'),
    ("vitals", b'{"heart_rate": "abc"}'),
    ("labs", b'{"test_name": "x", "value": "1e30"}'),
    ("labs", b'{"test_name": "x", "test_date": "garbage"}'),
    ("cycle", b'{"phase": ["period"]}'),
    ("conditions", b'{"condition_name": "x", "diagnosed_date": "nope"}'),
    ("visits", b'{"visit_date": "2026-99-99"}'),
])
def test_absurd_values_are_422_with_string_detail(mode, slug, body):
    client, db = make_client(mode)
    response = client.post(f"/health/{slug}", content=body, headers={**H1, "content-type": "application/json"})
    assert response.status_code == 422, (slug, body[:60], response.text[:200])
    assert isinstance(response.json()["detail"], str)
    assert not events(db) and not any(db.rows.get(t) for t in DOMAIN_TABLES)


@pytest.mark.parametrize("mode", MODES)
def test_hostile_text_is_cleaned_not_a_500(mode):
    client, db = make_client(mode)
    nasty = json.dumps({"symptom": "Head\u0000ache \ud800 ok", "notes": "x" * 50000}).encode()
    response = client.post("/health/symptoms", content=nasty, headers={**H1, "content-type": "application/json"})
    assert response.status_code == 201, response.text
    entry = response.json()["entry"]
    assert entry["symptom"] == "Headache  ok" and len(entry["notes"]) == 2000
    # non-finite lab results are kept as text instead of sending NaN to the database
    lab = client.post("/health/labs", json={"test_name": "CRP", "value": "nan", "reference_range": "1-" + "9" * 400}, headers=H1)
    assert lab.status_code == 201 and "Result: nan" in lab.json()["entry"]["notes"] and "value" not in lab.json()["entry"]


@pytest.mark.parametrize("mode", MODES)
def test_unknown_slug_and_bad_days(mode):
    client, _ = make_client(mode)
    assert client.get("/health/nope", headers=H1).status_code == 404
    assert client.post("/health/nope", json={}, headers=H1).status_code == 404
    assert client.get("/health/sleep?days=0", headers=H1).status_code == 422
    assert client.get("/health/sleep?days=abc", headers=H1).status_code == 422
    assert client.get("/health/sleep?days=100000", headers=H1).status_code == 422


def test_authentication_is_checked_before_the_body():
    client, _ = make_client("compat")
    assert client.post("/health/sleep", content=b"not json", headers={"content-type": "application/json"}).status_code == 401
    assert client.get("/health/sleep").status_code == 401
    assert client.get("/health/summary").status_code == 401
