# L1 (chat backend) decision draft

For the lead to fold into DECISIONS.md (one entry per feature, newest first) and one line into CLAUDE.md conventions:
`No authority names in reply prose; sources only as links.`

### 2026-10-16 · Chat reply speed: fewer round trips, parallel reads, one model call
- What: `POST /chat` is split into a "prepare" half (sign-in to the safety gate) and a "respond" half. The conversation check and the recent
  turns are read together; the user message is inserted first (the unique client-message index refuses a repeat, the read happens only then);
  after the safety gate the person's own context, the evidence lookup and the tone settings are read side by side (two small thread pools,
  context copied so telemetry and the reply budget keep working); the facts the person stated are saved while the model thinks; the
  conversation timestamp and the turn log run after the reply is out; saving an empty event list does nothing; a message created a moment ago
  skips the duplicate-events read. Optional extras are time-boxed (evidence 2 s, the person's own context 8 s, both logged, never silent).
  The model gets the three sources the screen shows (1,200 characters each) instead of six at 2,000.
- AI quick wins: Gemini minimal-cost settings (thinking level `low`, `GEMINI_THINKING_LEVEL`; retried once without it if a model refuses the
  setting), 900 output tokens (generous on purpose: the reply is JSON), one shared Gemini client, a pooled `requests.Session` for the others
  (`max_tokens`, `reasoning_effort: low` for gpt-oss, JSON response format), `GEMINI_TIMEOUT_S` 9, `AI_REQUEST_TIMEOUT` 18 (the 50 s budget is
  still the ceiling), embedding call 3 s on a pooled session, `analyze_turn` warmed at start-up.
- Caches (ttl_cache rules, admin off switches `cache_enabled.<name>`): embedding per normalised question (1 h, no user id in the key), RAG
  handling policy per document (1 h, cleared on ingest), tone settings (2 min, cleared when the first-run setup or the name is saved, empty never
  stored), profile + preferences for replies (1 min, same invalidation). Memory items and health events are NOT cached: a just-saved symptom
  is in the next turn (tested).
- Numbers (local benchmark `backend/loadtest/chat_bench.py`, real FastAPI app on FakeDB with every database call and the embedding call
  sleeping 80 ms, AI stubbed with 0 ms; n = 30, p50): baseline origin/main d8d5add **1222 ms** for an AI-route message, branch **584 ms**
  (52 % lower); deterministic daily log 580 ms to 422 ms (27 % lower). With a 2 s stubbed model the branch's p50 is 2512 ms (about 500 ms
  of overhead around the model; the baseline was not measured at 2 s). Streaming (`/chat/stream`) total time to `done` is about the same as `/chat`.
- Why: the owner wants speed "at any cost"; an AI turn made about 17 mostly serial round trips around one blocking call.
- Where: `backend/main.py` (`_chat_prepare`, `_chat_respond`, `_context_stage`, `_evidence_stage`), `chat_pipeline.py`, `chat_cache.py`,
  `chat_concurrency.py`, `context_engine.py`, `memory_retrieval.py`, `rag.py`, `ai_provider.py`, `bubbles_ai.py`, `admin_settings.py`.
- Notes: the insert-first path trusts the unique index `uq_chat_messages_user_client_message` (migration 20260919_coco_r7_chat_write_authority);
  the owner should confirm it exists (query in docs/OWNER_TODO.md). Hedging providers (start Groq if Gemini has not answered in 3 to 4 s and
  take the first valid reply) was considered and NOT done: provider order and the allowlist are unchanged. `tests/test_production_contracts.py`
  pins the chat source; its strings were updated deliberately (`_DETERMINISTIC_ROUTES`, `state.consent_required`, `ctx_job = submit(`).

