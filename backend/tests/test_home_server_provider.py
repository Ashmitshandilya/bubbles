"""The owner's home server (Ollama on an Ubuntu laptop, docs/HOME_SERVER.md) as the last keyed fallback."""
import pytest

import admin_settings
import ai_provider


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("HOME_LLM_URL", "HOME_LLM_TOKEN", "HOME_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ai_provider, "ALLOW_PAID_AI", False)
    admin_settings._values.pop("provider_paused.HomeServer", None)
    yield
    admin_settings._values.pop("provider_paused.HomeServer", None)


def _call(*args):
    # The function the chain really calls (the route smoke test replaces the module attribute ai_provider.call_* for the session).
    return dict(ai_provider.AUTHENTICATED_PROVIDERS)["HomeServer"](*args)


def _names(**kw):
    return [name for name, _fn in ai_provider.provider_pool(health_data=True, **kw)]


def test_not_in_the_pool_until_configured():
    assert "HomeServer" not in _names()


def test_last_in_the_pool_when_configured(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://bubbles-home.example.ts.net")
    monkeypatch.setenv("HOME_LLM_TOKEN", "t" * 64)
    assert _names()[-1] == "HomeServer"


def test_a_url_without_a_token_is_not_used(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://bubbles-home.example.ts.net")
    assert "HomeServer" not in _names()


@pytest.mark.parametrize("url", ["http://bubbles-home.example.ts.net", "http://192.168.1.20:8088", "ftp://x"])
def test_plain_http_is_refused_except_loopback(monkeypatch, url):
    monkeypatch.setenv("HOME_LLM_URL", url)
    monkeypatch.setenv("HOME_LLM_TOKEN", "t" * 64)
    assert ai_provider.home_server_url() is None
    assert "HomeServer" not in _names()


@pytest.mark.parametrize("given, expected", [
    ("https://h.ts.net", "https://h.ts.net/v1/chat/completions"),
    ("https://h.ts.net/", "https://h.ts.net/v1/chat/completions"),
    ("https://h.ts.net/v1", "https://h.ts.net/v1/chat/completions"),
    ("https://h.ts.net/v1/chat/completions", "https://h.ts.net/v1/chat/completions"),
    ("http://127.0.0.1:8088", "http://127.0.0.1:8088/v1/chat/completions"),
])
def test_url_forms(monkeypatch, given, expected):
    monkeypatch.setenv("HOME_LLM_URL", given)
    monkeypatch.setenv("HOME_LLM_TOKEN", "t" * 64)
    assert ai_provider.home_server_url() == expected


def test_an_admin_pause_removes_it(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://h.ts.net")
    monkeypatch.setenv("HOME_LLM_TOKEN", "t" * 64)
    admin_settings._values["provider_paused.HomeServer"] = True
    assert "HomeServer" not in _names()
    assert "HomeServer" in admin_settings.chain_names()


def test_a_model_off_the_list_fails_closed(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://h.ts.net")
    monkeypatch.setenv("HOME_LLM_TOKEN", "t" * 64)
    monkeypatch.setenv("HOME_LLM_MODEL", "gpt-5")
    called = []
    monkeypatch.setattr(ai_provider._SESSION, "post", lambda *a, **k: called.append(1))
    with pytest.raises(ai_provider.ProviderError, match="allowlist"):
        _call("sys", "hi")
    assert not called


class _Response:
    status_code = 200
    text = ""

    def json(self):
        return {"choices": [{"message": {"content": '{"reply": "ok"}'}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}


def test_sends_the_token_asks_for_json_and_gets_the_longer_timeout(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://h.ts.net")
    monkeypatch.setenv("HOME_LLM_TOKEN", "secret-token")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return _Response()

    monkeypatch.setattr(ai_provider._SESSION, "post", fake_post)
    result = _call("sys", "hi")
    assert result.provider == "HomeServer" and result.model == "llama3.2:3b"
    assert seen["url"] == "https://h.ts.net/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer secret-token"
    assert seen["json"]["response_format"] == {"type": "json_object"}
    assert seen["timeout"] == ai_provider.HOME_LLM_TIMEOUT > ai_provider.REQUEST_TIMEOUT


def test_the_reply_budget_still_caps_it(monkeypatch):
    monkeypatch.setenv("HOME_LLM_URL", "https://h.ts.net")
    monkeypatch.setenv("HOME_LLM_TOKEN", "secret-token")
    seen = {}
    monkeypatch.setattr(ai_provider._SESSION, "post", lambda url, **k: seen.update(k) or _Response())
    with ai_provider.reply_budget(10):
        _call("sys", "hi")
    assert seen["timeout"] <= 10
