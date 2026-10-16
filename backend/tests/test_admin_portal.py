"""Admin portal: the gate, telemetry privacy, failure isolation, caches, provider pauses and settings (the review's conditions).

Each test names the review condition it covers (docs/admin/DESIGN.md, Sir Noah's conditions 1 to 14).
"""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

import admin_settings
import ai_provider
import bubbles_ai
import consent
import doc_store
import ops_telemetry
from ai_provider import ProviderError, ProviderResult
from test_chat_http_flow import USER, env, send  # noqa: F401  (stateful app, fake database, stub model)

ADMIN = "aaaaaaaa-0000-0000-0000-00000000000a"


def jwt(aal: str = "aal2", exp_in: float = 3600, sub: str = "x") -> str:
    def part(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{part({'alg': 'HS256'})}.{part({'aal': aal, 'exp': time.time() + exp_in, 'sub': sub})}.sig"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_env(env, monkeypatch):
    original = env.main._verify_token
    users: dict[str, NS] = {}
    calls: list[str] = []

    def verify(token):
        calls.append(token)
        if token in users:
            return users[token]
        return original(token)

    monkeypatch.setattr(env.main, "_verify_token", verify)
    monkeypatch.setenv("BUBBLES_ADMIN_USER_IDS", ADMIN)
    tokens = NS(admin=jwt(), aal1=jwt("aal1"), user=jwt(sub="someone"))
    users[tokens.admin] = NS(id=ADMIN)
    users[tokens.aal1] = NS(id=ADMIN)
    users[tokens.user] = NS(id="someone-ordinary")
    env.tokens, env.verify_calls, env.real_verify = tokens, calls, original
    return env


def _events(kind: str | None = None) -> list[dict]:
    return [e for e in ops_telemetry.recent(0, 5000) if kind is None or e["kind"] == kind]


# 1 and 4 -------------------------------------------------------------------------------------------------------------------

def test_everyone_but_a_two_step_admin_gets_the_same_404_as_an_unknown_path(admin_env):
    c, t = admin_env.client, admin_env.tokens
    unknown = c.get("/no-such-route-anywhere")
    refused = [
        c.get("/admin/overview"),                                                   # no token
        c.get("/admin/overview", headers=bearer("junk")),                           # bad token
        c.get("/admin/overview", headers=bearer(t.user)),                           # ordinary user
        c.get("/admin/overview", headers=bearer(t.aal1)),                           # admin, password step only
        c.delete("/admin/settings", headers=bearer(t.user)),                        # wrong method
        c.put("/admin/settings", content=b"{not json", headers={**bearer(t.user), "content-type": "application/json"}),
        c.get("/admin/does-not-exist", headers=bearer(t.user)),                     # unknown admin path
        c.get("/admin", headers=bearer(t.user)),
    ]
    for res in refused:
        assert res.status_code == 404 and res.content == unknown.content
    assert c.get("/admin/overview", headers=bearer(t.admin)).status_code == 200


def test_with_no_admin_list_nobody_is_an_admin(admin_env, monkeypatch):
    monkeypatch.delenv("BUBBLES_ADMIN_USER_IDS", raising=False)
    assert admin_env.client.get("/admin/me", headers=bearer(admin_env.tokens.admin)).status_code == 404


def test_the_router_has_its_own_lock_even_without_the_middleware():
    import admin_api
    with pytest.raises(HTTPException) as refused:
        admin_api._admin(NS(state=NS()))
    assert refused.value.status_code == 404


# 2 and 3 -------------------------------------------------------------------------------------------------------------------

def test_bad_tokens_on_admin_paths_still_count_toward_the_bad_token_limit(admin_env, monkeypatch):
    from chat_pipeline import RateLimiter
    monkeypatch.setattr(admin_env.main, "_auth_fail_limiter", RateLimiter(limit=2, window=60))
    for _ in range(2):
        admin_env.client.get("/admin/me", headers={**bearer("junk"), "cf-connecting-ip": "7.7.7.7"})
    assert admin_env.main._auth_fail_limiter.over("ip:7.7.7.7")


def test_refusals_are_audited_at_most_once_a_minute_and_hold_no_token_address_or_id(admin_env):
    c, t = admin_env.client, admin_env.tokens
    for token in ("junk", t.user, t.aal1, "junk", "junk"):
        c.get("/admin/me", headers={**bearer(token), "cf-connecting-ip": "8.8.8.8"})
    audits = _events("audit")
    assert len(audits) == 1 and audits[0]["data"]["action"] == "admin_denied"
    text = json.dumps(audits)
    for secret in ("junk", t.user, "8.8.8.8", "someone-ordinary", ADMIN):
        assert secret not in text


# 5 ---------------------------------------------------------------------------------------------------------------------------

def test_events_hold_only_whitelisted_technical_fields_never_what_was_said(admin_env):
    c = admin_env.client
    assert send(admin_env, "My zebra-coloured rash has itched since Monday and I feel low").status_code == 200
    c.get("/partner/SECRETSHARETOKEN12345?q=zebra")
    c.get("/no-such-route?q=zebra")
    ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1, message="zebra", user_id=USER, ip="1.2.3.4")
    events = _events()
    text = json.dumps(events)
    for secret in ("zebra", "SECRETSHARETOKEN12345", USER, "1.2.3.4", "itched", "Bearer"):
        assert secret not in text
    for e in events:
        assert set(e) == {"seq", "at", "kind", "request_id", "data"}
        assert set(e["data"]) <= ops_telemetry.FIELDS[e["kind"]]
    chat = [e for e in events if e["kind"] == "api" and e["data"]["route"] == "/chat"]
    assert chat and chat[0]["data"]["route_kind"] in ops_telemetry.NOTE_VALUES["route_kind"] and chat[0]["data"]["ai_called"] is True
    assert {e["data"]["route"] for e in events if e["kind"] == "api"} >= {"unmatched"}


