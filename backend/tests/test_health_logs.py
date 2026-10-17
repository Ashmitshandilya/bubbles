"""Contract tests for /health/<domain>: frontend form shape <-> live Supabase columns."""
import itertools
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from health_logs import DOMAINS, build_router

# Column names of the live tables (verified against the project 2026-10-06).
LIVE_COLUMNS = {
    "sleep_logs": {"id", "user_id", "sleep_date", "bedtime", "wake_time", "duration_minutes", "sleep_quality", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "symptoms": {"id", "user_id", "symptom_name", "severity", "started_at", "ended_at", "notes", "body_location", "source", "user_confirmed", "created_at", "updated_at"},
    "activity_logs": {"id", "user_id", "activity_date", "activity_type", "duration_minutes", "distance_km", "calories_burned", "steps", "intensity", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "menstrual_cycles": {"id", "user_id", "start_date", "end_date", "cycle_length_days", "period_length_days", "flow_notes", "symptoms", "source", "user_confirmed", "created_at", "updated_at"},
    "hydration_logs": {"id", "user_id", "logged_at", "amount_ml", "drink_type", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "mood_logs": {"id", "user_id", "logged_at", "mood", "intensity", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "health_events": {"id", "user_id", "event_type", "event_date", "title", "description", "data", "source", "confidence", "user_confirmed", "created_at", "updated_at", "source_extracted_event_id", "source_message_id"},
    "weight_logs": {"id", "user_id", "logged_at", "weight_kg", "body_fat_percent", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "vital_signs": {"id", "user_id", "measured_at", "heart_rate_bpm", "systolic_bp", "diastolic_bp", "temperature_c", "spo2_percent", "respiratory_rate", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "medications": {"id", "user_id", "medication_name", "dosage", "frequency", "start_date", "end_date", "reason", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "medical_conditions": {"id", "user_id", "condition_name", "status", "diagnosed_date", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "allergies": {"id", "user_id", "allergen", "reaction", "severity", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "lab_results": {"id", "user_id", "medical_report_id", "test_name", "value", "unit", "reference_min", "reference_max", "abnormal_flag", "tested_at", "notes", "source", "user_confirmed", "created_at", "updated_at"},
    "medical_reports": {"id", "user_id", "report_name", "report_type", "report_date", "doctor_name", "hospital_name", "file_path", "extracted_text", "extracted_data", "processing_status", "user_confirmed", "created_at", "updated_at"},
    "doctor_visits": {"id", "user_id", "visit_date", "doctor_name", "specialty", "reason", "diagnosis", "notes", "recommendations", "medical_report_id", "source", "user_confirmed", "created_at", "updated_at"},
    "chat_messages": {"id", "user_id", "role", "content", "created_at"},
    # Trackers now also read this table (compatibility store, see test_tracker_fallback.py).
    "extracted_health_events": {"id", "user_id", "message_id", "event_type", "extracted_data", "confidence", "extraction_status", "user_confirmed", "created_at", "updated_at"},
}

# What each frontend page actually POSTs (see frontend/app/**/page.tsx and *Client.tsx).
FORM_BODIES = {
    "sleep": {"duration": 7.5, "quality": 6, "notes": "ok", "date": "2026-10-05T22:00:00.000Z"},
    "symptoms": {"symptom": "Headache", "severity": 4, "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "activity": {"type": "Walk", "duration": 30, "intensity": "moderate", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "cycle": {"phase": "period", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "hydration": {"volume": "500", "type": "water", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "mood": {"mood": "7", "stress": "3", "anxiety": "", "notes": "fine", "date": "2026-10-05T10:00:00.000Z"},
    "nutrition": {"meal_type": "lunch", "description": "Dal and rice", "calories": "450", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "eyes": {"screen_hours": "7", "comfort": "3", "symptoms": "dry,red", "glasses": "yes", "breaks": "4", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "weight": {"weight": "140.5", "time_of_day": "morning", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "vitals": {"heart_rate": "72", "blood_pressure": "120/80", "temperature": "98.6", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "medications": {"name": "Ibuprofen", "dosage": "200mg", "reason": "pain", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "conditions": {"condition_name": "Asthma", "diagnosed_date": "2020-01-02", "status": "managed", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "allergies": {"allergen": "Peanuts", "reaction_type": "food", "severity": "severe", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "labs": {"test_name": "HbA1c", "value": "5.8", "unit": "%", "reference_range": "4.0-6.0", "test_date": "2026-10-01", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "reports": {"report_type": "imaging", "title": "Chest X-ray", "report_date": "2026-09-30", "findings": "clear", "notes": "", "date": "2026-10-05T10:00:00.000Z"},
    "visits": {"doctor_name": "Dr Rao", "specialty": "GP", "visit_date": "2026-10-02", "reason": "checkup", "notes": "", "next_visit": "2027-01-02", "date": "2026-10-05T10:00:00.000Z"},
}


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.payload, self.ordering = db, table, [], None, None
        self.deleting = False
        self.changes = None
        self.max_rows = None

    def select(self, *_cols):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def delete(self):
        self.deleting = True
        return self

    def update(self, changes):
        self.changes = changes
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def in_(self, key, values):
        self.filters.append((key, ("__in__", list(values))))
        return self

    def gte(self, key, value):
        return self

    def order(self, key, desc=False):
        self.ordering = (key, desc)
        return self

    def limit(self, n):
        self.max_rows = n
        return self

    def _matches(self, row):
        for key, value in self.filters:
            if "->" in key:
                continue
            if isinstance(value, tuple) and value and value[0] == "__in__":
                if row.get(key) not in value[1]:
                    return False
            elif row.get(key) != value:
                return False
        return True

    def execute(self):
        rows = self.db.rows.get(self.table, [])
        if self.deleting:
            gone = [r for r in rows if self._matches(r)]
            self.db.rows[self.table] = [r for r in rows if r not in gone]
            return SimpleNamespace(data=gone)
        if self.changes is not None:
            hit = [r for r in rows if self._matches(r)]
            for r in hit:
                r.update(self.changes)
            return SimpleNamespace(data=hit)
        if self.payload is not None:
            unknown = set(self.payload) - LIVE_COLUMNS[self.table]
            assert not unknown, f"{self.table}: columns not in live schema: {sorted(unknown)}"
            row = {"id": f"id-{next(self.db.ids)}", "created_at": "2026-10-06T00:00:00+00:00", **self.payload}
            self.db.rows.setdefault(self.table, []).append(row)
            return SimpleNamespace(data=[row])
        found = [r for r in rows if self._matches(r)]
        if self.ordering:
            key, desc = self.ordering
            found = sorted(found, key=lambda r: str(r.get(key) or ""), reverse=desc)
        return SimpleNamespace(data=found[: self.max_rows] if self.max_rows else found)


class FakeDB:
    def __init__(self):
        self.rows, self.ids = {}, itertools.count(1)

    def table(self, name):
        assert name in LIVE_COLUMNS, f"unexpected table {name}"
        return FakeQuery(self, name)


def make_client():
    db = FakeDB()

    def get_user(authorization):
        assert authorization == "Bearer t", "auth header must be forwarded"
        return SimpleNamespace(id="user-1")

    app = FastAPI()
    app.include_router(build_router(get_user, db))
    return TestClient(app), db


H = {"Authorization": "Bearer t"}


def test_every_domain_round_trips_with_live_columns():
    client, _ = make_client()
    assert set(FORM_BODIES) == set(DOMAINS)
    for slug, body in FORM_BODIES.items():
        created = client.post(f"/health/{slug}", json=body, headers=H)
        assert created.status_code == 201, (slug, created.text)
        listed = client.get(f"/health/{slug}?days=30", headers=H).json()
        assert listed["status"] == "success"
        assert len(listed["entries"]) == 1, slug
        entry = listed["entries"][0]
        assert entry["id"] and entry["date"], slug
        assert "None" not in str(entry) and None not in entry.values(), (slug, entry)


def test_units_are_converted_to_stored_metric_and_back():
    client, db = make_client()
    client.post("/health/weight", json={"weight": "154.3", "date": "2026-10-05T10:00:00Z"}, headers=H)
    client.post("/health/vitals", json={"temperature": "98.6", "blood_pressure": "118/76", "date": "2026-10-05T10:00:00Z"}, headers=H)
    client.post("/health/sleep", json={"duration": 7.5, "quality": 6, "date": "2026-10-05T22:00:00Z"}, headers=H)
    assert abs(db.rows["weight_logs"][0]["weight_kg"] - 70.0) < 0.1
    assert db.rows["vital_signs"][0]["temperature_c"] == 37.0
    assert (db.rows["vital_signs"][0]["systolic_bp"], db.rows["vital_signs"][0]["diastolic_bp"]) == (118, 76)
    assert db.rows["sleep_logs"][0]["duration_minutes"] == 450
    assert client.get("/health/sleep", headers=H).json()["entries"][0]["duration"] == 7.5
    assert client.get("/health/weight", headers=H).json()["entries"][0]["weight"] == 154.3


def test_rows_are_user_scoped_and_marked_user_entered():
    client, db = make_client()
    client.post("/health/hydration", json={"volume": 250}, headers=H)
    row = db.rows["hydration_logs"][0]
    assert row["user_id"] == "user-1" and row["source"] == "user_logged" and row["user_confirmed"] is True


def test_validation_rejects_bad_input():
    client, _ = make_client()
    assert client.post("/health/sleep", json={"duration": 99}, headers=H).status_code == 422
    assert client.post("/health/sleep", json={}, headers=H).status_code == 422
    assert client.post("/health/vitals", json={"blood_pressure": "abc"}, headers=H).status_code == 422
    assert client.post("/health/vitals", json={"notes": "only notes"}, headers=H).status_code == 422
    assert client.post("/health/cycle", json={"phase": "nonsense"}, headers=H).status_code == 422
    assert client.post("/health/mood", json={"mood": 11}, headers=H).status_code == 422
    assert client.post("/health/unknown", json={}, headers=H).status_code == 404
    assert client.get("/health/unknown", headers=H).status_code == 404


def test_cycle_summary_predicts_from_period_starts():
    client, _ = make_client()
    for day in ("2026-07-01", "2026-07-29", "2026-08-27"):
        client.post("/health/cycle", json={"phase": "period", "date": f"{day}T00:00:00Z"}, headers=H)
    summary = client.get("/health/cycle?days=90", headers=H).json()["summary"]
    assert summary["period_start_count"] == 3
    assert summary["average_cycle_length"] == 28.5
    assert summary["last_period"] == "2026-08-27"
    assert "next_predicted" in summary


def test_summary_counts_across_domains():
    client, _ = make_client()
    client.post("/health/sleep", json={"duration": 7}, headers=H)
    client.post("/health/mood", json={"mood": 5}, headers=H)
    summary = client.get("/health/summary", headers=H).json()
    assert summary["categories_with_data"] == 2
    assert summary["total_entries"] == 2
    assert summary["days_tracked"] == 1 and summary["last_update"]


def test_recent_queries_and_suggestions():
    client, db = make_client()
    for text in ("how is my sleep", "how is my sleep", "when is my period"):
        db.rows.setdefault("chat_messages", []).append({"id": text, "user_id": "user-1", "role": "user", "content": text, "created_at": "x"})
    assert client.get("/intelligence/recent-queries?limit=4", headers=H).json()["queries"] == ["how is my sleep", "when is my period"]
    assert len(client.get("/intelligence/suggestions?limit=3", headers=H).json()["suggestions"]) == 3


def test_crisis_wording_in_a_tracker_note_stores_nothing_and_returns_support():
    client, db = make_client()
    for slug, field in (("mood", "notes"), ("symptoms", "notes"), ("medications", "notes")):
        body = {"notes": "I feel like a burden to everyone", "date": "2026-10-05T10:00:00Z", "mood": 3, "name": "x", "symptom": "x"}
        r = client.post(f"/health/{slug}", json=body, headers=H)
        assert r.status_code == 200, slug
        out = r.json()
        assert out["status"] == "safety" and out["saved"] is False and "14416" in out["message"], slug
    assert client.get("/health/mood?days=30", headers=H).json()["entries"] == []


def test_near_misses_in_a_tracker_note_are_saved_normally():
    client, _ = make_client()
    r = client.post("/health/mood", json={"mood": 6, "notes": "this project is a burden on the team", "date": "2026-10-05T10:00:00Z"}, headers=H)
    assert r.status_code == 201


def test_new_passive_phrases_are_crisis_and_near_misses_are_not():
    from safety_engine import assess_safety
    for t in ("I feel like a burden to everyone", "nobody would miss me", "I feel worthless", "I am worthless", "mujhe marna chahta hun", "jeena nahi chahti"):
        assert assess_safety(t).crisis, t
    for t in ("I'm not a burden, the bus was late", "my worthless ex", "the dish is a burden on the table", "nobody would miss the bus"):
        assert not assess_safety(t).crisis, t


def test_a_person_can_delete_their_own_entry_and_only_theirs():
    client, db = make_client()
    created = client.post("/health/weight", json={"weight": "140.5", "date": "2026-10-05T10:00:00Z"}, headers=H).json()["entry"]
    other = {"id": "someone-else", "user_id": "user-2", "weight_kg": 70, "logged_at": "2026-10-05T10:00:00Z"}
    db.rows["weight_logs"].append(other)

    assert client.delete("/health/weight/someone-else", headers=H).status_code == 404   # not theirs: untouched
    assert other in db.rows["weight_logs"]
    assert client.delete("/health/nope/x", headers=H).status_code == 404
    assert client.delete(f"/health/weight/{created['id']}", headers=H).json() == {"status": "success", "deleted": created["id"]}
    assert client.get("/health/weight?days=30", headers=H).json()["entries"] == []
    assert client.delete(f"/health/weight/{created['id']}", headers=H).status_code == 404   # already gone


def _events(db, uid="user-1"):
    return [r for r in db.rows.get("extracted_health_events", []) if r["user_id"] == uid]


def test_delete_removes_the_insights_copy_too():
    client, db = make_client()
    entry = client.post("/health/weight", json={"weight": "154.3", "date": "2026-10-05T10:00:00Z"}, headers=H).json()["entry"]
    assert len(_events(db)) == 1                      # the mirror Insights reads
    assert client.delete(f"/health/weight/{entry['id']}", headers=H).status_code == 200
    assert db.rows["weight_logs"] == [] and _events(db) == []


def test_edit_changes_the_tracker_row_and_the_insights_copy_together():
    client, db = make_client()
    entry = client.post("/health/weight", json={"weight": "154.3", "date": "2026-10-05T10:00:00Z"}, headers=H).json()["entry"]
    edited = client.put(f"/health/weight/{entry['id']}", json={"weight": "150", "date": "2026-10-05T10:00:00Z"}, headers=H)
    assert edited.status_code == 200 and edited.json()["entry"]["weight"] == 150.0
    assert [r["weight_kg"] for r in db.rows["weight_logs"]] == [round(150 / 2.2046226218, 2)]
    events = _events(db)
    assert len(events) == 1 and events[0]["extracted_data"]["weight_kg"] == round(150 / 2.2046226218, 2)
    assert client.get("/health/weight?days=30", headers=H).json()["entries"][0]["weight"] == 150.0
    assert client.put("/health/weight/nope", json={"weight": "150"}, headers=H).status_code == 404


def test_delete_retracts_a_chat_saved_weight_for_the_same_day():
    client, db = make_client()
    entry = client.post("/health/weight", json={"weight": "154.3", "date": "2026-10-05T10:00:00Z"}, headers=H).json()["entry"]
    kg = db.rows["weight_logs"][0]["weight_kg"]
    db.rows["extracted_health_events"].append({"id": "chat-1", "user_id": "user-1", "event_type": "weight", "extraction_status": "confirmed",
                                               "user_confirmed": True, "created_at": "2026-10-05T11:00:00+00:00",
                                               "extracted_data": {"weight_kg": kg, "_prov": {"source": "chat"}}})
    client.delete(f"/health/weight/{entry['id']}", headers=H)
    chat = [r for r in _events(db) if r["id"] == "chat-1"][0]
    assert chat["extraction_status"] == "retracted"


def test_companion_is_told_the_trackers_newest_values_and_nothing_stale():
    from latest_values_block import latest_values_block
    client, db = make_client()
    assert latest_values_block(db, "user-1") == ""                                   # nothing saved: no invented figure
    client.post("/health/weight", json={"weight": "165", "date": "2026-10-04T10:00:00Z"}, headers=H)
    newest = client.post("/health/weight", json={"weight": "154.3", "date": "2026-10-05T10:00:00Z"}, headers=H).json()["entry"]
    assert "weight: 70.0 kg (154.3 lbs)" in latest_values_block(db, "user-1")
    client.put(f"/health/weight/{newest['id']}", json={"weight": "150", "date": "2026-10-05T10:00:00Z"}, headers=H)
    assert "weight: 68.0 kg (150.0 lbs)" in latest_values_block(db, "user-1")
    client.delete(f"/health/weight/{newest['id']}", headers=H)
    assert "weight: 74.8 kg (165.0 lbs)" in latest_values_block(db, "user-1")        # falls back to the older real entry
