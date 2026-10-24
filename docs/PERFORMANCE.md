# Performance (renovation plan 11.7), measured 2026-10-24

What was measured, how, and what is left. Numbers come from the preview server with a fake in-memory database (see `docs/LOAD_TEST.md`), so they
show the app-side cost only; production adds Supabase round trips, which the parallel reads are there to hide.

## Targets and results

| Target | Result | Status |
|---|---|---|
| Today: API calls on load | 3 of its own (`/today`, `/health/summary`, `/onboarding/tour`); the browser log shows 8 in total because the app shell adds 5 (`/health` twice, `/onboarding/state`, `/experience`, `/notifications`). Before: about 12 of Today's own | met |
| `/today` p95, one user, warm | 135 to 140 ms (target 400 ms) | met |
| `/today` under load | p50 315 ms and p95 606 ms at 10 users; p50 3.5 s at 50 users (one Python process, CPU-bound) | see below |
| Route JS per page (gzip) | shared 103 kB; signed-in pages 205 to 247 kB first load (target 180 kB) | **not met** |
| Chat: first visible words p50 with true streaming | not built (see below) | **not done** |
| Deterministic chat replies p95 | not re-measured this round | open |
| Lighthouse LCP on a mid phone over 4G | not run | open |
| Refetch guard (`npm run e2e:refetch`) | not re-run after the Today rewrite | open |
| Load test vs `docs/LOAD_TEST.md` (94 req/s, p95 847 ms at 50 users) | with `/today` added to the mix: 47 to 50 req/s and p95 3.7 s at 50 users | **changed**: the mix is heavier now, see below |

## What changed in this pass

- `GET /today` reads the trackers, the brief, the week, the living map, nutrient nudges, the profile and Orbit side by side. The health events
  that the brief, the week and the living map all need are now read once per request (`main._EVENT_MEMO`), and shorter windows are cut from the
  longer read using the recording time, which is the field the database filtered on.
- Folds on Today and the tracker pages mount their content only when opened, so a closed fold starts no requests (this removed three requests
  from Today: fitness summary, cycle overview and partner sharing).

## Why the load numbers moved

The old scenario had no `/today`. Adding it (the one call that replaces about twelve) makes the mix much heavier per virtual user, because
`/today` runs about fifteen reads and three analyses in one request. Throughput at 50 users therefore fell from about 94 to about 50 requests a
second and the tail grew. That is the same work the browser used to ask for as twelve separate calls, now in one; it is not extra work. A real
person opens Today a few times a day, not every 0.2 seconds, so the 10-user row (p95 606 ms with a fake database that has no network time) is the
realistic one. If production latency for Today is too high, the next steps in order are:

1. A per-user cache of the bundle for 20 to 60 seconds, emptied by any write from that person (the plan's 11.1; not built because every write
   route would need to empty it, and a stale Today right after logging water is worse than a slow one).
2. Let the brief and the living map share one health-state computation (they each build it from the same events).
3. A second worker, which needs a paid plan and would break the in-memory caches (`docs/LOAD_TEST.md`).

## Bundle size

Every signed-in page carries React, Next's runtime and the Supabase auth client (about 51 kB gzip for `@supabase/supabase-js`). That puts every
page near 205 kB first load. Getting under 180 kB would mean replacing `supabase-js` with a small hand-written auth client, which touches sign-in,
the two-step check and token refresh: a project of its own, not a tuning pass. The 3D landing and body map chunks are loaded only on their pages.

## True streaming (plan 5.5, WP9.1): not built, on purpose

Every provider call in `ai_provider.py` is a plain request and response; none of them streams. Real streaming would mean adding streaming to each
provider (Gemini plus the OpenAI-compatible pool), changing the model's output contract (text first, then an `<<<EVENTS>>>` line), and running
the dose scrubber, attribution strip and lints on each finished sentence, with a property test against recorded replies and a manual check on live
providers. None of that can be verified without live keys and recorded replies, and half-built streaming risks unguarded text reaching a person.
`/chat/stream` therefore still waits for the whole reply and sends it sentence by sentence, with every guard applied first.

## Smoothness pass (2026-10-24, branch `perf/smoothness`)

Done:

- [x] **Revisiting a page shows it at once.** Today keeps its last good answer in memory only (never on disk, dropped the moment nobody is signed in) and refreshes quietly behind it; every page that uses the shared query hook does the same, keyed by person and request. Measured in the browser: coming back to Today after 25 s shows it in about 160 ms with no skeletons (before, a skeleton screen until `/today` answered).
- [x] **One `/health` probe on load, not two.** The probe re-ran when the sign-in session arrived a moment after the page opened; a probe that answered in the last 30 s is not repeated.
- [x] **No tour question on every visit to Today.** `/onboarding/tour` is asked once per tab.
- [x] **Today's first load is lighter.** The Patterns, Living map, Whole health, Partner, Nutrient and Week folds are loaded when opened (`/dashboard` first-load JS 247 kB to 236 kB).
- [x] **`/today` does less work.** The health events and the health state that the brief, the week and the living map share are built once per request (single user 97 ms to 75 ms; checked by tests that each part still equals its own route's answer).
- [x] **Android launch asks for less.** Today seeds the tracker entries it already received in `/today` into the shared repository instead of loading every tracker and record (about 15 requests fewer at launch); the Track screen loads only what is still missing (`Repo.loadMissing`).

Not done (needs the owner's data or a bigger change): the per-user server cache of the bundle, a smaller auth client (bundle size), true streaming, Lighthouse on a real phone.
