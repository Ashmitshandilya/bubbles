"""Analytics, export and projection guards: only live positive observations count.

Rows with no extraction_status key are treated as pending (live), so the legacy test shapes keep working.
"""
from datetime import datetime, timedelta, timezone

import pytest

import organ_intelligence
from advanced_cycle_intelligence import analyze_advanced
from cycle_intelligence import analyze as analyze_cycle
from doctor_timeline import build_timeline, prepare_visit
from health_event_projection import project_confirmed_event
from interoperability import export_bundle, to_fhir_resource as bundle_resource
from longitudinal_health_analysis import analyze as longitudinal
from medication_intelligence import medication_overview
from organ_intelligence import build_body_system_intelligence
from pattern_engine import analyze, normalize_events, recurring_patterns, temporal_correlations
from provider_integration import to_fhir_resource as provider_resource
from womens_health_intelligence import classify_womens_health

NOW = datetime.now(timezone.utc)


def row(event_type, data, *, days_ago=0, status=None, confirmed=False, id=None, assertion=None, subject=None):
    d = dict(data)
    prov = {}
    if assertion:
        prov["assertion"] = assertion
    if subject:
        prov["subject"] = subject
    if prov:
        d["_prov"] = prov
    r = {
        "id": id or f"{event_type}-{days_ago}-{len(d)}",
        "event_type": event_type,
        "extracted_data": d,
        "confidence": 0.9,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "user_confirmed": confirmed,
    }
    if status:
        r["extraction_status"] = status
    return r


def screen(concepts, **kw):
    return row("wellness_checkin", {"pertinent_negatives": concepts, "screen": "symptom_screen"}, **kw)


# ---------------------------------------------------------------- pattern_engine

def test_normalize_events_keeps_only_live_positive_observations():
    rows = [
        row("symptom", {"symptom": "headache"}, id="live"),
        row("symptom", {"symptom": "headache"}, status="pending", id="pending"),
        row("symptom", {"symptom": "chest pain"}, status="rejected", id="rejected"),
        row("symptom", {"symptom": "chest pain"}, status="retracted", id="retracted"),
        row("symptom", {"symptom": "chest pain", "present": False}, id="negated"),
        row("symptom", {"symptom": "chest pain"}, assertion="hypothetical", id="hypothetical"),
        row("symptom", {"symptom": "diabetes"}, subject="other", id="other"),
        screen(["chest pain"], id="screen"),
    ]
    assert [r["id"] for r in normalize_events(rows)] == ["live", "pending"]


def test_normalize_events_passes_normalized_rows_through():
    raw = [row("symptom", {"symptom": "headache"}, days_ago=2, id="h1")]
    once = normalize_events(raw)
    twice = normalize_events(once)
    assert once[0]["subject"] == "headache"
    assert twice[0]["subject"] == "headache"  # used to collapse to the event_type ("symptom")
    assert twice[0]["data"] == {"symptom": "headache"}


def test_correlations_over_normalized_rows_keep_real_subjects():
    raw = []
    for i, d in enumerate((10, 6, 2)):
        raw.append(row("sleep", {"symptom": "poor sleep"}, days_ago=d, id=f"s{i}"))
        raw.append(row("symptom", {"symptom": "headache"}, days_ago=d + 1, id=f"h{i}"))
    found = temporal_correlations(normalize_events(raw), min_pairs=3)
    assert found
    assert {found[0]["a"]["subject"], found[0]["b"]["subject"]} == {"poor sleep", "headache"}


def test_subject_reads_compact_data_key():
    compact = [{"type": "symptom", "data": {"symptom": "nausea"}, "created_at": NOW.isoformat()}]
    assert normalize_events(compact)[0]["subject"] == "nausea"


def test_compact_rows_are_filtered_too():
    compact = [
        {"type": "symptom", "data": {"symptom": "nausea"}, "created_at": NOW.isoformat(), "extraction_status": "rejected"},
        {"type": "wellness_checkin", "data": {"pertinent_negatives": ["nausea"]}, "created_at": NOW.isoformat()},
    ]
    assert normalize_events(compact) == []


def test_normalize_events_prefers_the_event_date_over_ingestion_time():
    rows = [row("symptom", {"symptom": "headache", "date": "2026-09-01"}, days_ago=0)]
    assert normalize_events(rows)[0]["created_at"].date().isoformat() == "2026-09-01"


def test_normalize_events_falls_back_to_created_at_for_unparsable_date():
    rows = [row("symptom", {"symptom": "headache", "date": "yesterday"}, days_ago=3)]
    assert normalize_events(rows)[0]["created_at"].date() == (NOW - timedelta(days=3)).date()


