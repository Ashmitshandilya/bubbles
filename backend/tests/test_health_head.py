"""/health must answer both GET and HEAD with 200 (uptime monitors probe with HEAD) and stay unauthenticated."""
from fastapi.testclient import TestClient

import main


def test_health_answers_get_and_head_without_login():
    c = TestClient(main.app)
    assert c.get("/health").status_code == 200
    h = c.head("/health")
    assert h.status_code == 200 and h.content == b""
