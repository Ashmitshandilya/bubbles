-- Bubbles admin: let the ops events table hold onboarding funnel steps and client crash counts.
--
-- Apply ONCE in the Supabase SQL editor, AFTER 20261013_bubbles_ops.sql. Safe to run again. Until it is applied the API keeps
-- these two kinds in memory only (the rest of the telemetry is unaffected) and the admin portal says so.
--
-- What changes: the check on bubbles_ops_events.kind now also allows 'funnel' and 'client'. Both hold fixed words only (a
-- funnel step name, a crash code and 'web' or 'android'); the API rejects anything else before it is recorded. They are kept
-- 90 days, longer than the technical events, because they are tiny and answer slow questions. No user id, no text.
-- Undo: supabase/undo/20261016_bubbles_funnel_undo.sql

begin;

do $$
begin
  if to_regclass('public.bubbles_ops_events') is null then
    raise exception 'Apply 20261013_bubbles_ops.sql first (bubbles_ops_events does not exist).';
  end if;
end $$;

alter table public.bubbles_ops_events drop constraint if exists bubbles_ops_events_kind_check;
alter table public.bubbles_ops_events add constraint bubbles_ops_events_kind_check
  check (kind in ('api', 'ai_attempt', 'ai_reply', 'error', 'audit', 'funnel', 'client'));

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_funnel') on conflict do nothing;
  end if;
end $$;

commit;

-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select pg_get_constraintdef(oid) from pg_constraint where conname = 'bubbles_ops_events_kind_check';
--   -> a check that lists 'funnel' and 'client'
-- select count(*) from pg_policies where tablename = 'bubbles_ops_events';
--   -> 0 (still no policies)
-- select count(*) from bubbles_ops_events where kind in ('funnel', 'client');
--   -> 0 right after, then grows as people use the app
