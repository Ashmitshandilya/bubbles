# Database audit (B1)

Checked against the code on 2026-10-16 (branch `lane/l5-data-trust`). Where this differs from the earlier brief, the code wins and the difference is noted. Nothing here was run against the live database: the sandbox has no access to it. Section 1 is what to run first to learn what is really live.

## 1. Run this first (read-only, Supabase SQL editor)

Paste each block, run it, keep the results.

```sql
-- 1a. Which tables exist, how many rows (estimate), how big
select n.nspname as schema, c.relname as table, c.reltuples::bigint as approx_rows,
       pg_size_pretty(pg_total_relation_size(c.oid)) as size, c.relrowsecurity as rls
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r' and n.nspname in ('public', 'archive')
order by n.nspname, pg_total_relation_size(c.oid) desc;

-- 1b. Every index in public (look for the names listed in section 4)
select tablename, indexname, indexdef from pg_indexes where schemaname = 'public' order by tablename, indexname;

-- 1c. Were the key migrations applied? (each returns a row if yes)
select 'grants_20261006: service_role can write health_events' as check_name
 where has_table_privilege('service_role', 'public.health_events', 'INSERT');
select 'tuneup_20261013: archive schema exists' as check_name where exists (select 1 from information_schema.schemata where schema_name = 'archive');
select 'ops_20261013: bubbles_ops_events exists' as check_name where to_regclass('public.bubbles_ops_events') is not null;
select 'chat unique key (idempotent sends)' as check_name where to_regclass('public.uq_chat_messages_user_client_message') is not null;
select 'indexes_v2 applied' as check_name where to_regclass('public.bubbles_doc_user_title_idx') is not null;
select 'consent ledger applied' as check_name where to_regclass('public.consent_events') is not null;
select 'schema register applied' as check_name where to_regclass('public.bubbles_schema_migrations') is not null;

-- 1d. Which policies let a browser WRITE? (the finding in section 5)
select tablename, policyname, cmd, roles from pg_policies
where schemaname = 'public' and cmd in ('ALL', 'INSERT', 'UPDATE', 'DELETE') order by tablename;

-- 1e. How much of health_events is signed documents (the hottest table), and is there anything duplicated?
select event_type = 'bubbles_doc' as is_doc, count(*) from public.health_events group by 1;
select user_id, title, count(*) from public.health_events where event_type = 'bubbles_doc' group by 1, 2 having count(*) > 1 limit 20;

-- 1f. Which indexes are never used? (run again after a week of traffic before dropping anything)
select relname as table, indexrelname as index, idx_scan from pg_stat_user_indexes where schemaname = 'public' order by idx_scan, relname limit 40;
```

## 2. What the backend really uses

About 25 tables: the 20 canonical ones (profiles, health_events, menstrual_cycles, symptoms, medications, medical_reports, activity_logs, sleep_logs, hydration_logs, weight_logs, vital_signs, mood_logs, medical_conditions, allergies, lab_results, doctor_visits, exercise_logs, user_preferences, chat_conversations, chat_messages) plus extracted_health_events, memory_items, rag_documents, rag_chunks, rl_interactions, rl_arm_stats, bubbles_ops_events, bubbles_admin_settings. New in this branch: consent_events, bubbles_schema_migrations (both optional: the app works without them). Kept by the 20261013 tune-up but never read by the backend: notifications, supplements, vaccinations, family_medical_history, ovulation_tests, pregnancy_tests, organ_assessments (the last is granted but unused).

Most "whole health" features are not tables. They are signed JSON documents in `health_events` with `event_type = 'bubbles_doc'` and `title = '<kind>:<key>'` (`backend/doc_store.py`): notifications, plans, food logs, cycle days, chat feedback, partner links, consent (older single yes), the onboarding experience profile, safety pauses. That makes `health_events` the hottest table.

## 3. Migration chain