def test_a_note_only_accepts_values_from_the_fixed_lists():
    tokens = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.note(route_kind="I have chest pain", safety_level="RED", ai_called="yes", reasons="chest pain")
        assert ops_telemetry.current_note() == {"safety_level": "RED"}
    finally:
        ops_telemetry.end_request(tuple(tokens))


# 6 ---------------------------------------------------------------------------------------------------------------------------

def test_broken_telemetry_caches_and_settings_leave_chat_and_the_safety_gate_working(env, monkeypatch):
    monkeypatch.setattr(ops_telemetry, "_ring", None)              # every record() now fails inside
    monkeypatch.setattr(consent._cache, "_data", None)              # the consent cache is broken
    monkeypatch.setattr(admin_settings, "_values", None)            # settings cannot be read: nothing is paused
    red = send(env, "I have severe chest pain right now and I cannot breathe")
    assert red.status_code == 200 and red.json()["safety"]["level"] == "RED" and env.ai_calls == []
    ok = send(env, "I have been feeling really tired this week and I do not know why")
    assert ok.status_code == 200 and len(env.ai_calls) == 1


# 7 ---------------------------------------------------------------------------------------------------------------------------

def test_a_missing_table_means_memory_only_and_the_portal_says_so(admin_env, monkeypatch):
    class Missing:
        def table(self, *_a):
            raise Exception("PGRST205 Could not find the table 'public.bubbles_ops_events'")

    monkeypatch.setenv("BUBBLES_OPS_PERSIST", "1")
    monkeypatch.setattr(ops_telemetry, "_db", lambda: Missing())
    monkeypatch.setattr(ops_telemetry, "_ensure_flusher", lambda: None)
    ops_telemetry.record("api", method="GET", route="/x", status=200, latency_ms=1.0)
    assert ops_telemetry.flush_once() == 0 and ops_telemetry.status["mode"] == "not_set_up"
    rows, _capped, source = ops_telemetry.stored_events(datetime.now(timezone.utc) - timedelta(minutes=5))
    assert source == "memory" and rows
    assert send(admin_env, "I have been feeling really tired this week and I do not know why").status_code == 200
    body = admin_env.client.get("/admin/overview", headers=bearer(admin_env.tokens.admin)).json()
    assert body["system"]["persistence"]["mode"] == "not_set_up"
    assert any("memory only" in r for r in body["headline"]["reasons"])


