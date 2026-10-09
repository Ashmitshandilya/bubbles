-- PROPOSAL ONLY - NOT APPLIED. Recommended hardening for the Whole-Health OS documents.
-- Why: the older migration (20260919_coco_storage_reconciliation.sql) lets any signed-in browser read and write ITS OWN rows of
-- public.health_events through the database API. Bubbles' server signs every document it stores (backend/doc_store.py), so a forged or
-- edited document is ignored, but it is still best that browsers cannot write these rows at all.
-- This keeps everything else about health_events as it is and only blocks browser access to event_type = 'bubbles_doc'.
-- Run it once in the Supabase SQL editor after reviewing. Check the effect with:
--   select polname, polcmd from pg_policy where polrelid = 'public.health_events'::regclass;

create policy bubbles_doc_backend_only on public.health_events
  as restrictive
  for all
  to authenticated
  using (event_type <> 'bubbles_doc')
  with check (event_type <> 'bubbles_doc');

-- Optional: one row per document, so two simultaneous saves cannot create duplicates.
create unique index if not exists health_events_bubbles_doc_unique
  on public.health_events (user_id, title)
  where event_type = 'bubbles_doc';
