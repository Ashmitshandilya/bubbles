"""Notifications: generic text only, quiet hours, cap, dedupe, read state, due-reminder generation, email adapter (mocked)."""
from __future__ import annotations

import random
import re
import string
from datetime import datetime, timezone

import pytest

import clinical_constants as K
import doc_store
import med_schedule as M
import notifications as N
from tests.fake_db import FakeDB
from wellness_common import InputError

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"


def utc(h, m=0, day=8):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    return FakeDB({})


def schedule(db, uid=U1, **kw):
    s = M.normalize_schedule({"name": "Metformin", "dose_label": "500 mg", "times": ["12:00"], "start_date": "2026-09-01", **kw}, utc(0).date())
    s["id"] = kw.get("id", "aaaaaaaaaaaa")
    M.save_schedule(db, uid, s)
    return s


# --- generic text ----------------------------------------------------------------------------------------------------------------

def test_templates_are_generic():
    for kind, (title, body) in N.TEMPLATES.items():
        assert N.is_generic(title) and N.is_generic(body), kind
    assert set(N.TEMPLATES) == set(K.NOTIFY_KINDS)


@pytest.mark.parametrize("bad", [
    "Take 500 mg of Metformin", "You have drunk 750 ml", "Your period is late", "Chest pain logged", "Sleep 6.5 h last night",
    "Time for your ibuprofen", "semaglutide dose day", "Your blood pressure is high", "Mood 3/10", "", "   ", None, 42, "x" * 300,
    "Feeling anxious?", "Your PCOS plan", "heart failure fluid limit",
])
def test_custom_text_with_health_content_is_rejected(bad):
    assert not N.is_generic(bad)


def test_sanitise_replaces_unsafe_text_with_the_template():
    t, b = N.sanitise("med", "Take Metformin 500 mg", "You missed 2 doses of insulin")
    assert (t, b) == N.TEMPLATES["med"]
    assert N.sanitise("system", "Welcome back", "Nice to see you here") == ("Welcome back", "Nice to see you here")


def test_no_stored_notification_ever_has_digits_or_health_words_property(db):
    rng = random.Random(11)
    words = ["insulin", "pain", "mg", "ibuprofen", "pregnant", "ml", "dose", "cramps", "warfarin", "period", "kg", "12", "hello", "water"]
    settings = N.default_settings()
    settings["quiet_hours"]["enabled"] = False
    settings["daily_cap"] = K.NOTIFY_DAILY_CAP_MAX
    for i in range(40):
        junk = " ".join(rng.choice(words + list(string.ascii_lowercase)) for _ in range(rng.randint(1, 6)))
        kind = rng.choice(K.NOTIFY_KINDS)
        n = N.create_notification(db, U1, kind, title=junk, body=junk, dedupe_key=f"k{i}", now=utc(12, i % 59), settings=settings)
        if n:
            for field in (n["title"], n["body"]):
                assert not re.search(r"\d", field) and N.is_generic(field), (junk, field)
    for row in db.tables["health_events"]:
        blob = str(row["data"]["payload"].get("title", "")) + str(row["data"]["payload"].get("body", ""))
        assert not re.search(r"\d", blob)


# --- settings -----------------------------------------------------------------------------------------------------------------------

def test_default_settings_and_validation():
    d = N.default_settings()
    assert d["channels"] == {"in_app": True, "email": False, "push": False} and d["daily_cap"] == 5
    s = N.normalize_settings({"channels": {"email": True}, "quiet_hours": {"start": "22:30"}, "daily_cap": 3, "types": {"water": False},
                              "tz_offset_minutes": 330})
    assert s["channels"]["email"] and s["quiet_hours"]["start"] == "22:30" and s["daily_cap"] == 3 and not s["types"]["water"] and s["tz_offset_minutes"] == 330
    for bad in ({"channels": {"sms": True}}, {"channels": {"email": "yes"}}, {"daily_cap": 99}, {"daily_cap": -1}, {"daily_cap": True},
                {"quiet_hours": {"start": "25:00"}}, {"quiet_hours": "late"}, {"tz_offset_minutes": 9999}, {"types": {"meds": True}}, {"channels": []}):
        with pytest.raises(InputError):
            N.normalize_settings(bad)