### 2026-10-16 · POST /chat/stream (server-sent events)
- What: beside the untouched `/chat`. Events: `meta` (conversation_id, user_message_id, safety, kind, consent_required) as soon as the safety gate
  is known, `delta` (pieces of the finished reply), `done` (exactly today's `/chat` JSON), `error`; `: ping` every 10 s. Deterministic routes, an
  empty message and a replayed retry send `meta` and `done` only. Headers: `Cache-Control: no-store`, `X-Accel-Buffering: no`.
- Honest limits: (1) `delta` pieces are sentences of the FINISHED reply, cut after the dose scrubber, attribution stripper, lint and the urgent
  call-to-action line, so the person never sees raw model text; this does not make the model faster (the model is still one blocking JSON
  call), it shows text sooner after the model finishes and lets the screen show the safety state before the reply. True token streaming would
  need provider streaming plus an incremental JSON-string reader and was not built. (2) **Whether the Vercel rewrite `/bubbles-api/*` passes
  chunks through is UNVERIFIED** (Vercel cannot be run here, and `next start` cannot stand in for Vercel's edge). The client must fall back to
  plain `/chat` on any error, and may call the API origin directly for the stream. (3) The stream's `api` telemetry event is written when the
  stream opens, so it carries `stage_pre_ms` and the route kind only; ctx, rag, ai and post numbers come from `/chat` turns.
- Where: `backend/main.py` (`chat_stream`, `_sse`, `_delta_chunks`), `backend/tests/test_chat_speed.py`.

### 2026-10-16 · Batch confirmation of chat details
- What: `POST /health-events/confirmation {decisions:[{id, confirmed}]}` (1 to 30) in its own router (`health_event_confirm.py`); the old
  `PATCH /health-events/{id}/confirmation` runs the same code. One read of the current statuses and one update per decision value with a
  status condition (a second press changes nothing). The decision is durable when the update commits; copying into the health record
  (batch variant `project_confirmed_events`: one read, one list insert) and into memory (the usual `promote_health_event` rules) happens after
  the response and never turns a saved decision into an error (failure is logged and retried the next time that detail is saved). Dismissing
  something already saved answers 409. A permission error from the record tables switches the answers to `compat` for 10 minutes.
- The saved state survives a reload: `GET /chat/conversations/{id}/messages`, `GET /chat/latest` and idempotent replays overlay the real status
  from `extracted_health_events` (one owner-scoped query per 100 ids). The stored cap of events per reply is 100 with `health_events_more`.
- Defaults chosen: confirming a fact also promotes it to memory (so the header count can move); a withdrawn (retracted, superseded or rejected)
  detail can never be re-saved (409); dismissing a saved detail is 409 rather than a silent half undo.

### 2026-10-16 · Resumed chats: the 48 hour rule
- What: in a resumed thread, what the person said more than 48 hours ago is history. The model sees those turns labelled "earlier, N days ago,
  not necessarily true now", their symptoms are listed as past (never as current), and an old "no X" is no longer a standing denial.
  The safety engine only ever reads the current message, so this cannot soften an alarm.
- Where: `chat_pipeline.py` (`HISTORY_NOW_HOURS`, `history_user_facts`, `conversation_block`). Clinical note: `docs/drafts/l1-clinical.md`.

### 2026-10-16 · Friend voice (finishing PR #27)
- What: `response_style_instruction()` is the single voice and format rule; the old conflicting lines are gone from `bubbles_ai.py`; the model
  is told to use the evidence silently and never name a publisher; the evidence wrapper carries the fixed sentence about Source/Publisher/URL
  lines. Output guards on AI text only, after the dose scrubber: `strip_attribution` now rewrites any SENTENCE that opens with "NHS guidance
  says", "According to the WHO,", "Studies show" (not just the first), `authority_citation` and `heavy_verdict` lint codes, and the fixed
  call-to-action line on URGENT replies. `normalize_response` no longer turns a friendly paragraph into bullets. "Detailed" users get about 160
  words (was 250), lint `max_words` 150. Care checklist copy and tags in `onboarding.py` no longer name programmes or societies.
- Freeze list: `tests/test_freeze_list.py` hashes every fixed safety text (nine messages through the four safety responses, CRISIS_LINES,
  follow-up, ai_failed, correction, consent, degraded, dose note and the two urgent organ sentences) against the values computed on d8d5add.
- Not done (optional in the brief): trimming an over-long AI reply at a sentence boundary (the prompt asks for 60 to 120 words and lint warns at 150).
- Not mine, still open for their lanes: source chip rows and "Read more" fold (L2, `ChatBits.tsx`), Insights "Sources" label and snippet (L4), the
  `rag_links.py` snippet.

### 2026-10-16 · Model tracking, cost at read time, funnel and app problems (A7)
- What: the five `stage_*_ms` numbers on chat events (numeric allow-list), `funnel` (setup steps reached, fixed names, kept 90 days) and `client`
  (app problem codes, fixed names) event kinds with migration `20261016_bubbles_ops_funnel.sql` (+ undo); until it is applied they stay in memory and the
  technical events still save (own insert, check-violation detected). `POST /telemetry/client {code}` takes one code and nothing else.
  `GET /admin/usage?range=` returns counts and rates (safety tiers per day, reply-kind mix, AI share, consent asks, fallback / degraded /
  timeout rates, route use, funnel, app problems), cost at read time (free tier shows $0 and "free tier", a model with no name or price shows
  "unknown", `if_paid_usd` shows what the tokens would cost at the published price) and distinct-active-people / signup integers (`ops_usage.py`).
- Defaults: while `ALLOW_PAID_AI` is off, every model counts as free tier; Gemini is outside `FREE_MODEL_ALLOWLIST` (documented in DEPLOY.md, `.env.example`
  and docs/admin/README.md as an asymmetry, not changed).
- Where: `ops_telemetry.py`, `ops_metrics.py`, `ops_usage.py`, `client_telemetry.py`, `admin_api.py` (`/usage`), `onboarding_api.py` (three funnel calls),
  `docs/admin/README.md`.
