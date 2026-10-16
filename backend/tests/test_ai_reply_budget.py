"""One chat reply has one time budget for every AI call (Gemini, the fallback pool, retries)."""
import time

import pytest

import ai_provider
from ai_provider import ProviderError, call_timeout, reply_budget


def test_without_a_budget_each_call_keeps_its_own_cap():
    assert call_timeout(12.0) == 12.0


def test_a_call_never_outlasts_what_is_left_of_the_budget():
    with reply_budget(6.0):
        assert 5.0 < call_timeout(45.0) <= 6.0
        assert call_timeout(4.0) == 4.0


def test_a_spent_budget_stops_new_calls():
    with reply_budget(0.0):
        with pytest.raises(ProviderError):
            call_timeout()


def test_an_inner_budget_never_extends_the_outer_one():
    with reply_budget(4.0):
        with reply_budget(60.0):
            assert call_timeout(45.0) <= 4.0
    assert call_timeout(9.0) == 9.0


def test_the_fallback_pool_gives_up_fast_once_the_budget_is_spent(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_provider._SESSION, "post", lambda *a, **k: calls.append(k) or pytest.fail("no call after the budget"))
    for name in ("GROQ", "NVIDIA", "MISTRAL"):
        monkeypatch.setenv(f"{name}_API_KEY", "test-key")
    started = time.monotonic()
    with reply_budget(0.0), pytest.raises(ProviderError):
        ai_provider.call_fallback("system", "hello")
    assert calls == []
    assert time.monotonic() - started < 1.0


def test_provider_calls_get_the_budgeted_timeout(monkeypatch):
    seen = []

    class Response:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(*args, **kwargs):
        seen.append(kwargs["timeout"])
        return Response()

    monkeypatch.setattr(ai_provider._SESSION, "post", fake_post)
    with reply_budget(7.0):
        ai_provider._post_openai_compatible("Groq", "https://example.test", "key", "openai/gpt-oss-20b", "system", "hello")
    assert seen and seen[0] <= 7.0


def test_gemini_call_has_a_timeout():
    from pathlib import Path
    source = Path(__file__).parent.parent.joinpath("bubbles_ai.py").read_text(encoding="utf-8")
    assert "http_options=types.HttpOptions(timeout=" in source
    assert "with reply_budget():" in source
