# Load test

Script: `backend/loadtest/run.py` (asyncio + httpx; Locust is not installed and k6 is not needed). Server: `backend/loadtest/server.py`
(the preview server: fake in-memory database, demo person, AI providers replaced by a 50 ms stub, provider keys removed, rate limits lifted
because one demo person plays every virtual user). The runner refuses any host except localhost, so it cannot hit production or a real provider.

    cd backend
    BUBBLES_PREVIEW=1 python loadtest/server.py          # terminal 1, port 8001
    python loadtest/run.py --users 1 10 50 --seconds 30  # terminal 2
    python loadtest/run.py --smoke                       # about 10 s, exits 1 on any error (server must be running)

Each virtual user loops: GET /health, POST /chat (stubbed AI), POST /chat (short message), GET /organs/map, POST /companion/daily,
POST /intelligence/state, POST /patterns/analyze, with 0.2 s think time between requests.

## Result (16-core Windows laptop, one uvicorn process, 30 s per level, fake DB so there is no network latency to Supabase)

| Users | Requests/s | p50 | p95 | Errors |
|---|---|---|---|---|
| 1 | 4.7 | 16 ms | 25 ms | 0 % |
| 10 | 42 | 27 ms | 96 ms | 0 % |
| 50 | 94 | 319 ms | 847 ms | 0 % |

Slowest at 50 users (p50 / p95): /organs/map 627 / 1235 ms, /health 366 / 912 ms, /companion/daily 331 / 637 ms.

## Conclusions

- Throughput stops scaling between 10 and 50 users (42 to 94 requests/s while users grew 5x): the first saturation point is about 90 to 100
  requests/s on a single process, where even /health slows to 366 ms because every request shares one Python process.
- No errors at any level. Latency at 10 users is fine; the knee is between 10 and 50.
- The numbers exclude Supabase round trips and real AI latency, so production is slower per request; this shows the app-side ceiling only.
- /organs/map is the heaviest read; its five independent reads now run side by side (see the entry in DECISIONS.md).
- Procfile and DEPLOY.md run a single uvicorn worker (Render free plan, 0.1 CPU). A second worker needs a paid plan and would break
  the in-memory caches and rate limiters (per process), so it was left alone.

## Sequential database calls found

- Today: the screen issues about 12 independent GETs from the browser, already in parallel; the shared 20 s cache (app/lib/api-cache.ts) stops
  repeat reads on navigation and is emptied after every write.
- /organs/map: events, labs, conditions, cycle context and the setup document were five sequential reads; now parallel.
- /companion/daily, /intelligence/*, /patterns/analyze: one events read, then pure computation. Nothing to parallelise.
- /intelligence/all: one events read plus build_user_context; left as is.
