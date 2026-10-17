# F1 + F2: Admin Live and Overall pages (lane L9)

## Problem statement

The owner runs Bubbles from the admin portal and cannot answer four plain questions today.

1. **"Who just hit the app, and how did it go?"** The old Live tab lists technical events but by design carries no account id, so a report like "my chat was slow" cannot be matched to a request. Cause: `ops_telemetry.record()` accepted no user field (the ring held `{seq, at, kind, request_id, data}` only, `backend/ops_telemetry.py` module note) and `/admin/events/live` returned the raw ring. The tab also showed one line per event rather than one row per request, so an AI try, its fallback and the reply were three unrelated lines to stitch by hand (old `frontend/app/admin/panels.tsx`).
2. **"Where does a chat turn spend its time?"** The api event carried no stage timings. The stage field names (`stage_pre_ms`, `stage_ctx_ms`, `stage_rag_ms`, `stage_ai_ms`, `stage_post_ms`) were not on the `api` allow-list (`ops_telemetry.FIELDS["api"]`), so the pipeline's measurements would have been silently dropped.
3. **"How is Bubbles doing overall, since the start?"** Every number on the portal is computed from at most 20,000 raw events (`ops_telemetry.READ_CAP`), which are pruned after 14 days and are memory-only until the owner applies `20261013_bubbles_ops.sql`; a Render restart or sleep loses them. There was no all-time total, no 7d/30d beyond raw retention, no retention curve, no consent rate per purpose, no onboarding drop-off (`admin_api.py` had ranges up to `30d` only, all from raw events).
4. **"What should I look at next?"** Nothing exported, nothing refreshed itself while the tab was hidden or paused correctly, and nobody could tell when the page was only showing memory.

Constraints that shaped the fix: the admin gate (fresh sign-in, two-step, allow-list, byte-identical 404) stays exactly as it is; telemetry stays metadata only; the one owner-approved exception is the account id on the Live page, kept in the in-memory ring only; $0 infrastructure (no Redis, no SSE, no new dependency); the app must keep working when the owner has not applied the new migrations.

## What changed

Backend
- `ops_telemetry.py`: `bind_user` (UUID-shaped only), a top-level `uid` on `api` and `ai_attempt` events in the ring only (never in `data`, the queue, the table or the notes), `recent(with_uid=True)` as the only reader that returns it, `STAGE_FIELDS`, numeric validation of stage values in `record()`, `until` on `stored_events` (hour-by-hour reads for the rollup).
- `ops_rollups.py` (new): `count_events` (pure, tolerant of malformed rows), `run_rollups(db)` (idempotent hourly job with a watermark moved in the same upsert; exported for lane L8's cron endpoint), `collect(db, range)` for `1h/24h/7d/30d/all`, lazy refresh with a non-blocking lock.
- `ops_metrics.overall_view`, `ops_snapshots.py` (new: DAU/WAU/MAU, signups, D1/D7/D30 retention, consent rates, community and push counts, integers only), `admin_api.py`: `GET /admin/live` (alias of `/events/live`, with `since` or `after` cursor) and `GET /admin/overall?range=`.
- `supabase/migrations/20261016_bubbles_ops_rollups.sql` (+ undo): `ops_rollups_daily`, RLS on, service role only. Registered in `schema_status.py`.
- Reconciled with the session branch: one `funnel`/`client` contract (L1's `FUNNEL_STEPS = core, extras, later, completed, under_18`, `ops_telemetry.client(code)`, `/telemetry/client`); my duplicate migration and `client_events_api.py` were removed; cost uses L1's `model_cost` (A7).

Frontend (`frontend/app/admin`)
- Live: one row per request (UID with copy button, time, route, feature, provider, model, fallback, safety, status, latency, stage breakdown, error), filters, pause/resume, row detail with the request-id chain, polling every 3 s paused when the tab is hidden, a banner when events are memory only.
- Overall: totals, per-model rates, per-stage latency, funnel, retention, consent, safety, features, errors, community, push; range picker; CSV export per table (formula-safe); refresh every 20 s, paused when hidden.

Docs: `docs/admin/README.md` (named exception, Add another admin, rollup and cron contract), `DESIGN.md`, one line on `/privacy`.

## Decisions taken from defaults

- Refusals stay a byte-identical 404 (the brief says keep the gate exactly as is); the "403 for non-admin, 401 for anonymous" in the lane message was not applied because it would reveal that `/admin` exists and break the existing contract and its tests.
- Polling, not SSE (not verified on the Render free plan).
- Cost shows `$0, free tier` while paid AI is off.

## Open

- Owner: apply `20261016_bubbles_ops_rollups.sql` (and `20261016_bubbles_ops_funnel.sql`) in Supabase; until then Overall counts only what is held.
- Lane L8 must call `ops_rollups.run_rollups(db)` from its cron endpoint (optional: the page also rolls up lazily).
- Single-instance assumption for the rollup watermark (no compare-and-swap).
