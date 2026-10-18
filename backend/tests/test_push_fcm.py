"""Phone notifications (Firebase Cloud Messaging): off until configured, two yeses, generic text, one owner per phone, gone tokens
removed, test cooldown, background sweep, and the HTTP routes."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import consent_ledger
import med_schedule as M
import notifications as N
import push_fcm as P
import wellness_api
from tests.fake_db import FakeDB

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
TOK_A, TOK_B = "fcm-token-a:" + "A" * 140, "fcm-token-b:" + "B" * 140
ACCOUNT = {"type": "service_account", "project_id": "bubbles-test", "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n",
           "client_email": "push@bubbles-test.iam.gserviceaccount.com"}


def utc(h, m=0, day=8):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)


class Recorder:
    def __init__(self, status=200, body=None):
        self.calls, self.status, self.body = [], status, body or {"name": "projects/bubbles-test/messages/1"}

    def __call__(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.status, self.body


@pytest.fixture()
def db():
    consent_ledger._cache.clear()
    P._last_test.clear()
    return FakeDB({"t1": U1, "t2": U2})


@pytest.fixture()
def fcm(monkeypatch):
    """A configured server whose FCM calls are recorded instead of sent."""
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps(ACCOUNT))
    monkeypatch.setattr(P, "_access_token", lambda: "oauth-token")
    rec = Recorder()
    monkeypatch.setattr(P, "_http_post", rec)
    return rec


def both_yeses(db, uid=U1, **types):
    N.save_settings(db, uid, N.normalize_settings({"channels": {"push": True}, "quiet_hours": {"enabled": False}, "types": types}))
    consent_ledger.set_purpose(db, uid, "push_notifications", True)


# --- configuration ------------------------------------------------------------------------------------------------------------------

def test_off_until_the_service_account_is_set(db, monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    assert not P.configured() and N.channel_status()["push"]["available"] is False
    assert P.start_background(db) is False
    both_yeses(db)
    assert P.allowed(db, U1, N.load_settings(db, U1)) is False


@pytest.mark.parametrize("raw,ok", [
    (json.dumps(ACCOUNT), True),
    (base64.b64encode(json.dumps(ACCOUNT).encode()).decode(), True),
    (json.dumps({**ACCOUNT, "type": "authorized_user"}), False),
    (json.dumps({**ACCOUNT, "private_key": ""}), False),
    ("not json at all", False),
    ("{broken", False),
])
def test_only_a_real_service_account_counts(monkeypatch, raw, ok):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", raw)
    assert P.configured() is ok
    assert N.channel_status()["push"]["available"] is ok


# --- devices ------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "short", "has spaces in it but is long enough", "x" * 5000, 42, "<script>alert(1)</script>xxxxxx"])
def test_malformed_tokens_are_refused(db, bad):
    with pytest.raises(ValueError):
        P.register_device(db, U1, bad)


def test_register_refresh_and_remove(db):
    P.register_device(db, U1, TOK_A, now=utc(9))
    P.register_device(db, U1, TOK_A, now=utc(10))
    [device] = P.list_devices(db, U1)
    assert device["token"] == TOK_A and device["added_at"] == utc(9).isoformat() and device["seen_at"] == utc(10).isoformat()
    with pytest.raises(ValueError):
        P.register_device(db, U1, TOK_B, platform="ios")
    assert P.remove_device(db, U1, TOK_A) is True and P.list_devices(db, U1) == []
    assert P.remove_device(db, U1, "nope") is False


def test_at_most_five_phones_and_the_oldest_goes(db):
    tokens = [f"fcm-token-{i}:" + "C" * 60 for i in range(7)]
    for i, t in enumerate(tokens):
        P.register_device(db, U1, t, now=utc(8 + i))
    kept = {d["token"] for d in P.list_devices(db, U1)}
    assert kept == set(tokens[2:])


def test_a_phone_belongs_to_whoever_registered_it_last(db):
    """Shared phone: after the second person signs in, the first person's reminders must never show on it."""
    P.register_device(db, U1, TOK_A)
    P.register_device(db, U2, TOK_A)
    assert P.list_devices(db, U1) == [] and [d["token"] for d in P.list_devices(db, U2)] == [TOK_A]


