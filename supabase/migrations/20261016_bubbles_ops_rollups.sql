-- Bubbles admin Overall page: durable daily counters, so "7 days, 30 days, all time" survive restarts and log pruning.
--
-- Apply ONCE in the Supabase SQL editor, AFTER 20261013_bubbles_ops.sql (the raw events table this summarises). Safe to run
-- again. Until it is applied the Overall page still works from the events kept in memory and says that history is not saved.
--
-- Privacy: rows hold counters only (route templates, fixed lists, provider and model names, latency buckets). No user id,
-- message, prompt, reply, token or address. RLS is ON with NO policies and nothing is granted to anon or authenticated, so no
-- browser can read or write it through the database API. Only the server (service_role) can.
-- Undo: supabase/undo/20261016_bubbles_ops_rollups_undo.sql

begin;

create table if not exists public.ops_rollups_daily (
  day        date   not null,
  dimension  text   not null check (length(dimension) <= 60),
  key        text   not null check (length(key) <= 200),
  count      bigint not null default 0,
  primary key (day, dimension, key)
);

create index if not exists ops_rollups_daily_dim_idx on public.ops_rollups_daily (dimension, day);

alter table public.ops_rollups_daily enable row level security;

revoke all on table public.ops_rollups_daily from anon, authenticated;
grant select, insert, update on table public.ops_rollups_daily to service_role;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_ops_rollups') on conflict do nothing;
  end if;
end $$;

commit;

-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select relname, relrowsecurity from pg_class where relname = 'ops_rollups_daily';
--   -> one row: relrowsecurity = true
-- select count(*) from pg_policies where tablename = 'ops_rollups_daily';
--   -> 0
-- select grantee, privilege_type from information_schema.role_table_grants
--   where table_name = 'ops_rollups_daily' and grantee in ('anon', 'authenticated');
--   -> no rows
