# Bubbles admin portal

`https://heybubbles.in/admin`: an operations console for the people listed in `BUBBLES_ADMIN_USER_IDS`. It shows whether Bubbles is healthy, which AI provider and model is actually answering, how often the chain falls back, how each API route performs, live and stored technical logs, and a small set of safe settings with an audit trail.

**Rule: observe the system, not the user.** No message, prompt, reply, symptom, medication, cycle detail, note, user id, token or address is recorded or shown. Phase 0 findings and the reviewed design are in `DESIGN.md`.

## Turning it on (owner, one time)

1. **Two-step sign-in.** Sign in at heybubbles.in, open Settings, then Account, and turn on the authenticator app. The portal only opens for a session that passed the authenticator step (`aal2`).
2. **Your user id.** In Supabase, go to Authentication, then Users, and copy your id.
3. **Render.** Add the environment variable `BUBBLES_ADMIN_USER_IDS=<your id>` (comma-separate several). With it empty, nobody is an admin.
4. **Database (recommended).** Run `supabase/migrations/20261013_bubbles_ops.sql` once in the Supabase SQL editor, then run the three verification queries at the bottom of the file. Until then telemetry lives in memory only (lost on every restart) and the portal says so. Undo: `supabase/undo/20261013_bubbles_ops_undo.sql`.
5. Open `https://heybubbles.in/admin` while signed in. Anyone else, including a signed-out visitor, sees the normal "We couldn't find that page".

## How it fits together

```
Browser /admin (app/admin)          same-origin /bubbles-api/admin/*        FastAPI
  GET /admin/me  ───────────────────────────────────────────────────────▶  middleware: _admin_gate (fresh sign-in, aal2, allow-list)
  tabs poll /admin/overview, /ai, /api, /events, /events/live, /settings      │ anything else: byte-identical 404 before routing
                                                                             ▼
                                                                         admin_api.py (router, include_in_schema=False, second lock)
                                                                             │ reads
every request ─▶ middleware ─▶ ops_telemetry.record("api")                   ▼
chat          ─▶ ops_telemetry.note(route_kind, safety_level, ai_called)  ops_telemetry: ring (5,000) ─▶ queue (2,000) ─▶ flusher (10 s)
AI attempts   ─▶ ai_telemetry.record ─▶ ops "ai_attempt"                                                   ─▶ bubbles_ops_events
final answer  ─▶ bubbles_ai._record_reply ─▶ ops "ai_reply"               ops_metrics: pure aggregation (tested)
logger.error  ─▶ ops "error"                                              admin_settings: safe settings ─▶ bubbles_admin_settings
```

| File | Role |
|---|---|
| `backend/ops_telemetry.py` | Request id and note (ContextVars), whitelisted event fields, in-memory ring, bounded write queue, daemon flusher, retention pruning, reads with paging and a 20,000-row cap. Never raises. |
| `backend/ops_metrics.py` | Pure functions: AI summary, provider/model table, highlights (minimum sample 10), fallback flow, API route table with trend, headline status. |
| `backend/admin_api.py` | `/admin/*` routes. |
| `backend/admin_settings.py` | Allow-listed settings in memory, written through to the database, every change audited. |
| `backend/ttl_cache.py` | In-process cache with a time limit, shared misses, invalidation, stats and an off switch. |
| `backend/main.py` | `_admin_gate`, `_record_api_event`, sign-in cache, chat notes, profile-sync cache. |
| `backend/ai_telemetry.py`, `ai_provider.py`, `bubbles_ai.py` | Attempt positions and error categories, provider pause after the policy gate, final answer recorded only after validation. |
| `frontend/app/admin/*` | The console (`AdminClient.tsx` shell, `panels.tsx` tabs, `kit.tsx` shared pieces, `format.ts` wording with tests). |
| `supabase/migrations/20261013_bubbles_ops.sql` | The two tables, RLS on with no policies, nothing granted to anon or authenticated. |

## Authorization

