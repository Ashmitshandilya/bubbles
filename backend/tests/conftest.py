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
