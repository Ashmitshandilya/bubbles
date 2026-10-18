"""Phone reminders, the hard cases: the cron endpoint and its secret, replays, withdrawal in flight, FCM failing, other people's
tokens, garbage input and what a notification may contain. The happy paths live in test_push_fcm.py."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import consent
import consent_ledger
import data_rights
import doc_store
import hydration_engine as H
import med_schedule as M
import notifications as N
import push_api
import push_fcm as P
import wellness_api
from tests.fake_db import FakeDB

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
TOK_A, TOK_B = "fcm-token-a:" + "A" * 140, "fcm-token-b:" + "B" * 140
ACCOUNT = {"type": "service_account", "project_id": "bubbles-test", "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n",
           "client_email": "push@bubbles-test.iam.gserviceaccount.com"}
SECRET = "s3cret-value-for-tests"
NO_QUIET = {"enabled": False}
H1, H2 = {"Authorization": "Bearer t1"}, {"Authorization": "Bearer t2"}


def utc(h, m=0, day=8):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)


class Recorder:
    def __init__(self, status=200, body=None, exc=None):
        self.calls, self.status, self.body, self.exc = [], status, body or {"name": "x"}, exc

    def __call__(self, url, payload, headers):
        self.calls.append(payload)
        if self.exc:
            raise self.exc
        return self.status, self.body

    @property
    def tokens(self):
        return [c["message"]["token"] for c in self.calls]


@pytest.fixture()
def db():
    consent._cache.clear()
    P._last_test.clear()
    return FakeDB({"t1": U1, "t2": U2})


@pytest.fixture()
def fcm(monkeypatch):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps(ACCOUNT))
    monkeypatch.setattr(P, "_access_token", lambda: "oauth")
    rec = Recorder()
    monkeypatch.setattr(P, "_http_post", rec)
    return rec


def opt_in(db, uid=U1, token=TOK_A, **extra):
    """Both yeses and one registered phone."""
    N.save_settings(db, uid, N.normalize_settings({"channels": {"push": True}, "quiet_hours": NO_QUIET, **extra}))
    consent_ledger.set_purpose(db, uid, "push_notifications", True)
    P.register_device(db, uid, token)


def med_schedule(db, uid=U1, time="12:00"):
    s = M.normalize_schedule({"name": "Metformin", "dose_label": "500 mg", "times": [time], "start_date": "2026-09-01"}, utc(0).date())
    s["id"] = "aaaaaaaaaaaa"
    M.save_schedule(db, uid, s)


def at_noon(monkeypatch):
    """Make the scheduler think it is 12:10 UTC on the 8th, whatever the real clock says."""
    real = N.generate_due
    monkeypatch.setattr(N, "generate_due", lambda db_, uid, now=None, **kw: real(db_, uid, utc(12, 10), **kw))


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
    app.include_router(data_rights.build_router(get_user, db))
    app.include_router(push_api.build_router(db))
    return TestClient(app, raise_server_exceptions=False)


# --- who may register or remove a token ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/notifications/devices", "/notifications/devices/remove", "/notifications/push/test"])
def test_unauthenticated_requests_are_refused(client, db, path):
    for headers in ({}, {"Authorization": "Bearer nobody"}, {"Authorization": "garbage"}):
        assert client.post(path, json={"token": TOK_A}, headers=headers).status_code == 401
    assert doc_store.list_docs(db, U1, P.DEVICE_KIND) == []


def test_another_person_cannot_remove_my_token(db, client, fcm):
    opt_in(db)
    assert client.post("/notifications/devices/remove", json={"token": TOK_A}, headers=H2).json()["removed"] is False
    assert [d["token"] for d in P.list_devices(db, U1)] == [TOK_A]
    N.create_notification(db, U1, "water", now=utc(12))
    assert fcm.tokens == [TOK_A]


def test_registering_the_same_token_twice_keeps_one_device(db):
    opt_in(db)
    P.register_device(db, U1, TOK_A)
    P.register_device(db, U1, TOK_A)
    assert len(P.list_devices(db, U1)) == 1


def test_a_shared_phone_belongs_to_the_last_person_who_registered_it(db, fcm):
    opt_in(db)
    opt_in(db, U2)                                       # same token, second account
    assert P.list_devices(db, U1) == [] and [d["token"] for d in P.list_devices(db, U2)] == [TOK_A]
    N.create_notification(db, U1, "water", now=utc(12))
    assert fcm.calls == []                                # the first account's reminders no longer reach this phone


@pytest.mark.parametrize("bad", ["", " ", "x", "a" * 19, "a" * 4097, "has space " + "a" * 30, "snow-" + "a" * 30 + "☃", "../" + "a" * 30,
                                 None, 123, ["tok"], {"t": 1}, True])
def test_garbage_tokens_are_refused_and_nothing_is_stored(db, client, bad):
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}}))
    consent_ledger.set_purpose(db, U1, "push_notifications", True)
    assert client.post("/notifications/devices", json={"token": bad}, headers=H1).status_code == 422
    assert P.list_devices(db, U1) == []
    assert client.post("/notifications/devices/remove", json={"token": bad}, headers=H1).json()["removed"] is False


@pytest.mark.parametrize("platform", ["ios", "web", "ANDROID", "", None, 5, ["android"]])
def test_other_platforms_are_refused(db, client, platform):
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}}))
    consent_ledger.set_purpose(db, U1, "push_notifications", True)
    assert client.post("/notifications/devices", json={"token": TOK_A, "platform": platform}, headers=H1).status_code == 422
    assert P.list_devices(db, U1) == []


def test_non_object_bodies_are_refused(client):
    json_header = {**H1, "Content-Type": "application/json"}
    assert client.post("/notifications/devices", content="[1]", headers=json_header).status_code == 422
    assert client.post("/notifications/devices", content="not json", headers=json_header).status_code == 422


def test_no_yes_on_record_means_no_token_is_stored(db, client):
    assert client.post("/notifications/devices", json={"token": TOK_A}, headers=H1).status_code == 422          # switch off
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": True}}))                                   # switch on, no yes logged
    consent._cache.clear()
    assert consent_ledger.is_granted(db, U1, "push_notifications") is False
    assert client.post("/notifications/devices", json={"token": TOK_A}, headers=H1).status_code == 422
    assert P.list_devices(db, U1) == []


def test_at_most_five_phones_per_person(db):
    for i in range(8):
        P.register_device(db, U1, f"fcm-token-{i}:" + "Z" * 40)
    assert len(P.list_devices(db, U1)) == P.MAX_DEVICES


# --- consent --------------------------------------------------------------------------------------------------------------------------

def test_withdrawing_consent_forgets_every_phone_and_stops_sending(db, fcm):
    opt_in(db)
    P.register_device(db, U1, TOK_B)
    consent.set_purpose(db, U1, "push_notifications", False, source="settings")     # Privacy choices, not the reminders card
    assert P.list_devices(db, U1) == [] and N.load_settings(db, U1)["channels"]["push"] is False
    N.create_notification(db, U1, "water", now=utc(12))
    assert fcm.calls == []


def test_consent_withdrawn_between_creating_and_sending(db, fcm):
    opt_in(db)
    n = N.create_notification(db, U1, "water", now=utc(12))
    fcm.calls.clear()
    consent.set_purpose(db, U1, "push_notifications", False, source="settings")    # lands after the in-app copy, before the send
    P.deliver(db, U1, n, {"channels": {"push": True}})                              # a caller holding stale settings
    assert fcm.calls == []


def test_withdrawn_while_a_run_is_going_the_next_person_is_not_sent_to(db, fcm, monkeypatch):
    for uid, tok in ((U1, TOK_A), (U2, TOK_B)):
        opt_in(db, uid, tok, types={"water": False, "winddown": False})
        med_schedule(db, uid)
    real = N.generate_due
    order = []

    def spy(db_, uid, now=None, **kw):
        if not order:
            order.append(uid)
            consent.set_purpose(db_, U2 if uid == U1 else U1, "push_notifications", False, source="settings")
        return real(db_, uid, utc(12, 10), **kw)

    monkeypatch.setattr(N, "generate_due", spy)
    out = P.sweep(db, utc(12, 10))
    assert out["errors"] == 0 and len(fcm.calls) == 1
    assert fcm.tokens == [TOK_A if order[0] == U1 else TOK_B]


def test_a_revoked_token_is_never_sent_to(db, fcm):
    opt_in(db)
    P.register_device(db, U1, TOK_B)
    P.remove_device(db, U1, TOK_A)
    N.create_notification(db, U1, "water", now=utc(12))
    assert fcm.tokens == [TOK_B]


def test_the_sweep_forgets_phones_of_people_who_no_longer_say_yes(db, fcm):
    opt_in(db)
    # a stale row: the yes was withdrawn but the phone was never removed (for example a failed write)
    doc_store.put(db, U1, P.DEVICE_KIND, P.device_key(TOK_B), {"token": TOK_B, "platform": "android", "added_at": "x", "seen_at": "x"})
    db.table(doc_store.TABLE).delete().eq("user_id", U1).eq("title", "notification_settings:me").execute()   # settings gone: switch is off again
    out = P.sweep(db, utc(12))
    assert out["revoked"] == 1 and P.list_devices(db, U1) == [] and fcm.calls == []


# --- FCM misbehaving ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("make", [lambda: Recorder(status=500, body={"error": {"message": "boom"}}), lambda: Recorder(status=429),
                                  lambda: Recorder(status=403), lambda: Recorder(exc=TimeoutError("slow")),
                                  lambda: Recorder(exc=ConnectionError("down")), lambda: Recorder(exc=ValueError("bad json"))])
def test_fcm_failure_never_breaks_the_reminder_and_keeps_the_token(db, fcm, monkeypatch, make):
    opt_in(db)
    rec = make()
    monkeypatch.setattr(P, "_http_post", rec)
    n = N.create_notification(db, U1, "water", now=utc(12))
    assert n and n["kind"] == "water"                      # the in-app copy exists
    assert [d["token"] for d in P.list_devices(db, U1)] == [TOK_A]
    assert len(rec.calls) == 1                             # one try, no retry storm


def test_fcm_cannot_get_an_access_token(db, fcm, monkeypatch):
    opt_in(db)
    monkeypatch.setattr(P, "_access_token", lambda: (_ for _ in ()).throw(RuntimeError("oauth down")))
    assert N.create_notification(db, U1, "water", now=utc(12))
    assert len(P.list_devices(db, U1)) == 1


def test_a_token_fcm_says_is_gone_is_deleted_and_the_others_still_get_it(db, fcm, monkeypatch):
    opt_in(db)
    P.register_device(db, U1, TOK_B)
    gone = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}

    def post(url, payload, headers):
        fcm.calls.append(payload)
        return (404, gone) if payload["message"]["token"] == TOK_A else (200, {})

    monkeypatch.setattr(P, "_http_post", post)
    N.create_notification(db, U1, "water", now=utc(12))
    assert [d["token"] for d in P.list_devices(db, U1)] == [TOK_B] and sorted(fcm.tokens) == sorted([TOK_A, TOK_B])
    N.create_notification(db, U1, "winddown", now=utc(13))
    assert fcm.tokens.count(TOK_A) == 1                    # never tried again


def test_unconfigured_server_sends_nothing_and_does_not_fail(db, monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    opt_in(db)
    assert N.create_notification(db, U1, "water", now=utc(12))


# --- what a notification may say -------------------------------------------------------------------------------------------------------

HEALTH_WORDS = ("metformin", "500", " mg", "insulin", "dose", "diabetes", "pain", "period", "pregnan", "medicine", "blood", "anxiety")


@pytest.mark.parametrize("kind", ["water", "med", "winddown", "system"])
def test_the_payload_never_carries_health_content(db, fcm, kind):
    opt_in(db)
    med_schedule(db)
    N.create_notification(db, U1, kind, title="Take Metformin 500 mg", body="Your diabetes dose, pain and period are due", now=utc(12))
    text = json.dumps({k: v for k, v in fcm.calls[0]["message"].items() if k != "token"}).lower()
    assert not [w for w in HEALTH_WORDS if w in text], text
    assert fcm.calls[0]["message"]["data"] == {"kind": kind}


def test_generated_medicine_reminders_name_no_medicine(db, fcm, monkeypatch):
    opt_in(db, types={"water": False, "winddown": False})
    med_schedule(db)
    assert P.sweep(db, utc(12, 10))["created"] == 1
    text = json.dumps(fcm.calls[0]["message"]).lower()
    assert not [w for w in HEALTH_WORDS if w in text], text


# --- quiet hours, the daily cap and the windows ---------------------------------------------------------------------------------------

def test_nothing_is_sent_in_quiet_hours(db, fcm):
    opt_in(db)
    N.save_settings(db, U1, N.normalize_settings({"quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00"}}, N.load_settings(db, U1)))
    assert N.create_notification(db, U1, "water", now=utc(23)) is None
    assert N.create_notification(db, U1, "water", now=utc(3), dedupe_key="n") is None
    assert fcm.calls == []
    assert N.create_notification(db, U1, "water", now=utc(9), dedupe_key="d")
    assert len(fcm.calls) == 1


def test_the_daily_cap_applies_to_the_phone_too(db, fcm):
    opt_in(db, daily_cap=2)
    for i in range(5):
        N.create_notification(db, U1, "system", now=utc(10 + i), dedupe_key=f"k{i}")
    assert len(fcm.calls) == 2
    N.create_notification(db, U1, "system", now=utc(10, day=9), dedupe_key="next-day")
    assert len(fcm.calls) == 3


def test_a_person_who_only_wants_the_phone_is_not_dropped(db, fcm):
    N.save_settings(db, U1, N.normalize_settings({"channels": {"in_app": False, "email": False, "push": True}, "quiet_hours": NO_QUIET}))
    consent_ledger.set_purpose(db, U1, "push_notifications", True)
    P.register_device(db, U1, TOK_A)
    assert N.create_notification(db, U1, "water", now=utc(12))
    assert fcm.tokens == [TOK_A]


def test_a_late_scheduler_still_catches_a_water_slot_but_the_apps_own_view_is_unchanged():
    slots = [s for s in H.reminder_plan(2000, 0, 12 * 60)["slots"] if s["needed"]]
    slot = slots[0]
    late = slot["minutes"] + 80                                   # 80 minutes after the slot, before the next one (every 120)
    assert H.reminder_plan(2000, 0, late)["due_now"] is None                                              # the app: one hour
    assert H.reminder_plan(2000, 0, late, due_window_min=N.WATER_WINDOW_MIN)["due_now"] == slot["time"]   # the scheduler: 90


def test_winddown_is_still_due_forty_minutes_late(db):
    N.save_settings(db, U1, N.normalize_settings({"quiet_hours": NO_QUIET, "types": {"water": False, "med": False}}))
    import sleep_engine as S
    import wellness_common as W
    goal = S.resolve_goal(W.load_profile(db, U1)["age"], S.load_goal(db, U1))
    wd = N.parse_hhmm(S.winddown(goal["hours"], bedtime=goal.get("bedtime"), wake=goal.get("wake_time"), recent_bedtimes=[])["winddown"])
    on_time = utc(wd // 60, wd % 60)
    assert [n["kind"] for n in N.generate_due(db, U1, on_time)] == ["winddown"]
    N.save_settings(db, U2, N.normalize_settings({"quiet_hours": NO_QUIET, "types": {"water": False, "med": False}}))
    late = wd + 40
    assert [n["kind"] for n in N.generate_due(db, U2, utc(late // 60 % 24, late % 60))] == ["winddown"]
    N.save_settings(db, "00000000-0000-0000-0000-000000000003", N.normalize_settings({"quiet_hours": NO_QUIET, "types": {"water": False, "med": False}}))
    too_late = wd + 50
    assert N.generate_due(db, "00000000-0000-0000-0000-000000000003", utc(too_late // 60 % 24, too_late % 60)) == []


# --- the cron endpoint ---------------------------------------------------------------------------------------------------------------

def run(client, secret=SECRET, method="post"):
    headers = {} if secret is None else {"X-Cron-Secret": secret}
    return getattr(client, method)("/internal/push/run", headers=headers)


def test_an_unset_secret_is_the_same_404_as_an_unknown_path(client, monkeypatch):
    for name in ("BUBBLES_CRON_SECRET", "NOTIFY_CRON_SECRET"):
        monkeypatch.delenv(name, raising=False)
    ref = client.post("/internal/push/nothing-here", headers={"X-Cron-Secret": SECRET})
    assert (ref.status_code, ref.json()) == (404, {"detail": "Not Found"})
    for given in (SECRET, "", " ", "None", "null", None):
        r = run(client, given)
        assert (r.status_code, r.json()) == (404, {"detail": "Not Found"})


@pytest.mark.parametrize("given", [None, "", "wrong", SECRET[:-1], SECRET + "x", SECRET.upper(), " " + SECRET, "A" * 5000, "s3cret-value-for-test"])
def test_a_missing_or_wrong_secret_is_404_and_does_nothing(client, monkeypatch, db, fcm, given):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    opt_in(db)
    med_schedule(db)
    at_noon(monkeypatch)
    r = run(client, given)
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    assert fcm.calls == []


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_only_post_works_and_other_methods_do_not_reveal_the_route(client, monkeypatch, method):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    r = run(client, SECRET, method)
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


def test_the_secret_is_compared_in_constant_time(client, monkeypatch):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    seen = []
    real = push_api.hmac.compare_digest
    monkeypatch.setattr(push_api.hmac, "compare_digest", lambda a, b: (seen.append((a, b)), real(a, b))[1])
    assert run(client, "nope").status_code == 404 and run(client, SECRET).status_code == 200
    assert seen == [(b"nope", SECRET.encode()), (SECRET.encode(), SECRET.encode())]


def test_the_older_secret_name_is_accepted_too(client, monkeypatch):
    monkeypatch.delenv("BUBBLES_CRON_SECRET", raising=False)
    monkeypatch.setenv("NOTIFY_CRON_SECRET", SECRET)
    assert run(client).status_code == 200


def test_the_run_sends_due_reminders_and_returns_only_counts(client, monkeypatch, db, fcm):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    opt_in(db, types={"water": False, "winddown": False})
    med_schedule(db)
    at_noon(monkeypatch)
    body = run(client).json()
    assert body == {"status": "success", "checked": 1, "created": 1, "revoked": 0, "errors": 0, "partial": False, "rollups": body["rollups"]}
    assert fcm.tokens == [TOK_A]
    assert U1 not in json.dumps(body) and TOK_A not in json.dumps(body)


def test_calling_the_cron_twice_never_sends_twice(client, monkeypatch, db, fcm):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    opt_in(db, types={"water": False, "winddown": False})
    med_schedule(db)
    at_noon(monkeypatch)
    assert run(client).json()["created"] == 1
    assert run(client).json()["created"] == 0
    assert len(fcm.calls) == 1


def test_the_run_also_refreshes_the_admin_rollups(client, monkeypatch):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    import ops_rollups
    calls = []
    monkeypatch.setattr(ops_rollups, "run_rollups", lambda db_=None, **kw: calls.append(db_))
    assert run(client).json()["rollups"] == "done" and len(calls) == 1
    monkeypatch.setattr(ops_rollups, "run_rollups", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    r = run(client)
    assert r.status_code == 200 and r.json()["rollups"] == "failed"


def test_an_overlapping_run_is_skipped(client, monkeypatch):
    monkeypatch.setenv("BUBBLES_CRON_SECRET", SECRET)
    assert push_api._running.acquire(blocking=False)
    try:
        assert run(client).json() == {"status": "success", "skipped": "already_running"}
    finally:
        push_api._running.release()


def test_one_persons_broken_data_does_not_stop_everyone_else(db, fcm, monkeypatch):
    for uid, tok in ((U1, TOK_A), (U2, TOK_B)):
        opt_in(db, uid, tok, types={"water": False, "winddown": False})
        med_schedule(db, uid)
    real = N.generate_due

    def flaky(db_, uid, now=None, **kw):
        if uid == U1:
            raise RuntimeError("corrupt document")
        return real(db_, uid, utc(12, 10), **kw)

    monkeypatch.setattr(N, "generate_due", flaky)
    out = P.sweep(db, utc(12, 10))
    assert out["errors"] == 1 and out["created"] == 1 and fcm.tokens == [TOK_B]


def test_a_big_run_is_bounded(db, fcm):
    for i in range(6):
        opt_in(db, f"00000000-0000-0000-0000-0000000001{i:02d}", f"fcm-token-{i}:" + "Q" * 40)
    out = P.sweep(db, utc(12), batch=2)
    assert out["partial"] is True and out["checked"] == 2
    out = P.sweep(db, utc(12), budget_s=-1)                       # time budget already spent
    assert out["partial"] is True and out["checked"] == 0


# --- overlapping runs ---------------------------------------------------------------------------------------------------------------

def test_the_same_slot_is_one_notification(db, fcm):
    opt_in(db)
    a = N.create_notification(db, U1, "water", dedupe_key="water:2026-10-08:12:00", now=utc(12))
    b = N.create_notification(db, U1, "water", dedupe_key="water:2026-10-08:12:00", now=utc(12, 1))
    assert a and b is None and len(fcm.calls) == 1


def test_two_runs_that_both_pass_the_read_check_send_once(db, fcm):
    """Both runs read 'no such notification' and both write: the later row is removed and that run does not send."""
    opt_in(db)
    first = N.create_notification(db, U1, "water", dedupe_key="water:2026-10-08:12:00", now=utc(12))
    title = f"notification:{first['id']}"
    later = db.table(doc_store.TABLE).insert({"user_id": U1, "event_type": doc_store.EVENT_TYPE, "title": title, "data": {}}).execute().data[0]
    assert N._claim(db, U1, first["id"], later["id"]) is False
    rows = db.table(doc_store.TABLE).select("id").eq("user_id", U1).eq("title", title).execute().data
    assert len(rows) == 1 and rows[0]["id"] != later["id"]


# --- delete my data ---------------------------------------------------------------------------------------------------------------------

def test_delete_my_data_wipes_the_tokens_and_only_mine(db, client, fcm):
    opt_in(db)
    opt_in(db, U2, TOK_B)
    r = client.delete("/me/whole-health/data", params={"confirm": "true"}, headers=H1)
    assert r.status_code == 200, r.text
    assert P.list_devices(db, U1) == [] and [d["token"] for d in P.list_devices(db, U2)] == [TOK_B]
    assert P.users_with_devices(db) == [U2]


def test_a_run_that_loses_the_race_does_not_send(db, fcm, monkeypatch):
    """Another run writes the same slot between this run's read check and its write: this run backs off and sends nothing."""
    opt_in(db)
    key = "water:2026-10-08:12:00"
    nid = N.hashlib.sha256(f"{U1}|{key}".encode()).hexdigest()[:16]
    real_put = doc_store.put

    def put_after_rival(db_, uid, kind, k, payload, **kw):
        if kind == "notification":
            db_.table(doc_store.TABLE).insert({"user_id": uid, "event_type": doc_store.EVENT_TYPE, "title": f"notification:{nid}", "data": {}}).execute()
            # the rival's row exists, so this write lands as a second row (what two simultaneous inserts do)
            db_.table(doc_store.TABLE).insert({"user_id": uid, "event_type": doc_store.EVENT_TYPE, "title": f"notification:{nid}", "data": {"mine": 1}}).execute()
            return {"id": db_.table(doc_store.TABLE).select("id").eq("user_id", uid).eq("title", f"notification:{nid}").execute().data[-1]["id"]}
        return real_put(db_, uid, kind, k, payload, **kw)

    monkeypatch.setattr(doc_store, "put", put_after_rival)
    assert N.create_notification(db, U1, "water", dedupe_key=key, now=utc(12)) is None
    assert fcm.calls == []