# 8 ---------------------------------------------------------------------------------------------------------------------------

def test_sign_in_cache_keeps_successes_only_never_past_expiry_and_admin_always_checks_fresh(admin_env, monkeypatch):
    main, t = admin_env.main, admin_env.tokens
    calls = admin_env.verify_calls
    main.get_authenticated_user(f"Bearer {t.admin}")
    main.get_authenticated_user(f"Bearer {t.admin}")
    assert calls.count(t.admin) == 1                                   # remembered
    admin_env.client.get("/admin/me", headers=bearer(t.admin))
    assert calls.count(t.admin) == 2                                   # /admin never uses the memory

    expiring = jwt(exp_in=-5)
    for _ in range(2):
        with pytest.raises(HTTPException):
            main.get_authenticated_user(f"Bearer {expiring}")      # unknown to the fake: fails, and a failure is never remembered
    assert calls.count(expiring) == 2

    flaky = {"n": 0}

    def sometimes(token):
        flaky["n"] += 1
        if flaky["n"] == 1:
            raise HTTPException(status_code=401, detail="down")
        return NS(id="u-flaky")

    monkeypatch.setattr(main, "_verify_token", sometimes)
    token = jwt()
    with pytest.raises(HTTPException):
        main.get_authenticated_user(f"Bearer {token}")
    assert main.get_authenticated_user(f"Bearer {token}").id == "u-flaky"


def test_the_cache_never_outlives_the_token(admin_env, monkeypatch):
    main = admin_env.main
    seen = []
    monkeypatch.setattr(main, "_verify_token", lambda token: seen.append(token) or NS(id="u"))
    short = jwt(exp_in=0.5)
    main.get_authenticated_user(f"Bearer {short}")
    time.sleep(0.6)
    main.get_authenticated_user(f"Bearer {short}")
    assert len(seen) == 2


def test_two_step_is_still_required_through_the_cache(admin_env, monkeypatch):
    main = admin_env.main
    monkeypatch.setattr(main, "_verify_token", admin_env.real_verify)        # the real check, behind a fake sign-in service
    asked = []
    person = NS(id="u-mfa", factors=[{"status": "verified"}])
    monkeypatch.setattr(main, "supabase", NS(auth=NS(get_user=lambda token: asked.append(token) or NS(user=person))))
    password_only = jwt("aal1")
    for _ in range(2):
        with pytest.raises(HTTPException) as refused:
            main.get_authenticated_user(f"Bearer {password_only}")
        assert refused.value.status_code == 401
    assert len(asked) == 2                                                  # a refusal is never remembered
    assert main.get_authenticated_user(f"Bearer {jwt('aal2')}").id == "u-mfa"


# 9 ---------------------------------------------------------------------------------------------------------------------------

def test_withdrawing_consent_applies_to_the_very_next_message(env):
    assert send(env, "I have been feeling really tired this week and I do not know why").status_code == 200
    assert len(env.ai_calls) == 1                                       # consent read and remembered
    consent.set_ai_chat(env.db, USER, False)
    res = send(env, "I have also been sleeping badly and I do not know why")
    assert res.json()["consent_required"] is True and len(env.ai_calls) == 1


def test_deleting_all_data_forgets_the_remembered_consent(env):
    assert consent.has_ai_consent(env.db, USER) is True
    doc_store.delete_everything(env.db, USER)
    assert consent.has_ai_consent(env.db, USER) is False