16 migration files and 3 undo files before today. Today's `20261016_bubbles_*` set, each with an undo file: `indexes_v2` (already on main), `schema_migrations`, `lookup_indexes`, `consent_ledger`, `rls_tightening` (optional).

- **The chain does not replay in filename order.** `20260919_coco_storage_reconciliation.sql` sorts after `20260919_coco_r7_chat_write_authority.sql` (`r` < `s`), so a database built by replaying the files ends with the browser-writable `coco_owner_all` policy back on `chat_messages` and `chat_conversations`, undoing R7. The live database was not built this way, which is why nobody can prove what is live. `SECURITY_STATUS.md` still says about 219 live tables have no definition in the repo. Export the live schema as a new baseline before anyone sets up a copy (not done here: needs the live database).
- **Grants.** The backend uses the service key, so RLS does not gate it; only GRANTs do. `20261006_coco_service_role_grants.sql` lists 27 tables. A table created later and used by the backend needs its own grant. Every new table in this branch grants itself (`consent_events`, `bubbles_schema_migrations`); `bubbles_ops` already did. Without a grant the backend gets Postgres 42501, and the code degrades (`db_access.is_permission_denied`, compat store in `health_logs.py`).
- **Register.** `20261016_bubbles_schema_migrations.sql` adds `public.bubbles_schema_migrations(name, applied_at)` (RLS on, no policies, service role only). Each new migration inserts its name as its last step (guarded, so order does not matter). `GET /admin/schema` (admin only, behind the existing admin gate) lists which known migrations are missing. `backend/schema_status.py:KNOWN` is the list; a lane that adds a migration adds its name there.

## 4. Indexes

Verified in the code: `doc_store` reads by `(user_id, event_type = 'bubbles_doc', title)`; the partner quick link and invite code read by `(event_type, title)` with no user id; `_compat_events` filters `extracted_data->_prov->>store` on every tracker list; chat reads `extracted_health_events` by `(user_id, event_type, created_at)` and `(user_id, message_id)` every turn (`chat_pipeline._existing_keys`); memory reads active rows newest first.

| Need | Where | Index |
|---|---|---|
| document lookups | `20261016_bubbles_indexes_v2` | `bubbles_doc_user_title_idx` (user_id, title, created_at desc) where bubbles_doc |
| tracker/analytics by type | v2 | `health_events_user_type_date_idx` |
| chat events | v2 | `extracted_events_user_type_created_idx`, `extracted_events_user_message_idx` |
| memory | v2 | `memory_items_user_active_updated_idx`, `memory_items_user_source_idx` |
| tracker summary (user_id, created_at) on 14 tracker tables | `20261016_bubbles_lookup_indexes` | `<table>_user_created_idx` (only where the table and column exist) |
| nutrition / eye checks in health_events | lookup_indexes | `health_events_tracker_created_idx` (partial) |
| public lookups by title | lookup_indexes | `bubbles_doc_title_idx` (partial, title only) |
| compat-mode reads | lookup_indexes | `extracted_events_compat_idx` (partial on the JSON path, so it stays tiny) |
| consent trail | `20261016_bubbles_consent_ledger` | `consent_events_user_created_idx`, `consent_events_created_idx` |

Duplicates (pure write cost): `idx_health_events_user_time` = `idx_health_events_user_date` and `idx_chat_messages_conversation_time` = `idx_chat_messages_conversation_created` (dropped in v2, each only if its twin exists); `idx_user_preferences_user` = the primary key (dropped in lookup_indexes only if `user_id` is the single-column primary key). `idx_chat_messages_user_created` is left until `pg_stat_user_indexes` shows zero scans over a week. No ops-events index was added (the existing three cover the admin reads); a prune function was not needed (retention is handled by the backend flusher).

Nothing here touches RLS or grants of an existing table. EXPLAIN examples are at the bottom of each file.

## 5. Security finding: browser-writable policies

