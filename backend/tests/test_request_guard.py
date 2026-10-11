"""Request-level protections: body size (including chunked bodies), address limits, the access-log filter and the admin gate."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import request_guard as G


def echo_app(limit: int) -> TestClient:
    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return {"size": len(body)}

    app.add_middleware(G.BodyLimitMiddleware, max_bytes=limit)
    return TestClient(app, raise_server_exceptions=False)


def test_a_declared_body_over_the_limit_is_refused_without_reading_it():
    client = echo_app(100)
    ok = client.post("/echo", content=b"x" * 100)
    assert ok.status_code == 200 and ok.json() == {"size": 100}
    big = client.post("/echo", content=b"x" * 101)
    assert big.status_code == 413 and big.json()["code"] == "too_large"


def test_a_streamed_body_without_content_length_is_stopped_at_the_limit():
    client = echo_app(100)

    def chunks(total: int):
        for _ in range(total // 10):
            yield b"x" * 10

    assert client.post("/echo", content=chunks(100)).status_code == 200
    refused = client.post("/echo", content=chunks(1000))
    assert refused.status_code == 413


def test_the_default_limit_is_two_megabytes():
    assert G.MAX_BODY_BYTES == 2_000_000


def test_share_tokens_and_query_strings_never_reach_the_log():
    assert G.redact_path("/partner/abcDEF123_-token?x=1") == "/partner/[redacted]"
    assert G.redact_path("/cycle/partner/secretvalue") == "/cycle/partner/[redacted]"
    assert G.redact_path("/fitness/foods/search?q=chest+pain") == "/fitness/foods/search"
    assert G.redact_path("/health") == "/health"
    assert G.redact_path("/partner-sharing/connect") == "/partner-sharing/connect"


def test_the_access_log_filter_rewrites_uvicorn_records():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/partner/tok123?a=b", "1.1", 200), None)
    assert G.AccessLogRedactor().filter(record) is True
    assert record.args[2] == "/partner/[redacted]" and record.args[0] == "1.2.3.4:5" and record.args[4] == 200
    G.install_access_log_redaction()
    G.install_access_log_redaction()
    assert sum(isinstance(f, G.AccessLogRedactor) for f in logging.getLogger("uvicorn.access").filters) == 1


def test_only_listed_administrators_pass_the_admin_gate(monkeypatch):
    monkeypatch.delenv("BUBBLES_ADMIN_USER_IDS", raising=False)
    with pytest.raises(HTTPException) as nobody:
        G.require_admin(SimpleNamespace(id="u1"))
    assert nobody.value.status_code == 403
    monkeypatch.setenv("BUBBLES_ADMIN_USER_IDS", " u9 , u1 ")
    G.require_admin(SimpleNamespace(id="u1"))
    with pytest.raises(HTTPException):
        G.require_admin(SimpleNamespace(id="u2"))


@pytest.fixture()
def main_module(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_dummy_for_tests")
    return pytest.importorskip("main")


def fake_request(path="/profile", auth=None, ip="9.9.9.9"):
    headers = {"cf-connecting-ip": ip}
    if auth:
        headers["authorization"] = auth
    return SimpleNamespace(url=SimpleNamespace(path=path), headers=headers, client=SimpleNamespace(host=ip))


def test_one_address_cannot_flood_the_api_but_health_checks_always_pass(main_module, monkeypatch):
    from chat_pipeline import RateLimiter
    monkeypatch.setattr(main_module, "_ip_limiter", RateLimiter(limit=3, window=60))
    results = [main_module._guard_request(fake_request(ip="1.1.1.1")) for _ in range(5)]
    assert [r is None for r in results] == [True, True, True, False, False]
    assert results[3].status_code == 429
    assert main_module._guard_request(fake_request(path="/health", ip="1.1.1.1")) is None
    assert main_module._guard_request(fake_request(ip="2.2.2.2")) is None  # another address is unaffected


def test_an_address_that_keeps_sending_bad_tokens_is_stopped_before_sign_in_is_called(main_module, monkeypatch):
    from chat_pipeline import RateLimiter
    monkeypatch.setattr(main_module, "_ip_limiter", RateLimiter(limit=1000, window=60))
    monkeypatch.setattr(main_module, "_auth_fail_limiter", RateLimiter(limit=2, window=60))
    for _ in range(2):
        main_module._auth_fail_limiter.record("ip:3.3.3.3")
    stopped = main_module._guard_request(fake_request(auth="Bearer made-up", ip="3.3.3.3"))
    assert stopped is not None and stopped.status_code == 429
    assert main_module._guard_request(fake_request(auth=None, ip="3.3.3.3")) is None     # no token: nothing to protect
    assert main_module._guard_request(fake_request(auth="Bearer made-up", ip="4.4.4.4")) is None


def test_partner_invite_guessing_is_limited_per_address(main_module, monkeypatch):
    from chat_pipeline import RateLimiter
    monkeypatch.setattr(main_module, "_ip_limiter", RateLimiter(limit=1000, window=60))
    monkeypatch.setattr(main_module, "_connect_limiter", RateLimiter(limit=2, window=3600))
    hits = [main_module._guard_request(fake_request(path="/partner-sharing/connect", auth="Bearer t", ip="5.5.5.5")) for _ in range(3)]
    assert hits[0] is None and hits[1] is None and hits[2].status_code == 429


def test_operational_routes_are_for_administrators_only(main_module, monkeypatch):
    monkeypatch.delenv("BUBBLES_ADMIN_USER_IDS", raising=False)
    monkeypatch.setattr(main_module, "get_authenticated_user", lambda authorization: SimpleNamespace(id="ordinary-user"))
    for fn in (main_module.production_readiness, main_module.models_registry, main_module.ai_telemetry, main_module.privacy_security_baseline):
        with pytest.raises(HTTPException) as refused:
            fn(authorization="Bearer x")
        assert refused.value.status_code == 403
    monkeypatch.setenv("BUBBLES_ADMIN_USER_IDS", "ordinary-user")
    assert main_module.privacy_security_baseline(authorization="Bearer x")["status"] == "success"
