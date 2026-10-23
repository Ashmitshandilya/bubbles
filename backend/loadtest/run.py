"""Closed-loop load test with httpx (Locust is not installed and adds a dependency). Each virtual user loops over the scenario with a
short think time. Only talks to a local server; refuses any other host.

    python loadtest/server.py                       # terminal 1
    python loadtest/run.py --users 1 10 50 --seconds 30
    python loadtest/run.py --smoke                  # about 10 s, for CI
"""
import argparse
import asyncio
import statistics
import time
from urllib.parse import urlparse

import httpx

H = {"Authorization": "Bearer preview"}
SCENARIO = [
    ("GET", "/health", None),
    ("POST", "/chat", {"message": "what are some good ideas for a calm evening routine"}),   # AI stub
    ("POST", "/chat", {"message": "hi"}),                                       # deterministic route
    ("GET", "/organs/map", None),
    ("POST", "/companion/daily", {"days": 7}),
    ("POST", "/intelligence/state", {"days": 30}),
    ("POST", "/patterns/analyze", {"days": 30}),
    ("GET", "/today?days=14", None),                                          # the one call Today makes
]


async def user(client, stop, samples, think):
    while time.monotonic() < stop:
        for method, path, body in SCENARIO:
            t = time.perf_counter()
            try:
                r = await client.request(method, path, json=body, headers=H)
                ok = r.status_code < 400
            except httpx.HTTPError:
                ok = False
            samples.append((f"{method} {path}", (time.perf_counter() - t) * 1000, ok))
            await asyncio.sleep(think)


def pct(values, q):
    return statistics.quantiles(values, n=100)[q - 1] if len(values) > 1 else (values[0] if values else 0)


async def level(base, users, seconds, think):
    samples = []
    async with httpx.AsyncClient(base_url=base, timeout=60, limits=httpx.Limits(max_connections=users + 5)) as client:
        stop = time.monotonic() + seconds
        await asyncio.gather(*(user(client, stop, samples, think) for _ in range(users)))
    ms = [s[1] for s in samples]
    errors = sum(1 for s in samples if not s[2])
    print(f"users={users} requests={len(samples)} rps={len(samples) / seconds:.1f} p50={pct(ms, 50):.0f}ms p95={pct(ms, 95):.0f}ms errors={100 * errors / max(1, len(samples)):.1f}%")
    for name in dict.fromkeys(s[0] for s in samples):
        m = [s[1] for s in samples if s[0] == name]
        print(f"   {name:28} n={len(m):5} p50={pct(m, 50):6.0f}ms p95={pct(m, 95):6.0f}ms")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--users", type=int, nargs="+", default=[1, 10, 50])
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--think", type=float, default=0.2)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if urlparse(a.base).hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("Load tests only run against a local server.")
    if a.smoke:
        a.users, a.seconds = [5], 8
    errors = sum(asyncio.run(level(a.base, u, a.seconds, a.think)) for u in a.users)
    raise SystemExit(1 if a.smoke and errors else 0)


if __name__ == "__main__":
    main()
