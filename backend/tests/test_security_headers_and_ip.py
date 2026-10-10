"""Security headers, rate-limit client address, and request ids on 500s."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
import privacy_security  # noqa: E402


def _req(headers, host="10.0.0.1"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_client_ip_prefers_cloudflare_then_rightmost_forwarded_hop():
    assert main.client_ip(_req({"cf-connecting-ip": "1.1.1.1", "x-forwarded-for": "9.9.9.9, 2.2.2.2"})) == "1.1.1.1"
    assert main.client_ip(_req({"x-forwarded-for": "6.6.6.6, 2.2.2.2"})) == "2.2.2.2"     # a client-supplied left hop is ignored
    assert main.client_ip(_req({})) == "10.0.0.1"


def test_security_headers_include_hsts_and_permissions_policy():
    h = privacy_security.security_headers()
    assert h["Strict-Transport-Security"].startswith("max-age=") and "camera=()" in h["Permissions-Policy"]
    assert h["X-Frame-Options"] == "DENY" and h["Cache-Control"] == "no-store" and "Content-Security-Policy" not in h


def test_500_carries_a_request_id_header_and_body():
    from fastapi.testclient import TestClient

    @main.app.get("/_boom_request_id")
    def boom():
        raise RuntimeError("secret health detail")

    res = TestClient(main.app, raise_server_exceptions=False).get("/_boom_request_id")
    assert res.status_code == 500 and res.headers["x-request-id"] == res.json()["request_id"] and len(res.json()["request_id"]) == 8
    assert "secret" not in res.text
