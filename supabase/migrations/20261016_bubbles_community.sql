-- Bubbles Community (text-only posts, comments, reactions, reports, blocks, moderation log, bans).
--
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after reading it. Safe to run twice.
-- Until it is applied the Community page says it is not switched on yet and the rest of Bubbles is unaffected.
-- Also set COMMUNITY_ALIAS_SECRET on the API host (a long random string): without it Community stays off by design.
--
-- Privacy: every read and write goes through the Bubbles API, which never returns author_id to other people.
-- Access: RLS is ON with NO policies and every privilege is revoked from anon and authenticated, so no browser and no signed-in
-- user can read or write these tables through the database API. Only the server (service_role) can. service_role gets explicit
-- grants on purpose (the compat-mode lesson: a table created later is not covered by the older grant lists).
-- Undo: supabase/undo/20261016_bubbles_community_undo.sql

begin;

create table if not exists public.community_posts (
  id            uuid primary key default gen_random_uuid(),
  author_id     uuid not null references auth.users(id) on delete cascade,
  display_mode  text not null check (display_mode in ('anonymous', 'named')),
  alias         text not null check (char_length(alias) between 1 and 40),
  topic         text not null check (topic in ('cycle', 'sleep', 'mind', 'food', 'fitness', 'skin_hair', 'talk')),
  body          text not null check (char_length(body) between 1 and 1200),
  status        text not null default 'visible' check (status in ('visible', 'held', 'removed')),
  reason_code   text check (reason_code is null or char_length(reason_code) <= 40),
  crisis        boolean not null default false,
  created_at    timestamptz not null default now(),
  edited_at     timestamptz
);

create table if not exists public.community_comments (
  id            uuid primary key default gen_random_uuid(),
  post_id       uuid not null references public.community_posts(id) on delete cascade,
  author_id     uuid not null references auth.users(id) on delete cascade,
  display_mode  text not null check (display_mode in ('anonymous', 'named')),
  alias         text not null check (char_length(alias) between 1 and 40),
  body          text not null check (char_length(body) between 1 and 600),
  status        text not null default 'visible' check (status in ('visible', 'held', 'removed')),
  reason_code   text check (reason_code is null or char_length(reason_code) <= 40),
  crisis        boolean not null default false,
  created_at    timestamptz not null default now(),
  edited_at     timestamptz
);

create table if not exists public.community_reactions (
  id          uuid primary key default gen_random_uuid(),
  post_id     uuid references public.community_posts(id) on delete cascade,
  comment_id  uuid references public.community_comments(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        text not null check (kind in ('me_too', 'helpful')),
  created_at  timestamptz not null default now(),
  check ((post_id is not null) <> (comment_id is not null))
);

create table if not exists public.community_reports (
  id           uuid primary key default gen_random_uuid(),
  target       text not null check (target ~ '^(post|comment):[0-9a-f-]{36}$'),
  reporter_id  uuid not null references auth.users(id) on delete cascade,
  reason       text not null check (reason in ('unkind', 'unsafe_advice', 'spam', 'private_info', 'sexual', 'other')),
  created_at   timestamptz not null default now(),
  unique (target, reporter_id)
);

-- Rows here hold codes only, never text. The trail is kept after a post is deleted.
create table if not exists public.community_moderation_log (
  id           uuid primary key default gen_random_uuid(),
  target       text not null,
  action       text not null check (char_length(action) <= 40),
  reason_code  text check (reason_code is null or char_length(reason_code) <= 40),
  actor        text not null check (actor in ('bot', 'admin', 'user')),
  created_at   timestamptz not null default now()
);

-- blocked_alias_key is a one-way keyed hash of the blocked person, never their id or alias.
create table if not exists public.community_blocks (
  user_id            uuid not null references auth.users(id) on delete cascade,
  blocked_alias_key  text not null check (char_length(blocked_alias_key) between 16 and 128),
  created_at         timestamptz not null default now(),
  primary key (user_id, blocked_alias_key)
);

create table if not exists public.community_bans (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  reason_code  text check (reason_code is null or char_length(reason_code) <= 40),
  created_at   timestamptz not null default now()
);

create index if not exists community_posts_feed_idx on public.community_posts (created_at desc) where status = 'visible';
create index if not exists community_posts_topic_idx on public.community_posts (topic, created_at desc) where status = 'visible';
create index if not exists community_posts_author_idx on public.community_posts (author_id, created_at desc);
create index if not exists community_posts_review_idx on public.community_posts (created_at) where status = 'held';
create index if not exists community_comments_post_idx on public.community_comments (post_id, created_at);
create index if not exists community_comments_author_idx on public.community_comments (author_id, created_at desc);
create index if not exists community_reactions_post_idx on public.community_reactions (post_id) where post_id is not null;
create index if not exists community_reactions_comment_idx on public.community_reactions (comment_id) where comment_id is not null;
create unique index if not exists community_reactions_post_once on public.community_reactions (post_id, user_id, kind) where post_id is not null;
create unique index if not exists community_reactions_comment_once on public.community_reactions (comment_id, user_id, kind) where comment_id is not null;
create index if not exists community_reports_target_idx on public.community_reports (target);
create index if not exists community_moderation_log_idx on public.community_moderation_log (created_at desc);

alter table public.community_posts enable row level security;
alter table public.community_comments enable row level security;
alter table public.community_reactions enable row level security;
alter table public.community_reports enable row level security;
alter table public.community_moderation_log enable row level security;
alter table public.community_blocks enable row level security;
alter table public.community_bans enable row level security;

revoke all on table public.community_posts from anon, authenticated;
revoke all on table public.community_comments from anon, authenticated;
revoke all on table public.community_reactions from anon, authenticated;
revoke all on table public.community_reports from anon, authenticated;
revoke all on table public.community_moderation_log from anon, authenticated;
revoke all on table public.community_blocks from anon, authenticated;
revoke all on table public.community_bans from anon, authenticated;

grant select, insert, update, delete on table public.community_posts to service_role;
grant select, insert, update, delete on table public.community_comments to service_role;
grant select, insert, update, delete on table public.community_reactions to service_role;
grant select, insert, update, delete on table public.community_reports to service_role;
grant select, insert, delete on table public.community_moderation_log to service_role;
grant select, insert, update, delete on table public.community_blocks to service_role;
grant select, insert, update, delete on table public.community_bans to service_role;

commit;

-- Record that this migration was applied (only if 20261016_bubbles_schema_migrations.sql has been run). Safe to run twice.
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_community') on conflict (name) do nothing;
  end if;
end $$;


-- Verification (run after the script; every line must match the expectation in its comment):
--
-- select relname, relrowsecurity from pg_class where relname like 'community\_%' and relkind = 'r';
--   -> seven rows, relrowsecurity = true on every one
-- select count(*) from pg_policies where tablename like 'community\_%';
--   -> 0
-- select grantee, table_name, privilege_type from information_schema.role_table_grants
--   where table_name like 'community\_%' and grantee in ('anon', 'authenticated');
--   -> no rows
