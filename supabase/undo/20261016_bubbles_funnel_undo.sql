-- Undo for supabase/migrations/20261016_bubbles_funnel.sql. Removes funnel and client rows, restores the original check.
-- The API keeps working afterwards (it notices the table refuses these kinds and keeps them in memory only).
begin;
delete from public.bubbles_ops_events where kind in ('funnel', 'client');
alter table public.bubbles_ops_events drop constraint if exists bubbles_ops_events_kind_check;
alter table public.bubbles_ops_events add constraint bubbles_ops_events_kind_check
  check (kind in ('api', 'ai_attempt', 'ai_reply', 'error', 'audit'));
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_funnel';
  end if;
end $$;
commit;