def test_analyze_ignores_denials_and_keeps_its_shape():
    rows = [row("symptom", {"symptom": "cramps"}, days_ago=d, id=f"c{d}") for d in (9, 6, 3)]
    rows += [row("symptom", {"symptom": "chest pain", "present": False}, days_ago=d, id=f"n{d}") for d in (8, 5, 2)]
    rows += [screen(["chest pain"], days_ago=d, id=f"s{d}") for d in (7, 4, 1)]
    out = analyze(rows, days=30)
    assert set(out) == {"period_days", "event_count", "patterns", "correlations", "trend"}
    assert out["event_count"] == 3
    assert [p["subject"] for p in out["patterns"]] == ["cramps"]
    assert out["correlations"] == []


# ---------------------------------------------------------------- cycle

def test_cycle_symptoms_come_only_from_live_cycle_rows():
    events = [
        row("menstrual_symptom", {"symptom": "cramps"}),
        row("menstrual_symptom", {"name": "bloating"}),
        row("menstrual_symptom", {"symptom": "spotting", "present": False}),
        row("menstrual_symptom", {"symptom": "nausea"}, status="rejected"),
        row("symptom", {"symptom": "headache"}),
        screen(["chest pain"]),
    ]
    assert analyze_cycle(events)["symptoms"]["recent_unique"] == ["bloating", "cramps"]


def test_period_label_is_not_listed_as_a_symptom():
    out = analyze_cycle([row("period", {"name": "period", "symptom": "menstrual flow", "is_start": True, "date": "2026-09-01"})])
    assert out["symptoms"]["recent_unique"] == ["menstrual flow"]


@pytest.mark.parametrize("value,expected", [
    (True, 1), ("true", 1), ("yes", 1), ("2026-09-01", 1),
    (False, 0), ("false", 0), ("False", 0), ("no", 0), (None, 0), (0, 0), ("", 0),
])
def test_cycle_start_flags_are_real_booleans(value, expected):
    event = row("period", {"is_start": value, "date": "2026-09-01"})
    assert analyze_cycle([event])["cycle"]["period_start_count"] == expected
    assert analyze_advanced([event])["period_starts"] == expected


def test_denied_or_rejected_period_starts_are_not_counted():
    events = [
        row("period", {"is_start": True, "date": "2026-08-01"}),
        row("period", {"is_start": True, "date": "2026-08-29"}, status="rejected"),
        row("period", {"is_start": True, "date": "2026-09-26", "present": False}),
    ]
    assert analyze_cycle(events)["cycle"]["period_start_count"] == 1
    assert analyze_advanced(events)["period_starts"] == 1


# ---------------------------------------------------------------- longitudinal / women's / medication / organ

def test_longitudinal_skips_non_live_rows():
    events = [
        row("sleep", {"hours": 7}, days_ago=1),
        row("symptom", {"symptom": "chest pain", "present": False}, days_ago=1),
        row("symptom", {"symptom": "chest pain"}, days_ago=1, status="rejected"),
        screen(["chest pain"], days_ago=1),
    ]
    out = longitudinal(events, 30)
    assert out["data_quality"]["events_used"] == 1
    assert out["domains"]["symptom"]["coverage_status"] == "missing"
    assert "other" not in out["domains"]


def test_womens_health_ignores_denials_and_provenance_text():
    events = [
        row("symptom", {"symptom": "pregnancy symptoms", "present": False}),
        row("symptom", {"symptom": "menopause"}, status="rejected"),
        {"event_type": "symptom", "extracted_data": {"name": "fatigue", "_prov": {"key": "menopause check"}}},
        row("cycle", {}),
    ]
    topics = classify_womens_health(events)["topics"]
    assert topics["cycle"] == 1
    assert topics["pregnancy"] == 0
    assert topics["menopause"] == 0


def test_medication_overview_counts_only_live_rows():
    events = [
        row("medication", {"name": "aspirin"}),
        row("medication", {"name": "ibuprofen", "present": False}),
        row("supplement", {"name": "iron"}, status="rejected"),
    ]
    out = medication_overview(events)
    assert out["medications"] == ["aspirin"]
    assert out["count"] == 1


