from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# The address-based limits in front of every route are for real traffic. The suite sends hundreds of requests from one address, so they are
# raised for the test process only (the limits themselves are tested directly in tests/test_request_guard.py).
os.environ.setdefault("BUBBLES_IP_RATE_LIMIT", "1000000")
os.environ.setdefault("BUBBLES_AUTH_FAIL_LIMIT", "1000000")
os.environ.setdefault("BUBBLES_CONNECT_RATE_LIMIT", "1000000")
# Telemetry stays in memory during tests (no background writer against the dummy database address).
os.environ.setdefault("BUBBLES_OPS_PERSIST", "0")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_server_state():
    """Every test starts with empty server caches, telemetry and admin settings, so nothing remembered leaks between tests."""
    import admin_settings
    import ops_telemetry
    import ttl_cache
    ttl_cache.clear_all()
    for cache in list(ttl_cache._registry.values()):
        cache.enabled = True
    ops_telemetry.reset_for_tests()
    admin_settings.reset_for_tests()
    yield
