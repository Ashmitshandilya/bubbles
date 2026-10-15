"""Local latency benchmark for POST /chat (dev only, never touches a real service).

    cd backend && python loadtest/chat_bench.py [--n 30] [--rtt-ms 80] [--stream]

Runs the REAL FastAPI app in-process on the test suite's FakeDB. Every database call and the embedding HTTP call sleep ``--rtt-ms``
(default 80 ms, about one Render Singapore to Supabase Seoul round trip) so the number reflects how many round trips a chat turn
makes and how many of them overlap. The AI call itself is stubbed (``--ai-ms`` of artificial latency, default 0), so the number is the
backend's own overhead around the model. Prints p50 / p95 in milliseconds for an open-ended (AI route) message and for a
deterministic daily-log message.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
for p in (BACKEND, os.path.join(BACKEND, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("SUPABASE_URL", "https://bench.invalid")
os.environ.setdefault("SUPABASE_SECRET_KEY", "bench")
os.environ.setdefault("BUBBLES_OPS_PERSIST", "0")
os.environ["BUBBLES_CHAT_RATE_LIMIT"] = "100000"
for key in ("GROQ_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"):
    os.environ.pop(key, None)

USER = "00000000-0000-0000-0000-0000000000bb"
AI_MESSAGES = [
    "I have had a mild headache since morning, what could help?",
    "my knees ache after walking, is that normal?",
    "I feel tired most afternoons even after sleeping well, why might that be?",
    "should I be worried about a sore throat that started yesterday?",
    "my back feels stiff when I wake up, any ideas?",
]
LOG_MESSAGE = "Slept 7 hours, drank 1.5 L of water and walked 5,000 steps."


def build(rtt_ms: float, ai_ms: float):
    import fake_db
    from fake_db import FakeDB

    db = FakeDB({"bench": USER})
    import supabase_client
    supabase_client.supabase = db
    import main
    import rag
    from bubbles_ai import BubblesAIResponse
    import consent

    rtt = rtt_ms / 1000.0
    original = fake_db.Query.execute

    def slow_execute(self):
        time.sleep(rtt)
        return original(self)

    fake_db.Query.execute = slow_execute
    # the embedding request is one more HTTP round trip (it returns None: lexical-only, as when the function is cold)
    rag.embed_text = lambda *_a, **_k: (time.sleep(rtt), None)[1]

    def stub_ai(message, **_kw):
        time.sleep(ai_ms / 1000.0)
        return BubblesAIResponse(response="Thanks for sharing. Rest and water often help. How are you feeling now?",
                                 sentiment="neutral", health_events=[])

    main.ask_bubbles = stub_ai
    fake_db.Query.execute = original   # consent write without the artificial latency
    consent.set_ai_chat(db, USER, True)
    fake_db.Query.execute = slow_execute
    from fastapi.testclient import TestClient
    return TestClient(main.app, raise_server_exceptions=False), db


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def run(client, messages: list[str], n: int, path: str = "/chat") -> list[float]:
    headers = {"Authorization": "Bearer bench"}
    conv = None
    out: list[float] = []
    for i in range(n):
        body = {"message": messages[i % len(messages)] + (f" ({i})" if i >= len(messages) else "")}
        if conv:
            body["conversation_id"] = conv
        started = time.perf_counter()
        if path.endswith("/stream"):
            with client.stream("POST", path, json=body, headers=headers) as res:
                assert res.status_code == 200, res.status_code
                text = "".join(res.iter_text())
            assert "event: done" in text, text[:300]
        else:
            res = client.post(path, json=body, headers=headers)
            assert res.status_code == 200, res.text[:300]
            conv = res.json().get("conversation_id") or conv
        out.append((time.perf_counter() - started) * 1000)
    return out


def main_cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--rtt-ms", type=float, default=80.0)
    ap.add_argument("--ai-ms", type=float, default=0.0)
    ap.add_argument("--path", default="/chat")
    args = ap.parse_args()
    client, _db = build(args.rtt_ms, args.ai_ms)
    run(client, AI_MESSAGES, 3, args.path)   # warm-up: the first turn pays one-off start-up work
    for label, messages in (("ai route", AI_MESSAGES), ("daily log", [LOG_MESSAGE])):
        times = run(client, messages, args.n, args.path)
        print(f"{args.path} {label:10s} n={len(times)} rtt={args.rtt_ms:g}ms ai={args.ai_ms:g}ms  "
              f"p50={statistics.median(times):7.1f} ms  p95={pct(times, 0.95):7.1f} ms  min={min(times):7.1f} ms", flush=True)


if __name__ == "__main__":
    main_cli()
