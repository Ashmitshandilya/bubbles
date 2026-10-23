-- Bubbles Playbook: de-identified reply examples that people agreed to share (consent purpose "improve_bubbles"), and the entries
-- the owner approves from them. See BUBBLES_RENOVATION_PLAN.md section 9.2. Apply ONCE in the Supabase SQL editor. Safe to run twice.
-- Undo: supabase/undo/20261101_bubbles_playbook_undo.sql
--
-- Neither table holds a user id, a message from a person, or a name. Browsers cannot read or write them: row level security is on with no
-- policies, and nothing is granted to anon or authenticated. Only the trusted backend (service role) uses them.

begin;

create table if not exists public.bubbles_playbook_candidates (
  id uuid primary key default gen_random_uuid(),
  intent text not null,
  language text not null check (language in ('english', 'hinglish', 'hindi')),
  route text not null,
  reply_text text not null check (char_length(reply_text) <= 700),
  rating text not null check (rating in ('up', 'down', 'none')),
  outcome text not null check (outcome in ('helpful', 'unhelpful', 'unknown')),
  cohort_hash text not null,   -- HMAC of the user id with a server secret and the month: counts distinct people, cannot name them
  created_at timestamptz not null default now()
);
create index if not exists bubbles_playbook_candidates_intent_idx on public.bubbles_playbook_candidates (intent, language);
create index if not exists bubbles_playbook_candidates_created_idx on public.bubbles_playbook_candidates (created_at);

create table if not exists public.bubbles_playbook (
  id uuid primary key default gen_random_uuid(),
  intent text not null,
  language text not null check (language in ('english', 'hinglish', 'hindi')),
  guidance_text text not null default '',
  example_text text not null default '',
  status text not null default 'draft' check (status in ('draft', 'approved', 'retired')),
  approved_at timestamptz,
  uses integer not null default 0,
  helpful integer not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists bubbles_playbook_status_idx on public.bubbles_playbook (status, intent, language);

alter table public.bubbles_playbook_candidates enable row level security;
alter table public.bubbles_playbook enable row level security;
revoke all on table public.bubbles_playbook_candidates from anon, authenticated;
revoke all on table public.bubbles_playbook from anon, authenticated;
grant select, insert, update, delete on table public.bubbles_playbook_candidates to service_role;
grant select, insert, update, delete on table public.bubbles_playbook to service_role;

insert into public.bubbles_schema_migrations (name) values ('20261101_bubbles_playbook') on conflict (name) do nothing;

commit;

-- Verify (both should say rowsecurity = true and return no grants to anon or authenticated):
--   select tablename, rowsecurity from pg_tables where tablename in ('bubbles_playbook_candidates', 'bubbles_playbook');
--   select grantee, privilege_type from information_schema.role_table_grants
--     where table_name in ('bubbles_playbook_candidates', 'bubbles_playbook') and grantee in ('anon', 'authenticated');
