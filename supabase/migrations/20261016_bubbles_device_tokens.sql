-- Bubbles Android push: the table of phone (FCM) tokens. It is both the token store and the index the scheduler uses to find
-- "users who have push on", because per-user settings live in signed documents the scheduler cannot search.
--
-- Apply in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after reading it. Safe to run twice.
-- Until it is applied the API keeps working: registering a device answers "not ready", nothing is pushed, in-app reminders are
-- unchanged.
--
-- Privacy: a row holds only an opaque device token, the platform and the app version. No message text, no health data. The
-- token is deleted with the account (on delete cascade) and by "Delete my data".
-- Access: RLS is ON with NO policies and every privilege is revoked from anon and authenticated, so no browser can read or write
-- the table through the database API. Only the server (service_role) can.
-- Undo: supabase/undo/20261016_bubbles_device_tokens_undo.sql

begin;

create table if not exists public.device_tokens (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  token        text not null unique check (length(token) between 20 and 4096),
  platform     text not null default 'android' check (platform in ('android')),
  app_version  text check (app_version is null or length(app_version) <= 40),
  created_at   timestamptz not null default now(),
  last_seen    timestamptz not null default now(),
  revoked      boolean not null default false
);

create index if not exists device_tokens_user_active_idx on public.device_tokens (user_id) where not revoked;

alter table public.device_tokens enable row level security;

revoke all on table public.device_tokens from anon, authenticated;
grant select, insert, update, delete on table public.device_tokens to service_role;

-- Record this migration when the registry table from the data-trust migration exists (a no-op before it).
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_device_tokens') on conflict (name) do nothing;
  end if;
end $$;

commit;

-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select relname, relrowsecurity from pg_class where relname = 'device_tokens';
--   -> one row: relrowsecurity = true
-- select count(*) from pg_policies where tablename = 'device_tokens';
--   -> 0
-- select grantee, privilege_type from information_schema.role_table_grants
--   where table_name = 'device_tokens' and grantee in ('anon', 'authenticated');
--   -> no rows
