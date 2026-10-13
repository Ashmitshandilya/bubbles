"""DEV ONLY. Runs the REAL Bubbles API on an in-memory fake database with a signed-in demo person ("Riya") and about 60 days of
synthetic history, so every screen can be looked at with realistic data and no login.

    BUBBLES_PREVIEW=1 python preview_server.py        # http://127.0.0.1:8001, token "preview"

Refuses to start without BUBBLES_PREVIEW=1. Never imported by the app. Uses the test suite's FakeDB, so nothing leaves this machine.
"""
import os
import sys

if os.environ.get("BUBBLES_PREVIEW") != "1":
    raise SystemExit("Preview server: set BUBBLES_PREVIEW=1 to run it (dev only).")

os.environ.setdefault("SUPABASE_URL", "https://preview.invalid")
os.environ.setdefault("SUPABASE_SECRET_KEY", "preview")
os.environ.setdefault("BUBBLES_FRONTEND_ORIGINS", "http://localhost:3100,http://127.0.0.1:3100")
os.environ.setdefault("BUBBLES_OPS_PERSIST", "0")   # admin telemetry stays in memory: nothing is written anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fake_db import FakeDB  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000aa"
db = FakeDB({"preview": USER})

import supabase_client  # noqa: E402

supabase_client.supabase = db   # BEFORE main is imported, so every module sees the fake

import main  # noqa: E402
import preview_seed  # noqa: E402

# The demo person may open /admin in the preview. Preview tokens are not real sign-in tokens, so the two-step check is answered for
# them here. This file is never imported by the app and refuses to start without BUBBLES_PREVIEW=1.
os.environ.setdefault("BUBBLES_ADMIN_USER_IDS", USER)
main.token_aal = lambda _token: "aal2"

if __name__ == "__main__":
    report = preview_seed.seed(main.app, db, USER)
    print("seeded:", report, flush=True)
    import uvicorn

    uvicorn.run(main.app, host="127.0.0.1", port=int(os.environ.get("PREVIEW_PORT", "8001")), log_level="warning")
