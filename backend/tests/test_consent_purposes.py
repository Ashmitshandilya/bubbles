"""Granular consent: separate purposes, a ledger, enforcement points, the chat-card decline, delete-my-data keeping a minimised trail.

Every behaviour is checked twice: with the consent_events table, and without it (migration not applied: the same events are kept
as signed documents)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import consent
import doc_store
from fake_db import FakeAPIError, grant_consent, permission_denied

from test_chat_http_flow import H, OTHER, USER, env, send  # noqa: F401  (the same stateful app and stub model)

H2 = {"Authorization": "Bearer tok2"}
ALL = list(consent.PURPOSES)
DAILY_LOG = "Slept 6h 42m. Drank about 1.8 L of water. Walked 6,420 steps. Cramps 4/10."


@pytest.fixture(params=["with_table", "without_table", "table_not_granted"])
def cenv(request, env):  # noqa: F811
    """The chat app with a person who has never answered. The ledger table is there, missing, or refused to the backend."""
    env.db.tables["consent_events"] = []
    env.db.tables["health_events"] = [r for r in env.db.tables.get("health_events", []) if r.get("title", "").split(":")[0] != "consent_event"]
    if request.param == "without_table":
        env.db.failures[consent.TABLE] = FakeAPIError('relation "public.consent_events" does not exist', "42P01")
    elif request.param == "table_not_granted":
        env.db.failures[consent.TABLE] = permission_denied(consent.TABLE)
    env.variant = request.param
    for person in (USER, OTHER):
        consent.forget(person)
    consent._table_state.clear()
    return env


def put(env, purpose, granted, *, source="settings", seen="auto", h=H):
    body = {"granted": granted, "source": source}
    if seen == "auto" and granted:
        seen = consent.text_hash(purpose) if purpose in consent.PURPOSES else None
    if seen not in ("auto", None):
        body["text_hash"] = seen
    return env.client.put(f"/consents/{purpose}", json=body, headers=h)


def ledger(env, uid=USER):
    return [e for e in consent.events(env.db, uid) if e["purpose"] in consent.PURPOSES]


# ---- the screen ------------------------------------------------------------------------------------------------------------

def test_a_fresh_account_has_every_purpose_off(cenv):
    res = cenv.client.get("/consents", headers=H)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [p["id"] for p in body["purposes"]] == ALL
    assert all(p["granted"] is False and p["decision"] == "none" and p["decided_at"] is None for p in body["purposes"])
    assert body["policy_version"] == consent.POLICY_VERSION and body["disclosures"][0]["id"] == "service_storage"
    unavailable = [p["id"] for p in body["purposes"] if not p["available"]]
    assert unavailable == ["product_usage_metrics"]
    for p in body["purposes"]:
        assert p["title"] and p["description"] and p["text_version"] and p["text_hash"] == consent.text_hash(p["id"])


def test_a_yes_and_a_withdrawal_each_append_one_ledger_row_and_show_in_the_history(cenv):
    assert put(cenv, "email_reminders", True).json()["consent"]["granted"] is True
    assert len(ledger(cenv)) == 1
    assert put(cenv, "email_reminders", False).json()["consent"]["granted"] is False
    rows = ledger(cenv)
    assert [r["granted"] for r in rows] == [False, True] and all(r["source"] == "settings" for r in rows)
    assert all(r["policy_version"] == consent.POLICY_VERSION and r["text_hash"] == consent.text_hash("email_reminders") for r in rows)
    history = cenv.client.get("/consents/history", headers=H).json()["events"]
    assert [(h["purpose"], h["granted"]) for h in history] == [("email_reminders", False), ("email_reminders", True)]
    assert cenv.client.get("/consents/history", headers=H2).json()["events"] == []   # another person's history is not shown


def test_switching_to_the_value_it_already_has_adds_nothing(cenv):
    put(cenv, "partner_sharing", True)
    put(cenv, "partner_sharing", True)
    assert len(ledger(cenv)) == 1


def test_the_ledger_holds_no_free_text_and_no_other_person(cenv):
    put(cenv, "community_visibility", True, source="chat_card")
    row = ledger(cenv)[0]
    assert set(row) <= {"id", "purpose", "granted", "policy_version", "text_version", "text_hash", "source", "created_at"}
    if cenv.variant == "with_table":
        stored = cenv.db.rows("consent_events")
        assert len(stored) == 1 and stored[0]["user_id"] == USER and len(stored[0]["user_hash"]) == 32 and USER not in stored[0]["user_hash"]
    else:
        assert cenv.db.rows("consent_events") == []   # nothing was written to a table that is not there


def test_a_yes_must_quote_the_current_wording(cenv):
    assert put(cenv, "partner_sharing", True, seen=None).status_code == 422
    assert put(cenv, "partner_sharing", True, seen="0123456789abcdef").status_code == 409
    assert consent.is_granted(cenv.db, USER, "partner_sharing") is False
    assert ledger(cenv) == []
    assert put(cenv, "partner_sharing", False, seen=None).status_code == 200      # a withdrawal never needs the hash


def test_bad_requests(cenv):
    assert put(cenv, "weather", True).status_code == 404
    assert cenv.client.put("/consents/partner_sharing", json={"granted": "yes"}, headers=H).status_code == 422
    assert cenv.client.put("/consents/partner_sharing", json=[], headers=H).status_code == 422
    assert put(cenv, "partner_sharing", True, source="shouting").status_code == 422
    assert cenv.client.get("/consents").status_code == 401 and cenv.client.put("/consents/partner_sharing", json={"granted": False}).status_code == 401
    assert cenv.client.get("/consents/history").status_code == 401


def test_usage_metrics_is_listed_but_cannot_be_turned_on(cenv):
    assert put(cenv, "product_usage_metrics", True).status_code == 409
    assert consent.is_granted(cenv.db, USER, "product_usage_metrics") is False
    assert put(cenv, "product_usage_metrics", False, seen=None).status_code == 200


# ---- the helper ------------------------------------------------------------------------------------------------------------

def test_is_granted_missing_unknown_and_unreadable_are_false(cenv):
    assert consent.is_granted(cenv.db, USER, "partner_sharing") is False
    assert consent.is_granted(cenv.db, USER, "no_such_purpose") is False
    assert consent.is_granted(cenv.db, "", "partner_sharing") is False

    class Broken:
        def table(self, *_):
            raise RuntimeError("database down")
    assert consent.is_granted(Broken(), USER, "ai_chat_processing") is False


def test_a_write_is_seen_by_the_very_next_read_even_through_the_cache(cenv):
    assert consent.is_granted(cenv.db, USER, "push_notifications") is False      # remembered as no
    put(cenv, "push_notifications", True)
    assert consent.is_granted(cenv.db, USER, "push_notifications") is True
    put(cenv, "push_notifications", False)
    assert consent.is_granted(cenv.db, USER, "push_notifications") is False


def test_the_old_name_and_the_old_endpoints_still_work(cenv):
    assert cenv.client.put("/me/consent", json={"ai_chat": True}, headers=H).json()["ai_chat"] is True
    assert consent.is_granted(cenv.db, USER, "ai_chat") is True and consent.has_ai_consent(cenv.db, USER) is True
    assert consent.state(cenv.db, USER)["version"] == consent.VERSION
    assert cenv.client.get("/me/consent", headers=H).json()["ai_chat"] is True
    assert [r["purpose"] for r in ledger(cenv)] == ["ai_chat_processing"]
    assert cenv.client.put("/me/consent", json={"ai_chat": False}, headers=H).json()["ai_chat"] is False


def test_a_changed_wording_asks_again(cenv, monkeypatch):
    put(cenv, "health_memory_from_chat", True)
    assert consent.is_granted(cenv.db, USER, "health_memory_from_chat") is True
    monkeypatch.setitem(consent.PURPOSES["health_memory_from_chat"], "text_version", "2026-11a")
    consent.forget(USER)
    assert consent.is_granted(cenv.db, USER, "health_memory_from_chat") is False


# ---- enforcement points (one per point) ------------------------------------------------------------------------------------

def test_point_ai_provider_calls_need_ai_chat_processing(cenv):
    res = send(cenv, "I have been feeling really tired this week and I do not know why")
    assert res.json()["consent_required"] is True and cenv.ai_calls == []
    put(cenv, "ai_chat_processing", True)
    res = send(cenv, "I have been feeling really tired this week and I do not know why")
    assert res.json()["consent_required"] is False and len(cenv.ai_calls) == 1
    put(cenv, "ai_chat_processing", False)
    assert send(cenv, "I have also been sleeping badly and I do not know why").json()["consent_required"] is True
    assert len(cenv.ai_calls) == 1


def test_point_chat_events_need_health_memory_from_chat(cenv):
    put(cenv, "ai_chat_processing", True)
    res = send(cenv, DAILY_LOG).json()
    assert res["health_events"] == [] and cenv.db.rows("extracted_health_events") == []     # chat still works, nothing is extracted
    assert res["response"]
    put(cenv, "health_memory_from_chat", True)
    res = send(cenv, DAILY_LOG + " Again.").json()
    assert res["health_events"] and cenv.db.rows("extracted_health_events")
    put(cenv, "health_memory_from_chat", False)
    before = len(cenv.db.rows("extracted_health_events"))
    send(cenv, "Slept 5h 10m. Drank about 2 L of water. Walked 3,000 steps.")
    assert len(cenv.db.rows("extracted_health_events")) == before


def test_explicit_tracker_logs_still_save_without_the_chat_purpose(cenv):
    res = cenv.client.post("/health/sleep", json={"date": "2026-10-14", "duration": 7, "quality": 4}, headers=H)
    assert res.status_code == 201, res.text


def test_the_persist_helper_does_not_call_persist_when_off_or_empty(cenv):
    calls = []

    def persist(db, uid, message_id, events):
        calls.append(events)
        return [{"id": "1"}]
    assert consent.persist_chat_events(cenv.db, USER, "m", [{"e": 1}], persist=persist) == [] and calls == []
    put(cenv, "health_memory_from_chat", True)
    assert consent.persist_chat_events(cenv.db, USER, "m", [], persist=persist) == [] and calls == []
    assert consent.persist_chat_events(cenv.db, USER, "m", [{"e": 1}], persist=persist) == [{"id": "1"}] and calls == [[{"e": 1}]]


def test_point_partner_sharing_needs_the_purpose_and_withdrawal_stops_everything(cenv):
    settings = {"categories": ["sleep"], "owner_name": "Riya"}
    refused = cenv.client.put("/partner-sharing/settings", json=settings, headers=H)
    assert refused.status_code == 403 and "Privacy choices" in refused.json()["detail"]
    assert cenv.client.post("/partner-sharing/link", json={"expires_in_days": 7}, headers=H).status_code == 403
    assert cenv.client.post("/partner-sharing/invite", headers=H).status_code == 403
    put(cenv, "partner_sharing", True)
    assert cenv.client.put("/partner-sharing/settings", json=settings, headers=H).status_code == 200
    made = cenv.client.post("/partner-sharing/link", json={"expires_in_days": 7}, headers=H).json()
    assert cenv.client.get(made["share_path"].replace("/partner/", "/partner/"), headers={}).status_code == 200
    put(cenv, "partner_sharing", False)
    assert cenv.client.get(made["share_path"]).status_code == 404                  # the link stops at once
    status = cenv.client.get("/partner-sharing", headers=H).json()
    assert status["sharing"] is False and status["consent"] is False and status["categories"] == []


def test_point_email_reminders_need_the_purpose_and_the_channel_follows_it(cenv, monkeypatch):
    import notifications
    sent = []

    class Mail:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def send_message(self, msg):
            sent.append(msg)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    notifications.save_settings(cenv.db, USER, notifications.normalize_settings({"channels": {"email": True}, "quiet_hours": {"enabled": False}}))
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    assert notifications.create_notification(cenv.db, USER, "water", dedupe_key="a", now=now, email="a@example.com", mailer=Mail)
    assert sent == []                                                              # the switch is on, the yes is missing
    put(cenv, "email_reminders", True)
    assert notifications.load_settings(cenv.db, USER)["channels"]["email"] is True
    assert notifications.create_notification(cenv.db, USER, "water", dedupe_key="b", now=now + timedelta(hours=1), email="a@example.com", mailer=Mail)
    assert len(sent) == 1
    put(cenv, "email_reminders", False)
    assert notifications.load_settings(cenv.db, USER)["channels"]["email"] is False
    notifications.create_notification(cenv.db, USER, "water", dedupe_key="c", now=now + timedelta(hours=2), email="a@example.com", mailer=Mail)
    assert len(sent) == 1


def test_point_push_notifications_mirror_the_channel_switch(cenv):
    import notifications
    assert notifications.load_settings(cenv.db, USER)["channels"]["push"] is False
    put(cenv, "push_notifications", True)
    assert notifications.load_settings(cenv.db, USER)["channels"]["push"] is True
    put(cenv, "push_notifications", False)
    assert notifications.load_settings(cenv.db, USER)["channels"]["push"] is False


def test_point_community_posting_helper_is_false_until_granted(cenv):
    assert consent.is_granted(cenv.db, USER, "community_visibility") is False
    put(cenv, "community_visibility", True)
    assert consent.is_granted(cenv.db, USER, "community_visibility") is True and consent.is_granted(cenv.db, OTHER, "community_visibility") is False


def test_point_privacy_check_and_sharing_plan_use_the_stored_record(cenv):
    forged = {"purpose": "partner_sharing", "consent": {"partner_sharing": True}}
    assert cenv.client.post("/privacy/consent/check", json=forged, headers=H).json()["policy"]["decision"] == "deny"
    put(cenv, "partner_sharing", True)
    assert cenv.client.post("/privacy/consent/check", json={"purpose": "partner_sharing", "consent": {"partner_sharing": False}}, headers=H).json()["policy"]["decision"] == "allow"
    plan = cenv.client.post("/sharing/plan", json={"scopes": ["labs"], "consent": {"labs": False}}, headers=H).json()
    assert plan["allowed"] == ["labs"]
    put(cenv, "partner_sharing", False)
    plan = cenv.client.post("/sharing/plan", json={"scopes": ["labs"], "consent": {"labs": True}}, headers=H).json()
    assert plan["allowed"] == [] and plan["denied"] == ["labs"]


# ---- chat card: "No, not now" ----------------------------------------------------------------------------------------------

def test_a_decline_in_the_chat_card_is_recorded_and_stops_the_asking(cenv):
    first = send(cenv, "I have been feeling really tired this week and I do not know why").json()
    assert first["consent_required"] is True and first["consent_ask"] is True and "outside AI model" in first["response"]
    assert put(cenv, "ai_chat_processing", False, source="chat_card", seen=None).status_code == 200
    again = send(cenv, "I have also been sleeping badly and I do not know why").json()
    assert again["consent_required"] is True and again["consent_ask"] is False and cenv.ai_calls == []
    assert again["response"].startswith("No problem") and "Privacy choices" in again["response"] and "emergency number" in again["response"]
    assert ledger(cenv)[0]["source"] == "chat_card" and ledger(cenv)[0]["granted"] is False


def test_the_question_comes_back_after_14_days_or_a_new_wording(cenv, monkeypatch):
    put(cenv, "ai_chat_processing", False, source="chat_card", seen=None)
    now = datetime.now(timezone.utc)
    assert consent.reask_due(cenv.db, USER, now + timedelta(days=13)) is False
    assert consent.reask_due(cenv.db, USER, now + timedelta(days=14, minutes=1)) is True
    monkeypatch.setitem(consent.PURPOSES["ai_chat_processing"], "text_version", "2027-01a")
    consent.forget(USER)
    assert consent.reask_due(cenv.db, USER, now) is True


def test_an_urgent_message_keeps_the_fixed_text_after_a_decline(cenv):
    put(cenv, "ai_chat_processing", False, source="chat_card", seen=None)
    body = send(cenv, "I have had a little chest tightness since this morning").json()
    assert "prompt attention" in body["response"] and "No problem" not in body["response"]


def test_the_frozen_consent_reply_is_unchanged():
    text = consent.consent_needed_reply("Sudiksha")
    assert text.endswith("If something feels urgent, call your local emergency number.")
    assert "Nothing is sent unless you say yes" in text


# ---- sign-up acknowledgement -----------------------------------------------------------------------------------------------

def test_the_signup_acknowledgement_is_a_record_and_not_a_consent(cenv):
    res = cenv.client.post("/consents/acknowledgements", json={"version": consent.POLICY_VERSION}, headers=H)
    assert res.status_code == 200 and res.json()["acknowledged"] is True
    events = consent.events(cenv.db, USER)
    assert [(e["purpose"], e["source"], e["text_version"]) for e in events] == [(consent.ACK_PURPOSE, "signup", consent.POLICY_VERSION)]
    assert all(p["granted"] is False for p in cenv.client.get("/consents", headers=H).json()["purposes"])
    assert cenv.client.post("/consents/acknowledgements", json={"version": 3}, headers=H).status_code == 422
    assert cenv.client.get("/consents/history", headers=H).json()["events"][0]["kind"] == "acknowledgement"


# ---- delete my data --------------------------------------------------------------------------------------------------------

def test_delete_my_data_keeps_a_minimised_trail_and_resets_every_purpose(cenv):
    put(cenv, "ai_chat_processing", True)
    put(cenv, "partner_sharing", True)
    put(cenv, "partner_sharing", False)
    doc_store.put(cenv.db, USER, "plan", "p1", {"x": 1})
    removed = doc_store.delete_everything(cenv.db, USER)
    assert removed >= 1 and doc_store.get(cenv.db, USER, "plan", "p1") is None
    assert all(consent.is_granted(cenv.db, USER, p) is False for p in ALL)
    assert cenv.client.get("/me/consent", headers=H).json()["ai_chat"] is False
    if cenv.variant == "with_table":
        rows = cenv.db.rows("consent_events")
        assert rows and all(r["user_id"] is None and r["user_hash"] for r in rows)    # unlinked from the person, hash and decisions stay
        assert {(r["purpose"], r["granted"]) for r in rows} >= {("ai_chat_processing", True), ("ai_chat_processing", False), ("partner_sharing", False)}
        assert consent.events(cenv.db, USER) == []
    else:
        kept = consent.events(cenv.db, USER)
        assert {(e["purpose"], e["granted"]) for e in kept} >= {("ai_chat_processing", True), ("ai_chat_processing", False)}
        assert all(e["source"] in ("settings", "system") for e in kept)


def test_delete_my_data_keeps_the_trail_even_when_nothing_else_is_stored(cenv):
    put(cenv, "email_reminders", True)
    doc_store.delete_everything(cenv.db, USER)
    assert consent.is_granted(cenv.db, USER, "email_reminders") is False


# ---- admin: counts only ----------------------------------------------------------------------------------------------------

def test_consent_rates_are_counts_only(cenv):
    for person, h in ((USER, H), (OTHER, H2)):
        put(cenv, "partner_sharing", True, h=h)
    put(cenv, "ai_chat_processing", True, h=H)
    put(cenv, "ai_chat_processing", False, h=H2, source="chat_card", seen=None)
    rates = consent.consent_rates(cenv.db)
    if cenv.variant != "with_table":
        assert rates == {"available": False, "purposes": {}, "people_decided": 0}
        return
    assert rates["available"] is True and rates["people_decided"] == 2
    assert rates["purposes"]["partner_sharing"] == {"granted": 2, "declined": 0, "decided": 2, "rate": 1.0}
    assert rates["purposes"]["ai_chat_processing"] == {"granted": 1, "declined": 1, "decided": 2, "rate": 0.5}
    assert rates["purposes"]["push_notifications"]["rate"] is None
    assert USER not in str(rates) and OTHER not in str(rates)


# ---- the older single yes --------------------------------------------------------------------------------------------------

def test_an_existing_single_yes_still_counts_until_its_wording_changes(cenv):
    doc_store.put(cenv.db, USER, consent.KIND, consent.KEY, {"accepted": True, "version": consent.VERSION, "at": "2026-10-01T00:00:00+00:00"})
    consent.forget(USER)
    assert consent.is_granted(cenv.db, USER, "ai_chat_processing") is True
    assert consent.is_granted(cenv.db, USER, "health_memory_from_chat") is False      # the old yes never covered anything else
    put(cenv, "ai_chat_processing", False)
    assert consent.is_granted(cenv.db, USER, "ai_chat_processing") is False


def test_get_many_and_chunked_delete(cenv):
    for i in range(5):
        doc_store.put(cenv.db, USER, "chat_feedback", f"m{i}", {"rating": "up"})
    doc_store.put(cenv.db, OTHER, "chat_feedback", "m0", {"rating": "down"})
    got = doc_store.get_many(cenv.db, USER, "chat_feedback", ["m0", "m3", "nope", "m3"])
    assert got == {"m0": {"rating": "up"}, "m3": {"rating": "up"}}
    assert doc_store.get_many(cenv.db, USER, "chat_feedback", []) == {}
    assert doc_store.delete_everything(cenv.db, USER) == 5
    assert doc_store.get(cenv.db, OTHER, "chat_feedback", "m0") == {"rating": "down"}