- **Identity:** Supabase Auth through `get_authenticated_user(..., fresh=True)`. The sign-in cache is never used for admin requests.
- **Two-step:** the token's `aal` claim must be `aal2` (read after Supabase verified the token).
- **Allow-list:** `BUBBLES_ADMIN_USER_IDS` (exact id match). Empty means nobody.
- **Where it runs:** in the HTTP middleware, **before routing**. Any refusal (no token, bad token, ordinary user, password-only session, wrong method, malformed body, unknown admin path) gets exactly the same bytes as a path that does not exist: `404 {"detail":"Not Found"}`.
- **Brute force:** a bad token on `/admin/*` still counts toward the per-address bad-token limit (`_auth_fail_limiter`).
- **Refusal audit:** counted, and at most one `admin_denied` row a minute (the reason only: no token, address or id).
- **Second lock:** the router dependency `admin_api._admin` refuses with 404 when the gate did not mark the request.
- **No cookies:** Bearer header only, so CSRF does not apply. The routes are not in the OpenAPI schema. The website never caches `/admin` reads (`app/lib/api-cache.ts`).
- **The four older operational routes** (`/ai/telemetry`, `/production/readiness`, `/models/registry`, `/privacy/security-baseline`) keep their 403 for non-admins.

**What is public on purpose:** the website route `/admin` exists for everyone (it answers 200 with the loading screen, then shows "We couldn't find that page" to a non-admin), and the console's code ships in the website bundle and the Android app. That reveals nothing about data: every number and every action is behind the API gate above. With `BUBBLES_ADMIN_USER_IDS` empty the gate refuses before any sign-in call.

## Telemetry events

One table, `bubbles_ops_events(id, at, kind, request_id, data jsonb)`. `data` may only hold these keys (anything else is dropped in `record()`):

