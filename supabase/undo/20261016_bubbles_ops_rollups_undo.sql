-- Undo for supabase/migrations/20261016_bubbles_ops_rollups.sql. Removes the daily counters.
-- The API keeps working afterwards (the Overall page falls back to events kept in memory).
begin;
drop table if exists public.ops_rollups_daily;
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_ops_rollups';
  end if;
end $$;
commit;