def test_organ_snapshot_skips_metadata_and_non_live_and_newest_wins(monkeypatch):
    captured = {}
    monkeypatch.setattr(organ_intelligence, "assess_all", lambda snapshot: captured.update(snapshot) or [])
    events = [  # newest first, as the readers deliver them
        {"id": "new", "event_type": "lifestyle", "created_at": "2026-10-07T00:00:00Z", "extracted_data": {"bmi": 22, "_prov": {"assertion": "present"}}},
        {"id": "old", "event_type": "lifestyle", "created_at": "2026-09-01T00:00:00Z", "extracted_data": {"bmi": 31}},
        {"id": "neg", "event_type": "lifestyle", "created_at": "2026-10-08T00:00:00Z", "extracted_data": {"smoking_status": "current", "present": False}},
    ]
    build_body_system_intelligence(events)
    assert captured["bmi"] == 22
    assert "_prov" not in captured
    assert "smoking_status" not in captured


# ---------------------------------------------------------------- doctor timeline

def test_doctor_timeline_separates_pertinent_negatives_from_events():
    events = [
        row("symptom", {"symptom": "headache", "date": "2026-10-01"}, id="a", confirmed=True),
        row("symptom", {"symptom": "chest pain"}, status="rejected", id="b"),
        row("symptom", {"symptom": "nausea", "present": False}, id="c"),
        screen(["chest pain", "Nausea"], id="d"),
        screen(["nausea", "dizziness"], id="e", days_ago=2),
        screen(["fever"], status="rejected", id="f"),
    ]
    timeline = build_timeline(events)
    assert [e["id"] for e in timeline["events"]] == ["a"]
    assert timeline["count"] == 1
    assert timeline["pertinent_negatives"] == ["chest pain", "Nausea", "dizziness"]
    first = timeline["events"][0]
    assert first["extraction_status"] == "pending"
    assert first["user_confirmed"] is True
    assert first["date"].startswith("2026-10-01")
    assert "_prov" not in first["details"]


def test_visit_prep_counts_positives_only():
    events = [
        row("symptom", {"symptom": "headache"}, id="a"),
        row("symptom", {"symptom": "chest pain", "present": False}, id="b"),
        screen(["chest pain"], id="c"),
    ]
    visit = prepare_visit(events, "headaches")
    assert visit["visit_summary"]["frequent_event_types"] == [("symptom", 1)]
    assert visit["visit_summary"]["event_count"] == 1
    assert visit["timeline"]["pertinent_negatives"] == ["chest pain"]


# ---------------------------------------------------------------- FHIR export

def test_export_bundle_exports_only_live_positive_rows():
    events = [
        row("symptom", {"symptom": "headache"}, id="a"),
        row("symptom", {"symptom": "chest pain", "present": False}, id="b"),
        row("symptom", {"symptom": "nausea"}, status="rejected", id="c"),
        screen(["dizziness"], id="d"),
    ]
    bundle = export_bundle(events)
    assert bundle["total"] == 1
    assert [e["resource"]["id"] for e in bundle["entry"]] == ["a"]


def test_denial_is_never_a_condition():
    denial = row("symptom", {"symptom": "chest pain", "present": False}, id="b")
    for resource in (bundle_resource(denial), provider_resource(denial)):
        assert resource["resourceType"] == "Observation"
        assert resource["valueCodeableConcept"] == {"text": "absent"}
    negated_condition = row("medical_condition", {"name": "diabetes"}, assertion="negated")
    assert bundle_resource(negated_condition)["resourceType"] == "Observation"
    assert provider_resource(negated_condition)["resourceType"] == "Observation"


def test_fhir_verification_status_follows_user_confirmation():
    pending = bundle_resource(row("symptom", {"symptom": "headache"}))
    confirmed = bundle_resource(row("symptom", {"symptom": "headache"}, confirmed=True))
    assert pending["resourceType"] == "Condition"
    assert pending["verificationStatus"]["coding"][0]["code"] == "unconfirmed"
    assert confirmed["verificationStatus"]["coding"][0]["code"] == "confirmed"
    assert {"system": "https://bubbles.local/verification", "code": "confirmed"} in confirmed["meta"]["tag"]
    assert provider_resource(row("lab_result", {"name": "Hb"}, confirmed=True))["verificationStatus"]["text"] == "confirmed"
    assert provider_resource(row("lab_result", {"name": "Hb"}))["verificationStatus"]["text"] == "unconfirmed"


def test_provider_value_is_whitelisted_and_dead_rows_are_not_exchanged():
    ok = provider_resource(row("lab_result", {"name": "Hb", "value": 13}, assertion="present"))
    assert ok["value"] == {"name": "Hb", "value": 13}
    for dead in (row("lab_result", {"name": "Hb"}, status="rejected"), screen(["fever"]), row("symptom", {"symptom": "x"}, subject="other")):
        assert provider_resource(dead)["resourceType"] == "OperationOutcome"


