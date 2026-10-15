"""Android push: device tokens, the push consent gate, the FCM sender (fake transport), the third channel in notifications, the scheduler
endpoint's auth and idempotence, and "delete my data". No network: every sender is a fake."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import data_rights
import med_schedule as M
import notifications as N
import push_api
import push_devices as D
import push_fcm
from tests.fake_db import FakeDB, permission_denied

U1, U2 = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
TOK1, TOK2, TOK3 = ("a" * 20 + f"-token-{i}" for i in (1, 2, 3))
H1, H2 = {"Authorization": "Bearer u1"}, {"Authorization": "Bearer u2"}


def utc(h, m=0, day=8):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    return FakeDB({})


def push_on(db, uid=U1, **extra):
    N.save_settings(db, uid, N.normalize_settings({"channels": {"push": True}, **extra}, N.load_settings(db, uid)))


def med(db, uid=U1):
    s = M.normalize_schedule({"name": "Metformin", "dose_label": "500 mg", "times": ["12:00"], "start_date": "2026-09-01"}, utc(0).date())
    s["id"] = "aaaaaaaaaaaa"
    M.save_schedule(db, uid, s)


class Pusher:
    def __init__(self, invalid=()):
        self.calls, self.invalid = [], list(invalid)

    def __call__(self, tokens, title, body, kind):
        self.calls.append((list(tokens), title, body, kind))
        return {"sent": len(tokens) - len(self.invalid), "failed": len(self.invalid), "invalid": self.invalid, "reason": None}


def client(db):
    def get_user(authorization):
        uid = {"Bearer u1": U1, "Bearer u2": U2}.get(authorization or "")
        if not uid:
            raise HTTPException(status_code=401, detail="Authentication required")
        return SimpleNamespace(id=uid)

    app = FastAPI()
    app.include_router(push_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False)


# --- device tokens -----------------------------------------------------------------------------------------------------------

def test_register_stores_then_reassigns_to_the_signed_in_user(db):
    D.register(db, U1, TOK1, "android", "1.2.0")
    assert D.active_tokens(db, U1) == [TOK1]
    D.register(db, U2, TOK1, "android", "1.2.0")   # a second person signs in on the same phone
    assert D.active_tokens(db, U1) == [] and D.active_tokens(db, U2) == [TOK1]
    assert len(db.rows("device_tokens")) == 1


@pytest.mark.parametrize("bad", ["", "short", "x" * 600, "has space in it 1234567890", None, 42, "a" * 20 + "<script>"])
def test_bad_tokens_are_refused(db, bad):
    with pytest.raises(D.PushInputError):
        D.register(db, U1, bad)
    assert db.rows("device_tokens") == []


def test_only_android_and_a_bad_version_is_dropped_not_refused(db):
    with pytest.raises(D.PushInputError):
        D.register(db, U1, TOK1, "ios")
    D.register(db, U1, TOK1, "android", "1.0; drop table")
    assert db.rows("device_tokens")[0]["app_version"] is None


def test_at_most_five_active_tokens_the_oldest_are_revoked(db):
    tokens = [f"{'b' * 20}-{i}" for i in range(7)]
    for t in tokens:
        D.register(db, U1, t)
    assert sorted(D.active_tokens(db, U1)) == sorted(tokens[2:])


def test_unregister_revokes_only_the_callers_own_token(db):
    D.register(db, U1, TOK1)
    assert D.unregister(db, U2, TOK1) == 0          # another user cannot revoke it
    assert D.active_tokens(db, U1) == [TOK1]
    assert D.unregister(db, U1, TOK1) == 1
    assert D.active_tokens(db, U1) == []


def test_missing_table_is_not_ready_not_a_crash(db):
    db.failures["device_tokens"] = permission_denied("device_tokens")
    with pytest.raises(D.PushUnavailable):
        D.register(db, U1, TOK1)
    assert N.send_push(db, U1, "water", "t", "b", pusher=Pusher())["reason"] == "error"


# --- consent gate and the routes -----------------------------------------------------------------------------------------------

def test_register_is_refused_with_422_until_push_is_on(db):
    c = client(db)
    r = c.post("/notifications/push/register", json={"token": TOK1, "platform": "android"}, headers=H1)
    assert r.status_code == 422 and db.rows("device_tokens") == []
    push_on(db)
    r = c.post("/notifications/push/register", json={"token": TOK1, "platform": "android", "app_version": "1.2.0"}, headers=H1)
    assert r.status_code == 200 and r.json()["registered"] is True
    assert c.post("/notifications/push/register", json={"token": TOK1}).status_code == 401


def test_register_answers_not_ready_when_the_migration_is_missing(db):
    push_on(db)
    db.failures["device_tokens"] = permission_denied("device_tokens")
    r = client(db).post("/notifications/push/register", json={"token": TOK1}, headers=H1)
    assert r.status_code == 200 and r.json() == {"status": "success", "registered": False, "reason": "not_ready"}


def test_delete_route_revokes_only_own_token(db):
    push_on(db)
    push_on(db, U2)
    c = client(db)
    c.post("/notifications/push/register", json={"token": TOK1}, headers=H1)
    assert c.request("DELETE", "/notifications/push/register", json={"token": TOK1}, headers=H2).json()["revoked"] == 0
    assert c.request("DELETE", "/notifications/push/register", json={"token": TOK1}, headers=H1).json()["revoked"] == 1
    assert c.request("DELETE", "/notifications/push/register", json={}, headers=H1).status_code == 422


def test_turning_push_off_revokes_every_device(db):
    push_on(db)
    D.register(db, U1, TOK1)
    D.register(db, U1, TOK2)
    N.save_settings(db, U1, N.normalize_settings({"channels": {"push": False}}, N.load_settings(db, U1)))
    assert D.active_tokens(db, U1) == []


def test_delete_my_data_wipes_device_tokens(db):
    D.register(db, U1, TOK1)
    D.register(db, U2, TOK2)
    app = FastAPI()
    app.include_router(data_rights.build_router(lambda a: SimpleNamespace(id=a.removeprefix("Bearer ")), db))
    r = TestClient(app).delete("/me/whole-health/data?confirm=true", headers={"Authorization": "Bearer " + U1})
    assert r.status_code == 200
    assert [x["token"] for x in db.rows("device_tokens")] == [TOK2]


# --- the sender ------------------------------------------------------------------------------------------------------------------

class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def test_fcm_sends_only_generic_text_with_a_fixed_route(db):
    posted = []

    def post(url, json=None, headers=None, timeout=None):
        posted.append((url, json, headers))
        return Resp(200, {"name": "x"})

    out = push_fcm.send([TOK1], "A little water break?", "Time for a sip of water.", "water", post=post, token_provider=lambda: "bearer")
    assert out["sent"] == 1 and out["invalid"] == []
    msg = posted[0][1]["message"]
    assert msg["data"] == {"route": "/hydration", "kind": "water"} and msg["android"]["notification"]["channel_id"] == "reminders"
    assert posted[0][2] == {"Authorization": "Bearer bearer"}


@pytest.mark.parametrize("title,body", [("Take 500 mg of Metformin", "ok"), ("Hi", "Your blood pressure is high"), ("Hi", "You drank 750 ml")])
def test_fcm_refuses_health_text_and_never_posts(title, body):
    def post(*a, **k):
        raise AssertionError("must not post")

    assert push_fcm.send([TOK1], title, body, "system", post=post, token_provider=lambda: "x")["reason"] == "not_generic"


def test_fcm_reports_dead_tokens_but_not_a_wrong_project_or_outage():
    def post(url, json=None, headers=None, timeout=None):
        t = json["message"]["token"]
        if t == TOK1:
            return Resp(404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}})
        if t == TOK2:
            return Resp(404, {"error": {"status": "NOT_FOUND", "message": "Requested entity was not found."}})   # wrong project id
        return Resp(503)

    out = push_fcm.send([TOK1, TOK2, TOK3], "Bubbles", "You have an update in Bubbles.", "system", post=post, token_provider=lambda: "x")
    assert out["invalid"] == [TOK1] and out["failed"] == 3 and out["sent"] == 0


def test_fcm_not_configured_sends_nothing(monkeypatch):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_B64", raising=False)
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON", raising=False)
    push_fcm._account.cache_clear()
    assert push_fcm.configured() is False
    assert push_fcm.send([TOK1], "Bubbles", "You have an update in Bubbles.", "system")["reason"] == "not_configured"


def test_fcm_account_is_read_from_base64_or_json_and_validated(monkeypatch):
    info = {"project_id": "p", "client_email": "a@p.iam.gserviceaccount.com", "private_key": "k"}
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_B64", base64.b64encode(json.dumps(info).encode()).decode())
    push_fcm._account.cache_clear()
    assert push_fcm.configured()
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_B64")
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_JSON", json.dumps({"project_id": "p"}))   # missing key fields
    push_fcm._account.cache_clear()
    assert not push_fcm.configured()
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT_B64", "%%%not base64%%%")
    push_fcm._account.cache_clear()
    assert not push_fcm.configured()
    push_fcm._account.cache_clear()


# --- push as a third channel in notifications ---------------------------------------------------------------------------------------

def test_push_only_user_is_not_dropped(db):
    push_on(db, channels={"push": True, "in_app": False, "email": False})
    D.register(db, U1, TOK1)
    p = Pusher()
    n = N.create_notification(db, U1, "water", now=utc(12), pusher=p, dedupe_key="water:2026-10-08:12:00")
    assert n is not None and len(p.calls) == 1
    assert p.calls[0][0] == [TOK1] and (p.calls[0][1], p.calls[0][2]) == N.TEMPLATES["water"] and p.calls[0][3] == "water"


def test_nothing_is_pushed_when_push_is_off_or_no_device(db):
    D.register(db, U1, TOK1)
    p = Pusher()
    assert N.create_notification(db, U1, "water", now=utc(12), pusher=p)       # push off by default
    assert p.calls == []
    push_on(db)
    assert N.create_notification(db, U2, "water", now=utc(12), pusher=p)       # U2 has no device
    push_on(db, U2)
    assert N.create_notification(db, U2, "water", now=utc(12, 5), pusher=p)
    assert p.calls == []


def test_quiet_hours_and_cap_apply_to_push_too(db):
    push_on(db, daily_cap=2)
    D.register(db, U1, TOK1)
    p = Pusher()
    assert N.create_notification(db, U1, "water", now=utc(23, 30), pusher=p) is None     # inside quiet hours (23:00 to 07:00)
    assert N.create_notification(db, U1, "water", now=utc(10), pusher=p)
    assert N.create_notification(db, U1, "water", now=utc(11), pusher=p)
    assert N.create_notification(db, U1, "water", now=utc(12), pusher=p) is None         # cap of 2 reached
    assert len(p.calls) == 2


def test_custom_unsafe_text_is_replaced_before_it_can_be_pushed(db):
    push_on(db)
    D.register(db, U1, TOK1)
    p = Pusher()
    N.create_notification(db, U1, "med", title="Take Metformin 500 mg", body="Your sugar is high", now=utc(12), pusher=p)
    assert (p.calls[0][1], p.calls[0][2]) == N.TEMPLATES["med"]


def test_invalid_tokens_reported_by_the_sender_are_revoked(db):
    push_on(db)
    D.register(db, U1, TOK1)
    D.register(db, U1, TOK2)
    N.create_notification(db, U1, "water", now=utc(12), pusher=Pusher(invalid=[TOK1]))
    assert D.active_tokens(db, U1) == [TOK2]


def test_a_failing_sender_never_breaks_the_notification(db):
    push_on(db)
    D.register(db, U1, TOK1)

    def boom(*a):
        raise RuntimeError("fcm down")

    assert N.create_notification(db, U1, "water", now=utc(12), pusher=boom) is not None


def test_overlapping_runs_send_once(db):
    push_on(db)
    D.register(db, U1, TOK1)
    p = Pusher()
    key = "water:2026-10-08:12:00"
    first = N.create_notification(db, U1, "water", now=utc(12), pusher=p, dedupe_key=key)
    second = N.create_notification(db, U1, "water", now=utc(12, 1), pusher=p, dedupe_key=key)   # the next run sees the same slot
    assert first and second is None and len(p.calls) == 1
    assert len([r for r in db.rows("health_events") if r["title"].startswith("notification:")]) == 1


def test_a_racing_duplicate_row_is_removed_so_only_one_run_sends(db):
    push_on(db)
    N.create_notification(db, U1, "water", now=utc(12), dedupe_key="k")
    rows = [r for r in db.rows("health_events") if r["title"].startswith("notification:")]
    nid = rows[0]["title"].split(":", 1)[1]
    twin = {**rows[0], "id": "zzzz-later", "created_at": "2099-01-01T00:00:00+00:00"}
    db.tables["health_events"].append(twin)
    assert N._claim(db, U1, nid, "zzzz-later") is False                 # the later twin loses and is deleted
    assert [r["id"] for r in db.rows("health_events") if r["title"].startswith("notification:")] == [rows[0]["id"]]
    assert N._claim(db, U1, nid, rows[0]["id"]) is True


def test_the_wider_windows_catch_a_late_scheduler(db):
    push_on(db)
    D.register(db, U1, TOK1)
    med(db)
    p = Pusher()
    made = N.generate_due(db, U1, utc(12, 40), pusher=p)    # the cron was 40 minutes late for a 12:00 medicine (window is an hour)
    assert [n["kind"] for n in made] == ["med"] and len(p.calls) == 1
    assert N.generate_due(db, U1, utc(12, 50), pusher=p) == [] and len(p.calls) == 1   # same slot: no second push


# --- the scheduler endpoint ----------------------------------------------------------------------------------------------------------

def test_cron_endpoint_is_a_plain_404_without_the_secret(db, monkeypatch):
    c = client(db)
    unknown = c.post("/internal/nothing/here")
    for env in (None, "s3cret"):
        if env:
            monkeypatch.setenv("BUBBLES_CRON_SECRET", env)
        else:
            monkeypatch.delenv("BUBBLES_CRON_SECRET", raising=False)
            monkeypatch.delenv("NOTIFY_CRON_SECRET", raising=False)
        for headers in ({}, {"X-Cron-Secret": "wrong"}, {"X-Cron-Secret": ""}):
            r = c.post("/internal/push/run", headers=headers)
            assert (r.status_code, r.content) == (unknown.status_code, unknown.content)
    r = c.get("/internal/push/run", headers={"X-Cron-Secret": "s3cret"})     # right secret, wrong method: still the same 404
    assert (r.status_code, r.content) == (unknown.status_code, unknown.content)
    assert c.post("/internal/push/run", headers={"X-Cron-Secret": "s3cret"}).status_code == 200


def test_cron_unset_secret_never_matches_an_empty_header(db, monkeypatch):
    monkeypatch.delenv("BUBBLES_CRON_SECRET", raising=False)
    monkeypatch.delenv("NOTIFY_CRON_SECRET", raising=False)
    assert client(db).post("/internal/push/run", headers={"X-Cron-Secret": ""}).status_code == 404


def test_scheduler_fans_out_to_users_with_push_on_and_is_idempotent(db):
    push_on(db, U1, types={"water": False, "winddown": False})
    D.register(db, U1, TOK1)
    med(db, U1)
    D.register(db, U2, TOK2)                       # U2 has a token but push is off: it must be revoked, never pushed
    med(db, U2)
    p = Pusher()
    out = push_api.run_scheduler(db, now=utc(12, 5), pusher=p)
    assert out["users"] == 2 and out["created"] == 1 and out["sent"] == 1 and out["revoked_users"] == 1
    assert D.active_tokens(db, U2) == [] and [c[0] for c in p.calls] == [[TOK1]]
    again = push_api.run_scheduler(db, now=utc(12, 15), pusher=p)
    assert again["created"] == 0 and len(p.calls) == 1
    assert set(out) >= {"users", "created", "sent", "failed", "errors", "partial"} and not any(isinstance(v, str) and U1 in v for v in out.values())


def test_scheduler_is_bounded(db):
    for i in range(5):
        uid = f"00000000-0000-0000-0000-00000000010{i}"
        push_on(db, uid)
        D.register(db, uid, f"{'c' * 20}-{i}")
    out = push_api.run_scheduler(db, now=utc(12), pusher=Pusher(), batch=2)
    assert out["users"] == 2 and out["partial"] is True


def test_scheduler_survives_a_missing_device_table(db):
    db.failures["device_tokens"] = permission_denied("device_tokens")
    assert push_api.run_scheduler(db, now=utc(12), pusher=Pusher())["device_table"] == "not_ready"


def test_channel_status_reports_push_available_only_when_configured(monkeypatch):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_B64", raising=False)
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON", raising=False)
    push_fcm._account.cache_clear()
    assert N.channel_status()["push"]["available"] is False


# --- through the real app (middleware, registration) ---------------------------------------------------------------------------------

from test_chat_http_flow import env  # noqa: E402,F401  (stateful app with a fake database)


def test_real_app_cron_route_is_indistinguishable_from_an_unknown_path(env, monkeypatch):
    monkeypatch.delenv("NOTIFY_CRON_SECRET", raising=False)
    monkeypatch.setenv("BUBBLES_CRON_SECRET", "real-secret")
    unknown = env.client.post("/internal/does-not-exist")
    for headers in ({}, {"X-Cron-Secret": "nope"}):
        r = env.client.post("/internal/push/run", headers=headers)
        assert (r.status_code, r.content) == (unknown.status_code, unknown.content) == (404, b'{"detail":"Not Found"}')
    ok = env.client.post("/internal/push/run", headers={"X-Cron-Secret": "real-secret"})
    assert ok.status_code == 200 and ok.json()["status"] == "success"


def test_real_app_register_is_gated_by_the_push_switch(env):
    h = {"Authorization": "Bearer tok"}
    assert env.client.post("/notifications/push/register", json={"token": TOK1}, headers=h).status_code == 422
    assert env.client.put("/notifications/settings", json={"channels": {"push": True}}, headers=h).status_code == 200
    assert env.client.post("/notifications/push/register", json={"token": TOK1}, headers=h).json()["registered"] is True
    assert env.client.put("/notifications/settings", json={"channels": {"push": False}}, headers=h).status_code == 200
    assert [r["revoked"] for r in env.db.rows("device_tokens")] == [True]