def test_quiet_hours_wrap_midnight():
    s = N.default_settings()
    assert N.in_quiet_hours(s, 23 * 60 + 30) and N.in_quiet_hours(s, 3 * 60) and not N.in_quiet_hours(s, 12 * 60) and not N.in_quiet_hours(s, 7 * 60)
    s["quiet_hours"]["enabled"] = False
    assert not N.in_quiet_hours(s, 3 * 60)


def test_corrupt_settings_document_falls_back_to_defaults(db):
    doc_store.put(db, U1, "notification_settings", "me", {"daily_cap": "lots", "channels": "yes"})
    assert N.load_settings(db, U1) == N.default_settings()


# --- create / dedupe / cap / quiet / read --------------------------------------------------------------------------------------------

def test_create_dedupe_cap_quiet_and_type_off(db):
    s = N.default_settings()
    s["daily_cap"] = 2
    first = N.create_notification(db, U1, "water", dedupe_key="a", now=utc(12), settings=s)
    assert first and first["read"] is False and first["kind"] == "water"
    assert N.create_notification(db, U1, "water", dedupe_key="a", now=utc(12, 5), settings=s) is None          # duplicate
    assert N.create_notification(db, U1, "water", dedupe_key="b", now=utc(13), settings=s)
    assert N.create_notification(db, U1, "water", dedupe_key="c", now=utc(14), settings=s) is None              # cap of 2
    assert N.create_notification(db, U1, "water", dedupe_key="c", now=utc(14, 0, day=9), settings=s)            # next day
    assert N.create_notification(db, U2, "water", dedupe_key="a", now=utc(12), settings=s)                      # other user, other counters
    assert N.create_notification(db, U1, "system", dedupe_key="q", now=utc(23, 30), settings={**s, "daily_cap": 9}) is None   # quiet hours
    off = {**s, "daily_cap": 9, "types": {**s["types"], "med": False}}
    assert N.create_notification(db, U1, "med", dedupe_key="m", now=utc(12), settings=off) is None
    with pytest.raises(InputError):
        N.create_notification(db, U1, "bogus", now=utc(12), settings=s)


def test_list_and_mark_read_are_owner_scoped(db):
    s = N.default_settings()
    s["quiet_hours"]["enabled"] = False
    a = N.create_notification(db, U1, "system", dedupe_key="1", now=utc(10), settings=s)
    b = N.create_notification(db, U1, "water", dedupe_key="2", now=utc(11), settings=s)
    other = N.create_notification(db, U2, "system", dedupe_key="1", now=utc(10), settings=s)
    listing = N.list_notifications(db, U1)
    assert listing["unread_count"] == 2 and [n["id"] for n in listing["notifications"]][0] == b["id"]
    assert N.mark_read(db, U1, [other["id"]]) == 0                       # cannot touch another user's
    assert N.list_notifications(db, U2)["unread_count"] == 1
    assert N.mark_read(db, U1, [a["id"], "nope"]) == 1 and N.mark_read(db, U1, [a["id"]]) == 0
    assert N.list_notifications(db, U1, unread_only=True)["notifications"][0]["id"] == b["id"]
    assert N.mark_read(db, U1, all_=True) == 1 and N.list_notifications(db, U1)["unread_count"] == 0


# --- due reminders ---------------------------------------------------------------------------------------------------------------------

def test_generate_due_medicine_reminder_is_generic_and_deduped(db):
    schedule(db, times=["12:00"])
    made = N.generate_due(db, U1, utc(12, 10))
    assert [n["kind"] for n in made] == ["med"]
    text = made[0]["title"] + made[0]["body"]
    assert "Metformin" not in text and "500" not in text
    assert N.generate_due(db, U1, utc(12, 20)) == []                      # same slot: no repeat
    assert N.generate_due(db, U2, utc(12, 10)) == []                      # other user has nothing