# 10 --------------------------------------------------------------------------------------------------------------------------

def test_a_pause_only_removes_providers_and_never_grows_the_pool():
    full = [name for name, _ in ai_provider.provider_pool(health_data=True)]
    admin_settings._values["provider_paused.Groq"] = True
    paused = [name for name, _ in ai_provider.provider_pool(health_data=True)]
    assert paused == [n for n in full if n != "Groq"]
    assert set(paused) <= {name for name, _ in ai_provider.AUTHENTICATED_PROVIDERS}


def test_everything_paused_gives_the_calm_fallback_message_without_calling_anyone(monkeypatch):
    for name in admin_settings.chain_names():
        admin_settings._values[f"provider_paused.{name}"] = True
    monkeypatch.setattr(bubbles_ai, "_call_gemini_inner", lambda *a, **k: pytest.fail("Gemini is paused"))
    result = bubbles_ai.ask_bubbles("hello")
    assert bubbles_ai.is_degraded(result)
    assert _events("ai_attempt") == [] and _events("ai_reply")[0]["data"]["outcome"] == "degraded"


def test_only_known_chain_names_can_be_paused(admin_env):
    c, h = admin_env.client, bearer(admin_env.tokens.admin)
    for key in ("provider_paused.KeylessAI", "provider_paused.Kilo", "ALLOW_PAID_AI", "safety.rules", "provider_paused.Groq "):
        assert c.put("/admin/settings", json={"key": key, "value": True}, headers=h).status_code == 422
    assert c.put("/admin/settings", json={"key": "provider_paused.Groq", "value": True}, headers=h).status_code == 200
    assert admin_settings.is_paused("Groq")


# 11 --------------------------------------------------------------------------------------------------------------------------

def test_every_settings_change_is_audited_with_old_and_new_values(admin_env):
    c, h = admin_env.client, bearer(admin_env.tokens.admin)
    assert c.put("/admin/settings", json={"key": "telemetry_retention_days", "value": 30}, headers=h).status_code == 200
    assert ops_telemetry.retention_days == 30
    assert c.put("/admin/settings", json={"key": "telemetry_retention_days", "value": 0}, headers=h).status_code == 422
    changed = [e["data"] for e in _events("audit") if e["data"]["action"] == "setting_changed"]
    assert changed == [{"action": "setting_changed", "target": "telemetry_retention_days", "old": 14, "new": 30, "actor": ADMIN,
                        "outcome": changed[0]["outcome"]}]
    assert any(e["data"]["action"] == "setting_rejected" for e in _events("audit"))
    c.put("/admin/settings", json={"key": "my secret typed text", "value": True}, headers=h)
    assert "my secret typed text" not in json.dumps(_events("audit"))
    listed = {s["key"] for s in c.get("/admin/settings", headers=h).json()["settings"]}
    assert "telemetry_retention_days" in listed and "provider_paused.Gemini" in listed and "cache_enabled.sign_in" in listed


def test_turning_a_cache_off_empties_it_and_is_respected():
    consent._cache.put(("u", consent.VERSION), True)
    admin_settings.update("cache_enabled.consent", False, actor=ADMIN)
    assert consent._cache.enabled is False and consent._cache.stats()["entries"] == 0


# 12 --------------------------------------------------------------------------------------------------------------------------

GOOD = '{"response": "Here is a calm answer.", "sentiment": "neutral", "health_events": []}'


def _fallback(content, provider="Groq"):
    def call(system_instruction, user_message, *, health_data, first_position, defer_success):
        assert defer_success is True
        return ProviderResult(provider, "model-x", content, latency_ms=12.0, position=first_position)
    return call


