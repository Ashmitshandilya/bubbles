-- Bubbles: a tiny register of which of these migrations have been applied, so the admin portal can tell you what is still pending.
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run). Safe to run twice. Run it FIRST.
-- Undo: supabase/undo/20261016_bubbles_schema_migrations_undo.sql
--
-- Every later Bubbles migration adds its own name to this table as its last step. For the migrations that were applied before this
-- table existed, the lines below record them only when their effect is visible in the database (the table or index they create exists).
-- Nothing here changes data, RLS on other tables, or grants on other tables. The app works the same without it.

begin;

create table if not exists public.bubbles_schema_migrations (
  name text primary key,
  applied_at timestamptz not null default now()
);

alter table public.bubbles_schema_migrations enable row level security;
-- No policies on purpose: browsers cannot read or write it. Only the trusted backend (service role) can.
revoke all on table public.bubbles_schema_migrations from anon, authenticated;
grant select, insert on table public.bubbles_schema_migrations to service_role;

insert into public.bubbles_schema_migrations (name)
values ('20261016_bubbles_schema_migrations')
on conflict (name) do nothing;

-- backfill, only where the effect can be seen
insert into public.bubbles_schema_migrations (name)
select '20261013_bubbles_ops' where to_regclass('public.bubbles_ops_events') is not null
on conflict (name) do nothing;

insert into public.bubbles_schema_migrations (name)
select '20261013_bubbles_db_tuneup' where exists (select 1 from information_schema.schemata where schema_name = 'archive')
on conflict (name) do nothing;

insert into public.bubbles_schema_migrations (name)
select '20261016_bubbles_indexes_v2' where to_regclass('public.bubbles_doc_user_title_idx') is not null
on conflict (name) do nothing;

commit;

-- Verify (three queries):
--   1. select name, applied_at from public.bubbles_schema_migrations order by applied_at;
--   2. select relrowsecurity from pg_class where oid = 'public.bubbles_schema_migrations'::regclass;   -- expect: true
--   3. select count(*) from pg_policies where tablename = 'bubbles_schema_migrations';                   -- expect: 0
