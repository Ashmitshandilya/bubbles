"""The shared Supabase HTTP client: HTTP/1.1, bounded waits, and one quiet retry of a read on a dropped connection."""
import httpx
import pytest

import supabase_client
from supabase_client import _RetryStaleConnection, _http_client


def _flaky(monkeypatch, failures: int):
    calls = []

    def handle(self, request):
        calls.append(request.method)
        if len(calls) <= failures:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.", request=request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    return calls


def test_a_read_on_a_dropped_connection_is_sent_once_more(monkeypatch):
    calls = _flaky(monkeypatch, failures=1)
    response = _RetryStaleConnection().handle_request(httpx.Request("GET", "https://db.test/rest/v1/profiles"))
    assert response.status_code == 200
    assert calls == ["GET", "GET"]


def test_a_write_is_never_sent_twice(monkeypatch):
    calls = _flaky(monkeypatch, failures=1)
    with pytest.raises(httpx.RemoteProtocolError):
        _RetryStaleConnection().handle_request(httpx.Request("POST", "https://db.test/rest/v1/chat_messages"))
    assert calls == ["POST"]


def test_a_read_is_retried_only_once(monkeypatch):
    calls = _flaky(monkeypatch, failures=2)
    with pytest.raises(httpx.RemoteProtocolError):
        _RetryStaleConnection().handle_request(httpx.Request("GET", "https://db.test/rest/v1/profiles"))
    assert len(calls) == 2


def test_client_uses_http1_and_bounded_timeouts():
    client = _http_client()
    try:
        assert client.timeout.connect == 5.0 and client.timeout.read is not None
        assert isinstance(client._transport, _RetryStaleConnection)
        assert client._transport._pool._http2 is False
    finally:
        client.close()


def test_database_and_sign_in_share_the_safe_client():
    db = supabase_client.supabase
    assert isinstance(db.postgrest.session._transport, _RetryStaleConnection)
    assert db.auth._http_client is db.postgrest.session