def test_generate_due_skips_taken_doses(db):
    s = schedule(db, times=["12:00"])
    M.save_dose_doc(db, U1, {"schedule_id": s["id"], "date": "2026-10-08", "doses": {"12:00": {"status": "taken"}}})
    assert N.generate_due(db, U1, utc(12, 10)) == []


def test_generate_due_water_follows_progress(db):
    made = N.generate_due(db, U1, utc(11, 30))
    assert [n["kind"] for n in made] == ["water"] and made[0]["dedupe_key"] == "water:2026-10-08:11:00"
    assert N.generate_due(db, U1, utc(11, 40)) == []
    # on pace: plenty of water already logged -> no reminder
    db.tables["hydration_logs"] = [{"user_id": U2, "amount_ml": 1500, "drink_type": "water", "logged_at": utc(10).isoformat(), "id": "x", "created_at": "c"}]
    assert N.generate_due(db, U2, utc(11, 30)) == []


def test_generate_due_no_water_for_fluid_restricted_users(db):
    db.tables["medical_conditions"] = [{"user_id": U1, "condition_name": "Heart failure", "id": "c1", "created_at": "2026-01-01"}]
    assert N.generate_due(db, U1, utc(11, 30)) == []


def test_generate_due_winddown_and_quiet_hours(db):
    made = N.generate_due(db, U1, utc(22, 20))
    assert [n["kind"] for n in made] == ["winddown"]
    assert N.generate_due(db, U1, utc(23, 30, day=9)) == []                # inside quiet hours
    assert N.generate_due(db, U1, utc(3, 0, day=9)) == []


def test_generate_due_respects_cap_types_and_timezone(db):
    schedule(db, times=["12:00"])
    s = N.default_settings()
    s["daily_cap"] = 0
    N.save_settings(db, U1, s)
    assert N.generate_due(db, U1, utc(12, 10)) == []
    s.update(daily_cap=5, types={"water": False, "med": True, "winddown": True}, tz_offset_minutes=330)
    N.save_settings(db, U1, s)
    made = N.generate_due(db, U1, utc(6, 40))                      # 12:10 in India: the 12:00 dose is due, keyed by LOCAL day and time
    assert [n["dedupe_key"] for n in made] == ["med:2026-10-08:12:00"]


# --- email (SMTP) and push ---------------------------------------------------------------------------------------------------------------

class FakeSMTP:
    sent: list = []
    fail = False

    def __init__(self, host, port, timeout=5):
        if FakeSMTP.fail:
            raise OSError("smtp down")
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_email_is_off_unless_configured_and_is_fail_soft(db, monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert N.send_email("a@example.com", "Hi", "There", smtp_factory=FakeSMTP) is False and FakeSMTP.sent == []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    assert N.send_email("a@example.com", "Hi", "There", smtp_factory=FakeSMTP) is True and FakeSMTP.sent[0]["To"] == "a@example.com"
    assert N.send_email(None, "Hi", "There", smtp_factory=FakeSMTP) is False
    FakeSMTP.fail = True
    assert N.send_email("a@example.com", "Hi", "There", smtp_factory=FakeSMTP) is False        # never raises


def test_email_channel_only_when_user_enabled_and_body_is_generic(db, monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    s = N.default_settings()
    s["quiet_hours"]["enabled"] = False
    assert N.create_notification(db, U1, "water", dedupe_key="1", now=utc(12), settings=s, email="a@example.com", mailer=FakeSMTP)
    assert FakeSMTP.sent == []
    s["channels"]["email"] = True
    n = N.create_notification(db, U1, "water", dedupe_key="2", now=utc(13), settings=s, email="a@example.com", mailer=FakeSMTP)
    assert n and len(FakeSMTP.sent) == 1 and FakeSMTP.sent[0].get_content().strip() == n["body"]
    FakeSMTP.fail = True
    assert N.create_notification(db, U1, "water", dedupe_key="3", now=utc(14), settings=s, email="a@example.com", mailer=FakeSMTP)   # email failure never blocks


def test_push_is_a_documented_stub():
    assert N.send_web_push({}, "t", "b") == {"sent": False, "reason": "not_configured"}
    assert N.channel_status()["push"]["available"] is False