`20260919_coco_storage_reconciliation.sql` creates `coco_owner_all FOR ALL TO authenticated` on `health_events`, the canonical tracker tables, `chat_*`, `extracted_health_events` and `memory_items`. Any signed-in browser can therefore insert, update or delete its own rows through the Data API, including `user_confirmed = true` and signed-document rows (`bubbles_doc`). `doc_store` signs every document, so a forged document is ignored, but writes should not be possible at all.

Proof the website does not need those rights: in `frontend/app`, `components`, `lib` the only `supabase.*` calls are `supabase.auth.*` (sign-in, session, MFA); there is no `supabase.from(...)` or `.rpc(...)` (grep run 2026-10-16; the `.from(` hits are `Array.from`).

`20261016_bubbles_rls_tightening.sql` (**default OFF, the owner applies it deliberately**) replaces those policies with select-only for the owner, revokes insert/update/delete from `authenticated`, and hides `bubbles_doc` rows from browsers (restrictive select policy; the older write-only proposal in `docs/proposals/lock-bubbles-doc-rows.sql` is covered). The optional unique index (user_id, title) on documents from that proposal was not included: `doc_store.get` already takes the newest valid row, and a unique index would turn a race between two saves into an error. Run query 1e above first if you want it. DECISIONS.md requires an explicit decision for RLS changes: this brief authorises the file; the owner applies it.

## 6. N+1 patterns

| Where | Before | Now |
|---|---|---|
| `GET /chat/history` message counts | one exact count per conversation (up to 50; later 8 at a time) | one call to `bubbles_chat_counts` (`chat_counts.py`); falls back to the parallel per-conversation count while the function is missing |
| `GET /health/summary` | 17 sequential tracker reads plus a compat scan of up to 1000 whole rows | the tracker reads run concurrently (8 at a time); the compat scan is skipped when the primary tables were readable and a remembered flag says this person has no compat entries (5 min cache, cleared by any compat save) |
| tracker list (`list_domain`) | compat scan on every list | same flag |
| `GET /chat/feedback` | `doc_store.get` once per id (up to 50) | `doc_store.get_many`: one read |
| `doc_store.delete_everything` | one DELETE per row | one DELETE per 100 ids; also keeps the consent trail |

The optional SQL function `bubbles_tracker_stamps` was not added: the concurrent reads plus the new per-table indexes make the summary fast enough, and a second SQL object would be a second code path to maintain.

## 7. Not done, and why

- No live schema export or EXPLAIN against real data (no database access from the sandbox). The EXPLAIN queries are in the migration files.
- No CHECK constraint on `extracted_health_events.extraction_status` (optional in the brief). Add it as `NOT VALID` only after `select extraction_status, count(*) from extracted_health_events group by 1` shows only the five known values.
- The 214 archived tables were not re-audited.

## 7. Live table list (read through the Data API on 2026-10-26, after the fresh start)

44 tables are visible in `public`: 33 carry a `user_id` (activity, allergies, chat, community bans/blocks/reactions, consent, doctor visits, exercise, extracted events, family history, health events, hydration, labs, conditions, reports, medications, memory, cycles, mood, notifications, ovulation and pregnancy tests, rl, sleep, supplements, symptoms, preferences, vaccinations, vitals, weight); the others are the profile (`id` is the account), the RAG corpus, community posts and comments (author column), admin settings, ops events and rollups, and the migration register. The Data API does not show foreign keys to `auth.users`, so what is live must be confirmed with the SQL in section 1.

`20261102_bubbles_data_links.sql` (owner applies, safe to run twice, has an undo file):
- adds `user_id -> auth.users(id) on delete cascade` wherever it is missing, removing orphan rows first (`consent_events` is skipped for the cleanup because it is append-only);
- adds `public.bubbles_daily_facts`, one row per person per UTC day with sleep, mood, water and activity side by side (service role only).

The backend still reads the real tables and computes local days itself; the view is for analysis and the admin portal.