def test_the_answering_provider_is_recorded_only_after_a_validated_answer(monkeypatch):
    def gemini_down(*_a, **_k):
        raise ProviderError("Gemini: HTTP 503: unavailable")

    monkeypatch.setattr(bubbles_ai, "_call_gemini_inner", gemini_down)
    monkeypatch.setattr(bubbles_ai, "call_fallback", _fallback(GOOD))
    assert not bubbles_ai.is_degraded(bubbles_ai.ask_bubbles("hello"))
    attempts = [e["data"] for e in _events("ai_attempt")]
    assert [(a["provider"], a["position"], a["outcome"]) for a in attempts] == [("Gemini", 1, "error"), ("Groq", 2, "success")]
    assert attempts[0]["error_category"] == "provider_error"
    reply = _events("ai_reply")[0]["data"]
    assert (reply["outcome"], reply["provider"], reply["attempts"], reply["fallback_used"]) == ("answered", "Groq", 2, True)
    assert len({e["request_id"] for e in _events() if e["kind"].startswith("ai_")}) == 1


def test_an_unusable_answer_is_not_counted_as_an_answer(monkeypatch):
    monkeypatch.setattr(bubbles_ai, "_call_gemini_inner", lambda *a, **k: (_ for _ in ()).throw(ProviderError("down")))
    monkeypatch.setattr(bubbles_ai, "call_fallback", _fallback("this is not json"))
    assert bubbles_ai.is_degraded(bubbles_ai.ask_bubbles("hello"))
    assert [e["data"]["outcome"] for e in _events("ai_attempt")] == ["error", "invalid_json"]
    assert [e["data"]["outcome"] for e in _events("ai_reply")] == ["degraded"]


@pytest.mark.parametrize("error, category", [
    (ProviderError("the reply time budget is spent"), "budget_spent"),
    (TimeoutError("read timed out"), "timeout"),
    (ProviderError("Groq: HTTP 429: slow down"), "rate_limited"),
    (ProviderError("GEMINI_API_KEY is not configured."), "not_configured"),
])
def test_gemini_failures_and_timeouts_are_recorded_with_a_category(monkeypatch, error, category):
    def fail(*_a, **_k):
        raise error

    monkeypatch.setattr(bubbles_ai, "_call_gemini_inner", fail)
    monkeypatch.setattr(bubbles_ai, "call_fallback", _fallback(GOOD))
    bubbles_ai.ask_bubbles("hello")
    first = _events("ai_attempt")[0]["data"]
    assert first["provider"] == "Gemini" and first["error_category"] == category
    assert "slow down" not in json.dumps(_events())                          # the error text itself is never kept


# 13 --------------------------------------------------------------------------------------------------------------------------

def test_the_migration_locks_both_tables_to_the_server():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "20261013_bubbles_ops.sql").read_text(encoding="utf-8").lower()
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert body.strip().startswith("begin;") and body.strip().endswith("commit;")
    assert "if not exists" not in body and "create policy" not in body and "create function" not in body
    for table in ("bubbles_ops_events", "bubbles_admin_settings"):
        assert f"create table public.{table}" in body
        assert f"alter table public.{table} enable row level security" in body
        assert f"revoke all on table public.{table} from anon, authenticated" in body
    assert "revoke all on sequence public.bubbles_ops_events_id_seq from anon, authenticated" in body
    assert "grant select, insert, delete on table public.bubbles_ops_events to service_role" in body


# 14 --------------------------------------------------------------------------------------------------------------------------

