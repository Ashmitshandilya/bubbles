-- Bubbles: the consent ledger. One row each time someone says yes or no to a choice in Privacy choices (or the chat card, or sign-up).
-- Apply ONCE in the Supabase SQL editor after 20261016_bubbles_schema_migrations.sql. Safe to run twice.
-- Undo: supabase/undo/20261016_bubbles_consent_ledger_undo.sql
--
-- Append only: the backend adds rows. Nothing deletes them, and the only allowed change to a row is unlinking it from a person
-- ("delete my data" sets user_id to null; the choice, the dates, the wording version and the one-way user_hash stay).
-- No free text is ever stored here.
-- Until this is applied the app keeps the same events as signed documents (kind consent_event), so no choice is ever lost.

begin;

create table if not exists public.consent_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete set null,
  user_hash text not null,
  purpose text not null check (char_length(purpose) between 1 and 60),
  granted boolean not null,
  policy_version text,
  text_version text,
  text_hash text,
  source text not null check (source in ('settings', 'chat_card', 'onboarding', 'system', 'signup')),
  created_at timestamptz not null default now()
);

create index if not exists consent_events_user_created_idx on public.consent_events (user_id, created_at desc) where user_id is not null;
create index if not exists consent_events_created_idx on public.consent_events (created_at desc);

alter table public.consent_events enable row level security;

-- A signed-in person may read their own rows (their "What you agreed to" history). Nobody can write from a browser.
drop policy if exists consent_events_owner_read on public.consent_events;
create policy consent_events_owner_read on public.consent_events for select to authenticated using (auth.uid() = user_id);

revoke all on table public.consent_events from anon, authenticated;
grant select on table public.consent_events to authenticated;
grant select, insert on table public.consent_events to service_role;
grant update (user_id) on table public.consent_events to service_role;

-- Append only, enforced by the database itself (the service role skips RLS but not triggers).
create or replace function public.bubbles_consent_events_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'consent_events is append only';
  end if;
  if new.user_id is not null or (to_jsonb(new) - 'user_id') <> (to_jsonb(old) - 'user_id') then
    raise exception 'consent_events rows can only be unlinked from a person';
  end if;
  return new;
end $$;

drop trigger if exists bubbles_consent_events_guard on public.consent_events;
create trigger bubbles_consent_events_guard before update or delete on public.consent_events
  for each row execute function public.bubbles_consent_events_guard();

commit;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_consent_ledger') on conflict (name) do nothing;
  end if;
end $$;

-- Verify (three queries):
--   1. select relrowsecurity from pg_class where oid = 'public.consent_events'::regclass;                    -- expect: true
--   2. select polname, polcmd from pg_policy where polrelid = 'public.consent_events'::regclass;             -- expect: one select policy
--   3. select grantee, privilege_type from information_schema.role_table_grants where table_name = 'consent_events' order by 1, 2;
--        -- expect: authenticated SELECT, service_role INSERT + SELECT (+ UPDATE on user_id only), nothing for anon
