# Admin portal, AI observability and caching: Phase 0 findings and design

Branch `admin-portal-2026-10-13`, cut from `origin/main` at `502f5f1` on 2026-10-13.

**Status:** reviewed 2026-10-13. Sir Noah: ACCEPT WITH CONDITIONS (15 testable conditions, implemented and tested in `backend/tests/test_admin_portal.py`). Lixie: UI direction (one route with tabs, light dedicated header, denied view = the normal not-found page). Changes from this draft after review: the admin gate moved into the middleware (before routing) so wrong methods and malformed bodies cannot reveal a route; bad tokens on /admin still count toward the bad-token limit; refusal audit sampled to one row a minute; aal2 required; the admin's id is kept on audit rows; `/admin/requests/{id}` and the refresh setting were cut (the `request_id` filter and a fixed 5 s cover them); p99 kept only where the sample allows; the migration uses plain `create table` in one transaction with sequence revokes and a verification query. The built system is documented in `README.md`; this file stays as the Phase 0 record.

Guiding rule: **observe the system, not the user.** (One named exception, decided by the owner: the live view shows the account id of a request, from memory only; see README, "The one named exception".) Nothing in this design stores or shows a message, prompt, reply, symptom, medication, cycle detail, note or user id.

## 1. What already exists (discovery)

| Area | What is there today | Gap |
|---|---|---|
| Admin identity | `request_guard.admin_ids()` / `require_admin()` read `BUBBLES_ADMIN_USER_IDS` (comma separated user ids, empty = nobody). Used by 4 routes: `/ai/telemetry`, `/production/readiness`, `/models/registry`, `/privacy/security-baseline` (403 for non-admins). | No admin UI; 403 reveals the route exists. |
| Sign-in check | `main.get_authenticated_user()` calls `supabase.auth.get_user(token)` on **every** request (one network round trip each), and enforces two-step sign-in server side. | Not cached. |
| AI telemetry | `ai_telemetry.py`: in-process ring of the last 200 provider calls (provider, model, latency, outcome, tokens, error class) + counters. Fed from `ai_provider.call_fallback` (success and error) and `bubbles_ai._call_gemini` (**success only**). | Gemini failures and timeouts are invisible; no request id, no attempt position, no "which provider gave the final answer", no degraded count, nothing persisted, lost on every restart. |
| Request logging | `logging_util` structured, scrubbed JSON logs; unhandled exceptions get an 8-char `request_id` in the 500 body. uvicorn access log is redacted (`request_guard.AccessLogRedactor`). | No per-route latency/status metrics. |
| Chat path | `main.chat`: sign-in, rate limit, `sync_profile_from_auth` (a `profiles` read on every message for named users), consent read (`has_ai_consent`, a `health_events` read), safety triage (`analyze_turn`), deterministic routes never call a model, else context + RAG + `ask_bubbles` (one 50 s budget: Gemini, then Groq, NVIDIA, Mistral). | Route/safety/AI-called outcome is only in a log line. |
| Provider order | `bubbles_ai._ask_bubbles` (Gemini first) then `ai_provider.provider_pool(health_data=True)` = `AUTHENTICATED_PROVIDERS` (Groq, NVIDIA, Mistral). Keyless pool is off for health data. | Order lives in code; will be read from there, not hard-coded in the UI. |
| Backend caches | `/health` database probe (30 s), `association_loader` (30 min per user). | No shared cache abstraction or stats. |
| Frontend cache | `app/lib/api-cache.ts`: 20 s per-tab read cache with in-flight de-duplication, one owner at a time, cleared on any write and on sign-out; `/health`, `/chat`, `/me/consent` never cached. | Already covers request coalescing in the browser. Admin reads must bypass it (always fresh). |
| Database | 14 migrations; the live database has drifted (SECURITY_STATUS item 6). Every table has RLS; anon has no access. No telemetry or audit table. | Persistent logs need one new table (owner applies the SQL). |
| Hosting | One Render free instance (in-memory limiters), Vercel site proxying `/bubbles-api/*`. Render exposes `RENDER_GIT_COMMIT`. | Live view must be cheap: polling, no new infrastructure. |

## 2. Proposed design