| kind | fields |
|---|---|
| `api` | method, route (template such as `/partner/{token}`, or `unmatched`; never the raw path or query), status, latency_ms; chat adds route_kind, safety_level, ai_called (fixed value lists only) and the numbers `stage_pre_ms`, `stage_ctx_ms`, `stage_rag_ms`, `stage_ai_ms`, `stage_post_ms` (see below) |
| `ai_attempt` | provider, model, position (1 = first tried), outcome (`success`, `error`, `timeout`, `budget_spent`, `invalid_json`), error_category, latency_ms, token counts (`input_tokens`, `output_tokens`, `total_tokens`, `cached_tokens`) |
| `ai_reply` | outcome (`answered` or `degraded`), provider, model, attempts, fallback_used, total_ms. Written only after the answer passed validation. |
| `error` | category (auth, authorization, validation, rate_limit, database, rag, ai_provider, timeout, network, cache, internal), component, route, error_class, severity. Never the message. |
| `audit` | action, target, old, new, outcome, actor (the administrator's id; operators are not health-data subjects) |
| `funnel` | step: one of a fixed list (`about`, `goals`, `health`, `life`, `daily`, `mind`, `people`, `drains`, `talk`, `completed`, `under_18`). A count of people reaching a first-run setup step, never an answer. Needs `20261016_bubbles_ops_funnel.sql`; until then it stays in memory. |
| `client` | code: one of a fixed list (`render_error`, `unhandled_rejection`, `chunk_load_failed`, `api_unreachable`, `sign_in_refresh_failed`, `stream_fallback`), sent by the website or app to `POST /telemetry/client`. Same migration. |

The portal's own `/admin/*` requests are not recorded as traffic. Retention: technical events `telemetry_retention_days` (default 14, settable 1 to 90), funnel rows 90 days, audit rows 365 days, pruned at most hourly.

**Where a chat turn spends its time.** The five `stage_*_ms` numbers on a `/chat` event (numbers only, from a fixed list of names, each 0 to 600,000; text is refused): `pre` = sign-in checks to the safety gate (conversation, saving the message, understanding it), `ctx` = reading the person's own context, `rag` = the evidence lookup, `ai` = waiting for the model, `post` = checking and saving the reply. `ctx` and `rag` run side by side, so their sum can be more than the request's own time. The AI summary (`/admin/ai`, `/admin/overview`) carries p50 and p95 per stage as `stage_ms`. `/chat/stream` events carry only `stage_pre_ms` (the stream's event is written when the stream opens). Cost is never stored in an event; see Cost below.

**Request id:** every response carries `X-Request-Id` (8 hex). The same id appears on the request's events and on log lines, so a user-reported failure can be traced in Logs without any content.

## How Bubbles answers

1. **Safety first, no model.** The safety engine reads the message before anything else. Emergencies, corrections, clarifications, daily logs, fitness, small talk and follow-ups to a safety reply are answered with fixed or rule-built text and never call a model.
2. **Otherwise, with the person's yes to outside AI** (Settings), the reply is written by the first model that answers: **Gemini** (`gemini-3-flash-preview`, minimal thinking, 900 output tokens, 9 s per call), then **Groq** (`openai/gpt-oss-20b`), **NVIDIA** (`nvidia/nemotron-3.5-lightning-30b-a3b`), **Mistral** (`ministral-14b-latest`). One 50 s budget covers the whole chain and one retry on 429, 5xx or timeout. The keyless pool is off and paid AI is off.
3. **If nobody answers** the person gets the fixed calm fallback and what Bubbles understood is still saved.
4. **After the model:** the reply is checked (no doses, no source names, no verdicts, urgent replies keep their call to act today) before it is saved and shown.
5. **Allowlist asymmetry:** Groq, NVIDIA and Mistral models must be on `FREE_MODEL_ALLOWLIST`; the Gemini model is read from `GEMINI_MODEL` and is not checked. Use a free-tier key.

## Cost, usage and people (`GET /admin/usage`)

Everything here is counts and rates, worked out when the page is read. **Cost** = tokens x the published price, per provider and model: while paid AI is off every model shows `$0, free tier` (with `if_paid_usd`, what the same tokens would cost at the published price where one is known); a model with no name or no price row shows `unknown`, never free. **Usage** = safety tiers per day (GREEN, AMBER, RED), the mix of reply kinds, the share answered by a model versus fixed text, how often a consent question was needed, fallback, degraded and timeout rates, which routes are used (successful calls only), the first-run funnel, and the app-problem codes. **People** = distinct people who sent a message in the last 1, 7 and 30 days and new profiles in the last 7 and 30 days, as integers only (`ops_usage.py`; reads at most 20,000 message rows and says `capped`).

## "Who is actually answering?"

- **Answered share** comes from `ai_reply` events (validated answers only). Attempts that returned unusable JSON are recorded as `invalid_json`, not as answers.
- **First-choice rate** is the share of a provider's attempts made at position 1.
- **Fallback flow** follows the order read from the code: Gemini, then `ai_provider.AUTHENTICATED_PROVIDERS` (Groq, NVIDIA, Mistral). For each step it counts how many replies reached it, were answered there, or were passed on, plus how many ran out (the calm fallback message).
- **Highlights** (gives most answers, most reliable, slowest by p95, fails most) need at least 10 calls. Below that they say "Not enough data yet".

## Safe settings

| Key | Values | Effect |
|---|---|---|
| `provider_paused.<Gemini, Groq, NVIDIA, Mistral>` | true/false | Skips that provider. Applied after the policy gate, so it can only remove a provider, never add, reorder or reach the keyless pool. Read from memory on the chat path; if unreadable, nothing is paused. All paused = the existing calm fallback message, and the portal shows an urgent note. |
| `cache_enabled.<sign_in, consent, profile_sync, embedding, rag_policy, style_block, profile_context>` | true/false | Turns a server cache off (and empties it). |
| `telemetry_retention_days` | 1 to 90 | Prune age for technical events. |

Anything else is refused with 422 and the refusal is audited. Not editable from the portal: secrets, safety rules, clinical constants, sign-in providers, RLS, DNS, billing, model allow-lists, the paid and keyless switches. Settings live in one process (DEPLOY.md: one Render instance).

## Caching

| Cache | Key | Lifetime | Invalidated by | Why it is safe |
|---|---|---|---|---|
| `sign_in` | SHA-256 of the token | 30 s, never past the token's own expiry | expiry; Clear caches; turning it off | Successes only; the two-step check ran before storing; `/admin` always checks fresh. Accepted trade-off: a token signed out elsewhere keeps working for up to 30 s. |
| `consent` | (user id, consent version) | 5 min | `consent.set_ai_chat` (before and after the write), `doc_store.delete_everything` | Read errors are never stored, and an unreadable answer means "no". A withdrawal applies to the very next message. |
| `profile_sync` | user id | 1 h | expiry | Holds only "this person's name is already stored". |

The chat path adds four more: `embedding` (the meaning-search numbers for a recent question; keyed by a hash of the normalised question, no user id, 1 h, a failed call is never stored), `rag_policy` (each reading page's handling rule, global, 1 h, cleared when a document is ingested), `style_block` (a person's tone settings, 2 min, cleared when the first-run setup or the name is saved, an empty answer is never stored) and `profile_context` (profile and preferences read for replies, 1 min, same invalidation). Memory items and health events are deliberately not cached: a detail saved a second ago is in the next reply.

Every cache is per user or holds no user data, lives in process memory only, and falls back to the normal lookup on any internal error. Concurrent identical misses share one lookup. Stats (hit rate, misses, how long a miss takes) appear under Overview, then Errors and caches. The browser keeps its existing 20-second per-user read cache (`app/lib/api-cache.ts`), which already de-duplicates identical reads in flight. Admin reads bypass it.

There is no account-deletion route today. If one is added it must call `ttl_cache.clear_all()`.

## Endpoints

All routes are under `/admin`, admin only, and absent from the schema. Ranges are `15m, 1h, 6h, 24h, 7d, 30d`. Lists are paged (at most 200) and report `capped` when the 20,000-row read cap was hit.

| Route | Purpose |
|---|---|
| `GET /me` | environment, commit, start time, storage mode, chain order with pause and key flags, refresh interval |
| `GET /overview?range=` | headline (`ok`, `warn` or `fail` plus plain reasons), a 5-minute `now` block, system components, AI/API/error totals, cache stats |
| `GET /ai?range=` | provider/model table, highlights, chain, fallback flow |
| `GET /api?range=` | per-route table with 12-bucket trend |
| `GET /events?kind=&provider=&outcome=&status=&route=&request_id=&before=&limit=` | log explorer with cursor paging (`before` is the `at` of the last row) |
| `GET /events/live?after=&process_started_at=` | events after a cursor from memory; flags a restart or a gap |
| `GET /usage?range=` | usage counts, cost at read time and active-people integers (see above) |
| `GET /settings`, `PUT /settings {key, value}` | safe settings |
| `GET /audit?range=` | admin actions and sampled refusals |
| `POST /cache/clear` | clears every server cache (audited) |

## Testing

- `backend/tests/test_admin_portal.py` covers Sir Noah's acceptance conditions 1 to 14: the uniform 404, bad tokens counted, sampled refusal audit, aal2 and an empty allow-list, the field allow-list (privacy), failure isolation with RED unchanged, memory-only mode, sign-in cache rules, consent invalidation, provider pause rules, settings audit, validated-answer attribution and error categories, the migration's locks, paging and the cap.
- `backend/tests/test_ops_metrics.py` tests every aggregation, plus the bounded queue, flush and prune.
- `backend/tests/test_ttl_cache.py` tests the cache.
- `frontend/app/admin/format.test.ts` tests wording, units, view parsing and the live merge. `app/lib/api-cache.test.ts` checks that `/admin` is never cached.
- Local look: `BUBBLES_PREVIEW=1 python backend/preview_server.py`, plus the frontend with `NEXT_PUBLIC_UI_PREVIEW=1 NEXT_PUBLIC_API_URL=http://127.0.0.1:8001` on port 3100, then open `/admin`. The demo person is an admin there only.

## Limits (known, deliberate)

- Aggregation reads at most 20,000 rows per range and aggregates in Python (`ponytail:` in `ops_telemetry.py`). Upgrade path: an SQL summary function.
- Live view is polling (every 5 s while the tab is visible): there is no SSE or WebSocket on the free plan.
- One process: settings, caches and the live ring are per process. With several instances the settings would need reloading and the live view would see one instance.
- Restarts on the free plan empty the live ring; stored history survives once the migration is applied.
- Invalid JSON from one fallback provider still ends the chain (unchanged behaviour, out of scope here; it is now visible as `invalid_json` in the portal).
