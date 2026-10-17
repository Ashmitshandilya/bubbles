from health_event_projection import project_confirmed_event


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.filters = []
        self.payload = None
        self.selection = None

    def select(self, value):
        self.selection = value
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _value):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    # Deliberately no .single(): real postgrest insert builders do not have it.
    def execute(self):
        if self.payload is not None:
            self.db.inserts.append((self.table, self.payload))
            return _Result([{"id": "canonical-1"}])
        return _Result([])


class _DB:
    def __init__(self):
        self.inserts = []

    def table(self, name):
        return _Query(self, name)


def test_confirmed_symptom_projects_to_ledger_and_domain_table():
    db = _DB()
    result = project_confirmed_event(
        db=db,
        user_id="user-1",
        event_id="event-1",
        event_type="symptom",
        extracted_data={"symptom": "headache", "severity": "moderate"},
        confidence=0.92,
    )
    assert result["status"] == "projected"
    assert [table for table, _ in db.inserts] == ["health_events", "symptoms"]


def test_projection_is_separate_from_unconfirmed_staging():
    db = _DB()
    project_confirmed_event(
        db=db,
        user_id="user-1",
        event_id="event-2",
        event_type="weight",
        extracted_data={"amount": 62.5, "unit": "kg"},
        confidence=0.99,
    )
    ledger = db.inserts[0][1]
    assert ledger["source"] == "bubbles_confirmed_extraction"
    assert ledger["source_extracted_event_id"] == "event-2"


def test_projection_uses_canonical_schema_fields_for_sleep():
    db = _DB()
    result = project_confirmed_event(db=db, user_id="user-1", event_id="event-sleep", event_type="sleep", extracted_data={"amount": 7.0, "unit": "hours", "date": "2026-09-19"}, confidence=0.9)
    assert result["domain_table"] == "sleep_logs"
    row = db.inserts[-1][1]
    assert row["sleep_date"] == "2026-09-19"
    assert row["duration_minutes"] == 420.0
    assert "sleep_quality" in row


def test_projection_maps_vitals_to_real_columns():
    db = _DB()
    result = project_confirmed_event(db=db, user_id="user-1", event_id="event-vital", event_type="vital_sign", extracted_data={"name": "heart rate", "value": 78, "unit": "bpm"}, confidence=0.95)
    assert result["domain_table"] == "vital_signs"
    row = db.inserts[-1][1]
    assert row["heart_rate_bpm"] == 78
    assert "metric" not in row


def test_a_bare_today_is_stamped_now_not_midnight():
    from datetime import datetime, timezone
    from health_event_projection import _occurred_at
    today = datetime.now(timezone.utc).date().isoformat()
    assert _occurred_at({"date": today}) > f"{today}T00:00:01"           # sorts after anything logged earlier today
    assert _occurred_at({"date": "2026-09-19"}) == "2026-09-19T00:00:00+00:00"   # a past day keeps its day
    assert _occurred_at({"date": today, "time": "07:30:00"}).startswith(f"{today}T07:30")
