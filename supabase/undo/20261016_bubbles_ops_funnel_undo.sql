-- Undo for 20261016_bubbles_ops_funnel.sql: back to the five original kinds. Funnel and client rows are deleted first (the old check
-- would refuse them). Safe to run twice.

begin;

delete from public.bubbles_ops_events where kind in ('funnel', 'client');

alter table public.bubbles_ops_events drop constraint if exists bubbles_ops_events_kind_check;
alter table public.bubbles_ops_events
  add constraint bubbles_ops_events_kind_check check (kind in ('api', 'ai_attempt', 'ai_reply', 'error', 'audit'));

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_ops_funnel';
  end if;
end $$;

commit;