# ---------------------------------------------------------------- projection

class _R:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, db, table):
        self.db, self.table, self.payload = db, table, None

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            self.db.inserts.append((self.table, self.payload))
            return _R([{"id": "id-1"}])
        return _R([])


class _DB:
    def __init__(self):
        self.inserts = []

    def table(self, name):
        return _Q(self, name)


def project(event_type, data, event_id="e1"):
    db = _DB()
    result = project_confirmed_event(db=db, user_id="u", event_id=event_id, event_type=event_type, extracted_data=data, confidence=0.9)
    return db, result


@pytest.mark.parametrize("event_type,data", [
    ("symptom", {"symptom": "chest pain", "present": False}),
    ("allergy", {"name": "penicillin", "present": False}),
    ("medication", {"name": "aspirin", "_prov": {"assertion": "negated"}}),
    ("medical_condition", {"name": "diabetes", "_prov": {"assertion": "hypothetical"}}),
    ("symptom", {"symptom": "headache", "_prov": {"subject": "other"}}),
])
def test_non_positive_confirmed_event_is_ledger_only(event_type, data):
    db, result = project(event_type, data)
    assert result["status"] == "ledger_only_non_positive"
    assert result["domain_table"] is None
    assert [table for table, _ in db.inserts] == ["health_events"]


def test_denial_ledger_row_keeps_present_false_and_titles_the_denial():
    db, _ = project("symptom", {"symptom": "chest pain", "present": False, "_prov": {"assertion": "negated"}})
    ledger = db.inserts[0][1]
    assert ledger["title"] == "No chest pain"
    assert ledger["data"]["present"] is False
    assert ledger["data"]["_prov"]["assertion"] == "negated"


def test_positive_event_with_provenance_projects_without_leaking_metadata():
    db, result = project("symptom", {"symptom": "headache", "severity": 4, "_prov": {"assertion": "present", "subject": "self", "key": "k"}})
    assert result["status"] == "projected"
    assert [table for table, _ in db.inserts] == ["health_events", "symptoms"]
    domain_row = db.inserts[1][1]
    assert domain_row["symptom_name"] == "headache"
    assert not any(str(key).startswith("_") for key in domain_row)
    assert db.inserts[0][1]["data"]["_prov"]["key"] == "k"  # the ledger keeps the audit trail


@pytest.mark.parametrize("event_type,table", [("activity", "activity_logs"), ("exercise", "exercise_logs")])
def test_text_intensity_projects_for_activity_and_exercise(event_type, table):
    db, result = project(event_type, {"name": "yoga", "duration_minutes": 30, "severity": "moderate"})
    assert result["domain_table"] == table
    assert db.inserts[-1][1]["intensity"] == "moderate"


def test_allergy_text_severity_projects():
    db, result = project("allergy", {"name": "peanut", "severity": "mild"})
    assert result["domain_table"] == "allergies"
    assert db.inserts[-1][1]["severity"] == "mild"


def test_mood_intensity_is_still_an_integer_between_1_and_10():
    db, result = project("mood", {"name": "calm", "severity": "7"})
    assert result["domain_table"] == "mood_logs"
    assert db.inserts[-1][1]["intensity"] == 7


def test_validation_error_leaves_no_half_projected_event():
    db = _DB()
    with pytest.raises(ValueError):
        project_confirmed_event(db=db, user_id="u", event_id="e9", event_type="mood", extracted_data={"name": "stress", "severity": 0}, confidence=0.9)
    assert db.inserts == []  # no ledger row, so a corrected retry is not short-circuited as already_projected


def test_daily_logged_measurements_do_not_create_confident_correlations():
    """Sleep/water/steps are logged every day, so they co-occur with everything by construction."""
    raw = []
    for d in range(14):
        raw.append(row("sleep", {"name": "sleep", "hours": 7, "duration_minutes": 420}, days_ago=d, id=f"s{d}"))
        raw.append(row("hydration", {"name": "water", "amount_ml": 1800}, days_ago=d, id=f"w{d}"))
        raw.append(row("activity", {"name": "walking", "steps": 6000}, days_ago=d, id=f"a{d}"))
    assert temporal_correlations(normalize_events(raw), min_pairs=3) == []
    assert not [p for p in recurring_patterns(normalize_events(raw)) if p.get("event_type") in {"sleep", "hydration", "activity"}]
