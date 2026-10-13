-- Bubbles admin portal: technical telemetry and the few settings an administrator may change.
--
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after reading it.
-- Until it is applied the API keeps telemetry in memory only (lost on restart) and the admin portal says so.
--
-- Privacy: rows hold technical metadata only (route templates, status codes, latencies, provider and model names, outcomes,
-- error categories, admin actions). No message, prompt, reply, health detail, user id, token or address is ever written here.
-- Access: RLS is ON with NO policies, and every privilege is revoked from anon and authenticated, so no browser and no signed-in
-- user can read or write these tables through the database API. Only the server (service_role) can.
--
-- Plain "create table" on purpose: if a table with this name already exists on the live database (see
-- docs/security/SECURITY_STATUS.md, schema drift), this script stops with an error instead of silently reusing it.
-- Undo: supabase/undo/20261013_bubbles_ops_undo.sql

begin;

create table public.bubbles_ops_events (
  id          bigint generated always as identity primary key,
  at          timestamptz not null default now(),
  kind        text not null check (kind in ('api', 'ai_attempt', 'ai_reply', 'error', 'audit')),
  request_id  text check (request_id is null or request_id ~ '^[0-9a-f]{8,12}$'),
  data        jsonb not null default '{}'::jsonb check (jsonb_typeof(data) = 'object' and pg_column_size(data) < 4096)
);

create index bubbles_ops_events_at_idx on public.bubbles_ops_events (at desc);
create index bubbles_ops_events_kind_at_idx on public.bubbles_ops_events (kind, at desc);
create index bubbles_ops_events_request_idx on public.bubbles_ops_events (request_id) where request_id is not null;

create table public.bubbles_admin_settings (
  key         text primary key check (length(key) <= 80),
  value       jsonb not null,
  updated_at  timestamptz not null default now(),
  updated_by  text
);

alter table public.bubbles_ops_events enable row level security;
alter table public.bubbles_admin_settings enable row level security;

revoke all on table public.bubbles_ops_events from anon, authenticated;
revoke all on table public.bubbles_admin_settings from anon, authenticated;
revoke all on sequence public.bubbles_ops_events_id_seq from anon, authenticated;

grant select, insert, delete on table public.bubbles_ops_events to service_role;
grant usage on sequence public.bubbles_ops_events_id_seq to service_role;
grant select, insert, update on table public.bubbles_admin_settings to service_role;

commit;

-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select relname, relrowsecurity from pg_class where relname in ('bubbles_ops_events', 'bubbles_admin_settings');
--   -> both rows: relrowsecurity = true
-- select count(*) from pg_policies where tablename in ('bubbles_ops_events', 'bubbles_admin_settings');
--   -> 0
-- select grantee, table_name, privilege_type from information_schema.role_table_grants
--   where table_name in ('bubbles_ops_events', 'bubbles_admin_settings') and grantee in ('anon', 'authenticated');
--   -> no rows
-- select grantee, object_name, privilege_type from information_schema.role_usage_grants
--   where object_name = 'bubbles_ops_events_id_seq' and grantee in ('anon', 'authenticated');
--   -> no rows
