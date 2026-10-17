# Owner to-do (things only you can do)

1. **Supabase SQL editor:** read and run `supabase/migrations/20261016_bubbles_indexes_v2.sql` once (and `20261013_bubbles_ops.sql` if the admin portal still says telemetry is memory-only). Run the verification queries at the bottom of each file. Undo files are in `supabase/undo/`.
2. **Render (optional, faster replies):** `GEMINI_TIMEOUT_S` now defaults to 12 and `AI_REQUEST_TIMEOUT` to 20. Set them higher only if replies time out.
3. Still open from the big brief (not built yet): consent ledger, onboarding (gender first), Mind section, insight detail sheet, deficiency intelligence, Android push (needs Firebase credentials), admin Live and Overall pages, community.

## Database and privacy choices (B1, B2): exact run order

Run these in the Supabase SQL editor, one file at a time (paste, read, Run). Every file is safe to run twice and has an undo file in `supabase/undo/`. The app keeps working before, between and after them.

1. `supabase/migrations/20261016_bubbles_schema_migrations.sql` (the register of applied migrations; run it first).
2. `supabase/migrations/20261013_bubbles_ops.sql` if the admin portal still says telemetry is "memory only".
3. `supabase/migrations/20261016_bubbles_indexes_v2.sql` (already listed above; if you ran it before step 1, run it again, it only adds its line to the register).
4. `supabase/migrations/20261016_bubbles_lookup_indexes.sql` (tracker summary, partner link, compat reads, the chat history counting function).
5. `supabase/migrations/20261016_bubbles_consent_ledger.sql` (the consent history table). Until you run it, every choice is still recorded, as signed documents, and moves into the table's history only for new decisions.
6. Check: open the admin portal (`/admin/schema` returns the list of migrations still missing) or run `select name from public.bubbles_schema_migrations;`. Each file also ends with three verification queries.
7. Optional, deliberate, **off by default**: `supabase/migrations/20261016_bubbles_rls_tightening.sql`. Read its header first. It stops signed-in browsers from writing to their own rows through the database API (Bubbles itself is not affected). Run the first queries of `docs/DB_AUDIT.md` section 1 before and after.

Before step 1, run the read-only queries in `docs/DB_AUDIT.md` section 1 and keep the results; they show what is really live.

Privacy choices: a clinician or lawyer has not reviewed the wording. The text of each choice lives in `backend/consent.py` (`PURPOSES`); changing a description or its `text_version` asks everyone again for that choice. The privacy notice is versioned (`frontend/app/lib/privacy-notice-version.ts` = `POLICY_VERSION` in `backend/consent.py`); bump both when the notice changes in a way that matters.

Decision for you: "Anonymous usage counts" (`product_usage_metrics`) is listed but cannot be turned on, because the standing rule is no analytics. Say if that should change.
