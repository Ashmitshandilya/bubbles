-- Bubbles admin portal: two more kinds of technical event ("funnel" = which first-run setup step people reach, "client" = the website or
-- app reporting that something broke).
--
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after 20261013_bubbles_ops.sql.
-- Until it is applied nothing breaks: the API keeps these two kinds in memory only and the technical events are saved as before.
--
-- Privacy: a funnel row holds a fixed step name (about, goals, health, life, daily, mind, people, drains, talk, completed, under_18) and a
-- client row holds a fixed problem code (render_error, chunk_load_failed, ...). No user id, answer, message or address. The API refuses any
-- other value before it reaches this table. RLS and the revoked grants from the ops migration still apply (nothing here changes them).
-- Funnel rows are kept 90 days by the API's own pruning, technical rows 14 days, audit rows 365 days.
--
-- Idempotent: it replaces the one check constraint on bubbles_ops_events.kind and can be run twice.
-- Undo: supabase/undo/20261016_bubbles_ops_funnel_undo.sql

begin;

do $$
declare
  c record;
begin
  -- the kind check from the ops migration (its generated name is bubbles_ops_events_kind_check, found by definition to be safe)
  for c in
    select conname from pg_constraint
    where conrelid = 'public.bubbles_ops_events'::regclass and contype = 'c' and pg_get_constraintdef(oid) ilike '%kind%in%'
  loop
    execute format('alter table public.bubbles_ops_events drop constraint %I', c.conname);
  end loop;
  alter table public.bubbles_ops_events
    add constraint bubbles_ops_events_kind_check
    check (kind in ('api', 'ai_attempt', 'ai_reply', 'error', 'audit', 'funnel', 'client'));
end $$;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_ops_funnel') on conflict (name) do nothing;
  end if;
end $$;

commit;

-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select pg_get_constraintdef(oid) from pg_constraint where conname = 'bubbles_ops_events_kind_check';
--   -> a check that lists api, ai_attempt, ai_reply, error, audit, funnel, client
-- select count(*) from pg_policies where tablename = 'bubbles_ops_events';
--   -> 0 (still no policy)
-- select relrowsecurity from pg_class where relname = 'bubbles_ops_events';
--   -> true