def test_admin_lists_are_paged_and_say_when_they_were_capped(admin_env):
    c, h = admin_env.client, bearer(admin_env.tokens.admin)
    for i in range(7):
        ops_telemetry.record("ai_attempt", provider="Groq", model="m", position=1, outcome="success", latency_ms=float(i))
        time.sleep(0.002)
    first = c.get("/admin/events?kind=ai_attempt&limit=3", headers=h).json()
    assert len(first["events"]) == 3 and first["next_before"] and first["capped"] is False and first["cap"] > 0
    from urllib.parse import quote
    second = c.get(f"/admin/events?kind=ai_attempt&limit=3&before={quote(first['next_before'])}", headers=h).json()
    assert len(second["events"]) == 3
    assert {e["seq"] for e in first["events"]}.isdisjoint({e["seq"] for e in second["events"]})
    assert c.get("/admin/events?limit=500", headers=h).status_code == 422
    assert c.get("/admin/events?provider=KeylessAI", headers=h).status_code == 422
    assert c.get("/admin/events?request_id=zz;drop", headers=h).status_code == 422
    rows, capped, _ = ops_telemetry.stored_events(datetime.now(timezone.utc) - timedelta(hours=1), cap=5)
    assert len(rows) == 5 and capped is True


def test_the_admin_views_answer_for_an_admin(admin_env):
    c, h = admin_env.client, bearer(admin_env.tokens.admin)
    send(admin_env, "I have been feeling really tired this week and I do not know why")
    me = c.get("/admin/me", headers=h).json()
    assert me["admin"] is True and me["chain"][0]["provider"] == "Gemini" and me["live_refresh_seconds"] == 3
    for path in ("/admin/overview?range=15m", "/admin/ai?range=24h", "/admin/api", "/admin/audit", "/admin/settings", "/admin/events/live"):
        res = c.get(path, headers=h)
        assert res.status_code == 200 and res.json()["status"] == "success", path
    live = c.get("/admin/events/live?after=0", headers=h).json()
    assert live["events"] and live["next_cursor"] == live["events"][-1]["seq"]
    again = c.get(f"/admin/events/live?after={live['next_cursor']}&process_started_at=1999-01-01T00:00:00", headers=h).json()
    assert again["restarted"] is True
    assert c.post("/admin/cache/clear", headers=h).json()["status"] == "success"
    assert any(e["data"]["action"] == "caches_cleared" for e in _events("audit"))
    assert c.get("/openapi.json").status_code in (200, 404) and "/admin" not in c.get("/openapi.json").text


# Final review fixes ----------------------------------------------------------------------------------------------------------

def test_a_made_up_method_or_a_huge_value_never_reaches_an_event(env):
    env.client.request("ZEBRARASHMETHOD", "/health")
    ops_telemetry.record("ai_attempt", provider="Groq", model="m" * 5000, position=1, outcome="success", latency_ms=1.0)
    events = _events()
    text = json.dumps(events)
    assert "ZEBRA" not in text and any(e["data"].get("method") == "OTHER" for e in events if e["kind"] == "api")
    assert all(len(v) <= ops_telemetry.MAX_TEXT for e in events for v in e["data"].values() if isinstance(v, str))


def test_delete_all_forgets_the_consent_answer_even_when_a_delete_fails(env, monkeypatch):
    assert consent.has_ai_consent(env.db, USER) is True               # remembered
    assert consent._cache.stats()["entries"] == 1
    doc_store.put(env.db, USER, "plan", "p1", {"x": 1})               # something to delete
    real_table = env.db.table

    class Failing:
        def __init__(self, name):
            self.inner = real_table(name)

        def __getattr__(self, attr):
            if attr == "delete":
                raise RuntimeError("database went away mid-delete")
            return getattr(self.inner, attr)

    monkeypatch.setattr(env.db, "table", lambda name: Failing(name))
    with pytest.raises(RuntimeError):
        doc_store.delete_everything(env.db, USER)
    assert consent._cache.stats()["entries"] == 0                    # the next message reads the answer again


def test_nobody_configured_means_no_sign_in_call_at_all(admin_env, monkeypatch):
    monkeypatch.delenv("BUBBLES_ADMIN_USER_IDS", raising=False)
    before = len(admin_env.verify_calls)
    assert admin_env.client.get("/admin/me", headers=bearer(admin_env.tokens.admin)).status_code == 404
    assert len(admin_env.verify_calls) == before