### 2.1 Admin authorization (server is the boundary)

- Reuse Supabase Auth + `get_authenticated_user` (two-step sign-in still enforced) + `BUBBLES_ADMIN_USER_IDS`. No second auth system, no client-side role flag.
- New router `admin_api.py` mounted at `/admin/*` (API side). One dependency on every route: valid token AND id on the allow-list, otherwise a uniform **404 `{"detail":"Not Found"}`** (no token, bad token, ordinary user and unknown admin path all look identical, so the routes' existence is not revealed). Each refusal with a token is recorded as an `admin_denied` audit event (no token, no address stored).
- The 4 existing operational routes keep their current 403 behaviour (no regression for existing tests/clients).
- Bearer header only, no cookies, so CSRF does not apply (same as the rest of the API). Every admin list is bounded (range max 30 days, page size max 200) and filters are whitelisted values, not free SQL.
- Website: `/admin` page asks `GET /admin/me`; anything but 200 renders the ordinary "page not found" view. Hidden from search (`noindex`, already blocked by robots). This is UX only.

### 2.2 Telemetry (metadata only, never blocks a reply)

One module `ops_telemetry.py` (keeps the `ai_telemetry.record/snapshot` API working):

- **Request id**: the security-header middleware sets a 12-hex `request_id` ContextVar and returns `X-Request-Id`. Sync routes run in the thread pool with a copy of the context, so AI attempts inside a request carry its id.
- **Event kinds** (one shape, stored in one table):
  - `api`: method, route template (e.g. `/chat`, `/memory/{id}` style, never the raw URL), status, latency_ms. Chat adds `route_kind` (e.g. `ai`, `emergency`, `small_talk`), `safety_level` (GREEN/AMBER/RED) and `ai_called` (bool). OPTIONS skipped.
  - `ai_attempt`: provider, model, position in chain (1 = Gemini), outcome (`success`, `error`, `timeout`, `budget_spent`, `invalid_json`), error category, latency_ms, token counts.
  - `ai_reply`: final provider/model or `degraded`, attempts, fallback_used, total_ms.
  - `error`: category (auth, validation, database, network, ai_provider, timeout, rate_limit, rag, cache, internal), component, route, safe error class name.
  - `audit`: admin action, target, old/new value (settings only, never secrets), outcome.
- **Never stored**: user id (not even hashed: no admin view needs it), message, prompt, reply, context, query text, tokens, keys, IPs.
- **Path**: `record()` appends to an in-memory ring (5,000 events, feeds the live view) and to a bounded write queue (2,000; oldest dropped and counted). A daemon thread inserts the queue every 10 s in one batch. Any failure is swallowed and counted; the request never waits on it. If the table does not exist the module runs in **memory-only mode** and the portal says so.
- **Retention**: the flusher deletes `api`/`ai_*`/`error` rows older than `telemetry_retention_days` (default 14) and `audit` rows older than 365 days, at most once an hour.

### 2.3 Storage (one additive migration, owner applies)

`supabase/migrations/20261013_bubbles_ops.sql`:

- `public.bubbles_ops_events` (id bigint identity, at timestamptz, kind text, request_id text, data jsonb) + indexes on `(at desc)`, `(kind, at desc)`, `(request_id)`.
- `public.bubbles_admin_settings` (key text primary key, value jsonb, updated_at, updated_by).
- RLS **enabled with no policies** on both; `revoke all` from `anon, authenticated`; `grant` to `service_role` only. Normal users cannot read or write either table through the database API.

### 2.4 Admin API (all behind the admin dependency)

| Route | Returns |
|---|---|
| `GET /admin/me` | `{admin: true}` plus environment, commit, process start time. |
| `GET /admin/overview?range=` | system (health probe, version, commit, uptime, persistence mode), AI totals (requests, success, failed, fallback, degraded, safety-gated, p50/p95/p99), API totals (req/min, error rate, 4xx/5xx), cache stats. |
| `GET /admin/ai?range=` | per provider+model table (requests, success rate, timeout rate, first-choice rate, fallback position, final-answer share, latency avg/p50/p95/p99, error categories, last success/failure), the configured chain read from code with transition counts, and four highlights (most answers, most failing, slowest, most reliable). Highlights need a minimum sample (10) or say "not enough data". |
| `GET /admin/api?range=` | per route: requests, success rate, 4xx, 5xx, avg/p50/p95, slowest, last error. |
| `GET /admin/events?kind=&provider=&status=&route=&request_id=&range=&limit=&before=` | log explorer, newest first, cursor pagination. |
| `GET /admin/events/live?after=` | events newer than a cursor from the in-memory ring (polled every 5 s while the tab is visible). |
| `GET /admin/requests/{request_id}` | every event of one request (timeline: api, attempts, reply). |
| `GET/PUT /admin/settings` | safe settings only (below); every change audited. |
| `GET /admin/audit?range=` | audit events. |
| `POST /admin/cache/clear` | clears server caches; audited. |

Ranges: `15m, 1h, 6h, 24h, 7d, 30d` (default 1h). Aggregation is server side over at most 20,000 rows of the range (`ponytail:` marked; an SQL function is the upgrade path), and the response says when it was capped. Labels returned with every block: `live` (memory ring), `aggregated` (range), `historical` (stored rows).

### 2.5 Safe settings (allow-list, nothing else is editable)

| Key | Range | Effect |
|---|---|---|
| `telemetry_retention_days` | 1 to 90 | prune age |
| `live_refresh_seconds` | 3 to 60 | portal polling |
| `provider_paused.<Name>` | bool, names from the code's chain only | skip a provider in the chain (the free allow-list and $0 policy are untouched; pausing every provider gives the existing degraded reply) |
| `cache_enabled.<name>` | bool | turn a server cache off |

Not editable from the portal: secrets, safety rules, clinical constants, auth providers, RLS, DNS, billing, model allow-lists, paid/keyless flags.

### 2.6 Caching (measure first; small, explicit, safe)

New `ttl_cache.py`: `TTLCache(name, ttl, max_entries)` with `get_or_compute` (single-flight per key: concurrent identical misses share one computation), `invalidate(key)`, `clear()`, stats (hits, misses, errors, invalidations, avg miss ms, estimated ms saved). A cache error falls back to the normal computation. Registry for the portal. Backend is a plain in-process dict; the class is the extension point if Redis is ever justified.

Proposed first targets (each user-scoped, keyed by user id, invalidated on the user's own write):

1. **Sign-in verification** (largest win: one Supabase Auth round trip on every API call). Key = SHA-256 of the token, TTL 30 s, max 2,000. Trade-off: a signed-out token keeps working for up to 30 s. **Needs Sir Noah's decision.**
2. **AI consent** (`has_ai_consent`, one read per chat message): TTL 5 min, invalidated by `set_ai_chat` for that user.
3. **Profile name sync** (`sync_profile_from_auth`, one read per chat message): remember per user that the name is already stored, TTL 1 h.

Not cached: chat replies, health content, anything shared across users. The browser read cache stays as is; `/admin` is added to its never-cached list.

Measurement: the new `api` events give per-route latency in production; baseline is taken from them before turning caches on (each cache has an off switch in settings), then compared.

### 2.7 Website `/admin`

One route, client-rendered, tabs instead of many pages (Overview, AI and providers, Live, API, Logs, Settings and audit). No chart library: SVG/CSS bars from the existing tokens. Logic in `app/admin/*.ts` with Vitest tests; components thin. Visual direction from Lixie.

### 2.8 Out of scope (YAGNI, free tier)

Redis, Prometheus/Grafana, Kafka, Elasticsearch, WebSockets/SSE (the Live page polls a cursor every 3 s instead; SSE on the Render free plan was not verified), dynamic provider scoring, a second auth system.

## 3. Risks

1. Migration must be applied by the owner in the Supabase SQL editor; until then telemetry is memory-only (lost on restart).
2. Render free plan restarts wipe the live ring; persisted rows survive.
3. Sign-in cache (2.6 item 1) shortens nothing about token expiry but delays sign-out by up to 30 s.
4. Telemetry inserts add write load (batched, about 1 insert per 10 s).
5. `route_kind`/`safety_level` without a user id reveal only that some anonymous request was an emergency; reviewers to confirm this is acceptable.
