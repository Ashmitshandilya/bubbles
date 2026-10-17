"""LOAD TEST SERVER. The preview server (fake in-memory database, demo person, token "preview") with the AI providers replaced by a
50 ms stub, so a run never contacts a real provider, Supabase or production.   BUBBLES_PREVIEW=1 python loadtest/server.py"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("BUBBLES_PREVIEW", "1")
# one demo person from one address plays every virtual user, so the per-user and per-address limits are lifted (they are tested elsewhere)
for key in ("BUBBLES_CHAT_RATE_LIMIT", "BUBBLES_IP_RATE_LIMIT"):
    os.environ.setdefault(key, "10000000")
for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "MISTRAL_API_KEY"):
    os.environ.pop(key, None)  # no key, so no real provider could be called even if the stub were bypassed

import preview_server  # noqa: E402
import bubbles_ai  # noqa: E402


def _stub(message, system_instruction):
    time.sleep(0.05)
    return bubbles_ai.BubblesAIResponse(response="Sounds like a long day. Want to log how you slept?", sentiment="neutral", health_events=[])


bubbles_ai._call_gemini = _stub

if __name__ == "__main__":
    import uvicorn

    preview_server.preview_seed.seed(preview_server.main.app, preview_server.db, preview_server.USER)
    uvicorn.run(preview_server.main.app, host="127.0.0.1", port=int(os.environ.get("PREVIEW_PORT", "8001")), log_level="warning")