def test_another_users_token_is_never_removed_by_remove(db):
    P.register_device(db, U2, TOK_A)
    assert P.remove_device(db, U1, TOK_A) is False
    assert [d["token"] for d in P.list_devices(db, U2)] == [TOK_A]


# --- sending ------------------------------------------------------------------------------------------------------------------------

def test_needs_both_the_switch_and_the_consent(db, fcm):
    P.register_device(db, U1, TOK_A)
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}, "quiet_hours": {"enabled": False}}))
    assert N.create_notification(db, U1, "water", now=utc(12)) and fcm.calls == []          # switch on, no consent
    consent_ledger.set_purpose(db, U1, "push_notifications", True)
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": False}, "quiet_hours": {"enabled": False}}))
    assert N.create_notification(db, U1, "med", now=utc(13)) and fcm.calls == []            # consent, switch off
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}, "quiet_hours": {"enabled": False}}))
    P.register_device(db, U1, TOK_A)                                                          # turning the switch off forgot the phone
    assert N.create_notification(db, U1, "winddown", now=utc(14))
    assert len(fcm.calls) == 1
    consent_ledger.set_purpose(db, U1, "push_notifications", False)                           # withdrawing stops it at once
    assert N.create_notification(db, U1, "system", now=utc(15)) and len(fcm.calls) == 1


def test_the_message_is_generic_and_private(db, fcm):
    both_yeses(db)
    P.register_device(db, U1, TOK_A)
    N.create_notification(db, U1, "med", title="Take Metformin 500 mg", body="You missed 2 doses of insulin", now=utc(12))
    url, payload, headers = fcm.calls[0]
    assert url == "https://fcm.googleapis.com/v1/projects/bubbles-test/messages:send" and headers["Authorization"] == "Bearer oauth-token"
    msg = payload["message"]
    assert (msg["notification"]["title"], msg["notification"]["body"]) == ("Bubbles", "You have a reminder in Bubbles.")   # not even "Medicine check-in" on a lock screen
    assert msg["data"] == {"kind": "med"} and msg["token"] == TOK_A
    assert msg["android"]["notification"]["visibility"] == "PRIVATE" and msg["android"]["ttl"] == "3600s"
    text = json.dumps({k: v for k, v in msg.items() if k != "token"})
    assert not re.search(r"metformin|insulin|dose|\b500\b|mg", text, re.I)


def test_quiet_hours_and_cap_also_hold_for_the_phone(db, fcm):
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}, "daily_cap": 1}))   # default quiet hours 23:00-07:00
    consent_ledger.set_purpose(db, U1, "push_notifications", True)
    P.register_device(db, U1, TOK_A)
    assert N.create_notification(db, U1, "water", now=utc(23, 30)) is None
    assert N.create_notification(db, U1, "water", now=utc(12)) and N.create_notification(db, U1, "med", now=utc(13)) is None
    assert len(fcm.calls) == 1


def test_a_gone_token_is_deleted_and_other_failures_keep_it(db, fcm):
    both_yeses(db)
    P.register_device(db, U1, TOK_A)
    fcm.status, fcm.body = 500, {"error": {"message": "backend error"}}
    assert P.send_to_user(db, U1, "water") == {"sent": 0, "removed": 0}
    assert len(P.list_devices(db, U1)) == 1
    fcm.status, fcm.body = 404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}
    assert P.send_to_user(db, U1, "water") == {"sent": 0, "removed": 1}
    assert P.list_devices(db, U1) == []


def test_sending_never_raises(db, fcm, monkeypatch):
    both_yeses(db)
    P.register_device(db, U1, TOK_A)

    def boom(*_a):
        raise OSError("network down")

    monkeypatch.setattr(P, "_http_post", boom)
    assert N.create_notification(db, U1, "water", now=utc(12))            # the in-app copy still exists
    monkeypatch.setattr(P, "_access_token", lambda: (_ for _ in ()).throw(RuntimeError("bad key")))
    assert P.send_to_user(db, U1, "water")["reason"] == "not_ready"


