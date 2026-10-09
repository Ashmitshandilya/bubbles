"""Client timezone: header -> per-request value -> local_today(); CORS allows the header; default behaviour unchanged."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import calc_core
import main
import wellness_common as W


def test_parse_tz_header():
    assert W.parse_tz_header("330") == 330 and W.parse_tz_header(" -300 ") == -300
    assert W.parse_tz_header("99999") == W.TZ_LIMIT_MIN and W.parse_tz_header("abc") is None and W.parse_tz_header(None) is None


def test_local_today_follows_request_timezone_and_defaults_to_utc():
    t = datetime(2026, 10, 8, 22, 7, tzinfo=timezone.utc)
    assert calc_core.local_today(None, t).isoformat() == "2026-10-08"      # no header -> UTC, as before
    token = W.REQUEST_TZ.set(330)
    try:
        assert calc_core.local_today(None, t).isoformat() == "2026-10-09"  # India
        assert calc_core.local_today(0, t).isoformat() == "2026-10-08"     # explicit offset still wins
    finally:
        W.REQUEST_TZ.reset(token)
    assert W.request_tz() is None


def test_middleware_sets_and_resets_the_value(monkeypatch):
    seen = []
    monkeypatch.setattr(main, "_guard_request", lambda request: seen.append(W.request_tz()) or None)
    c = TestClient(main.app)
    c.get("/health", headers={"X-Tz-Offset-Minutes": "330"})
    c.get("/health", headers={"X-Tz-Offset-Minutes": "nonsense"})
    c.get("/health")
    assert seen == [330, None, None] and W.request_tz() is None


def test_cors_preflight_allows_the_header():
    r = TestClient(main.app).options("/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                                                          "Access-Control-Request-Headers": "x-tz-offset-minutes,authorization"})
    assert r.status_code == 200 and "x-tz-offset-minutes" in r.headers.get("access-control-allow-headers", "").lower()