def test_test_notification_needs_both_yeses_and_waits_a_minute(db, fcm):
    P.register_device(db, U1, TOK_A)
    with pytest.raises(PermissionError):
        P.send_test(db, U1)
    both_yeses(db)
    clock = iter([100.0, 130.0, 161.0])
    assert P.send_test(db, U1, clock=lambda: next(clock))["sent"] == 1
    assert P.send_test(db, U1, clock=lambda: next(clock))["reason"] == "wait"
    assert P.send_test(db, U1, clock=lambda: next(clock))["sent"] == 1
    assert fcm.calls[0][1]["message"]["notification"] == {"title": "Bubbles", "body": "Phone reminders are working."}


# --- background sweep ---------------------------------------------------------------------------------------------------------------

def test_sweep_sends_due_reminders_only_to_people_who_said_yes(db, fcm):
    for uid in (U1, U2):
        s = M.normalize_schedule({"name": "Metformin", "dose_label": "500 mg", "times": ["12:00"], "start_date": "2026-09-01"}, utc(0).date())
        s["id"] = "aaaaaaaaaaaa"
        M.save_schedule(db, uid, s)
    both_yeses(db, U1, water=False, winddown=False)
    N.save_settings(db, U2, N.normalize_settings({"channels": {"push": True}, "quiet_hours": {"enabled": False}, "types": {"water": False, "winddown": False}}))
    P.register_device(db, U1, TOK_A)
    P.register_device(db, U2, TOK_B)                                     # U2 never said yes in the consent log
    assert P.users_with_devices(db) == [U1, U2]
    assert P.sweep(db, utc(12, 10)) == {"checked": 1, "created": 1, "revoked": 1, "errors": 0, "partial": False}   # U2 has no yes: phone forgotten
    assert [c[1]["message"]["token"] for c in fcm.calls] == [TOK_A]
    assert P.sweep(db, utc(12, 15)) == {"checked": 1, "created": 0, "revoked": 0, "errors": 0, "partial": False}      # same slot: no repeat
    assert len(fcm.calls) == 1


def test_sweep_interval_is_bounded(monkeypatch):
    monkeypatch.setenv("PUSH_SWEEP_SECONDS", "5")
    assert P.sweep_interval() == P.SWEEP_MIN_S
    monkeypatch.setenv("PUSH_SWEEP_SECONDS", "soon")
    assert P.sweep_interval() == P.SWEEP_DEFAULT_S


def test_delete_everything_forgets_the_phone(db):
    import doc_store

    P.register_device(db, U1, TOK_A)
    doc_store.delete_everything(db, U1)
    assert P.list_devices(db, U1) == [] and P.users_with_devices(db) == []


# --- HTTP ---------------------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def client(db):
    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        try:
            return db.auth.get_user(authorization[7:]).user
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    app = FastAPI()
    app.include_router(wellness_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False)


def test_routes_register_test_and_forget(db, client, fcm):
    h = {"Authorization": "Bearer t1"}
    bad = client.post("/notifications/devices", json={"token": "x"}, headers=h)
    assert bad.status_code == 422 and isinstance(bad.json()["detail"], str)
    assert client.post("/notifications/devices", json={"token": TOK_A, "platform": "ios"}, headers=h).status_code == 422
    assert client.post("/notifications/devices", json={"token": TOK_A}, headers=h).status_code == 422   # no yes on record: nothing stored
    assert P.list_devices(db, U1) == []
    client.put("/notifications/settings", json={"channels": {"push": True}, "quiet_hours": {"enabled": False}}, headers=h)
    ok = client.post("/notifications/devices", json={"token": TOK_A}, headers=h).json()
    assert ok == {"status": "success", "registered": True, "devices": 1, "available": True}
    saved = client.get("/notifications/settings", headers=h).json()
    assert saved["settings"]["channels"]["push"] is True and saved["channels"]["push"]["available"] is True
    assert consent_ledger.is_granted(db, U1, "push_notifications") is True                       # the switch is logged as the yes
    assert client.post("/notifications/push/test", headers=h).json()["sent"] == 1
    assert client.post("/notifications/devices/remove", json={"token": TOK_A}, headers=h).json()["removed"] is True
    client.put("/notifications/settings", json={"channels": {"push": False}}, headers=h)
    assert consent_ledger.is_granted(db, U1, "push_notifications") is False
    assert [e["purpose"] for e in consent_ledger.history(db, U1)].count("push_notifications") == 2
