-- Undo for supabase/migrations/20261016_bubbles_community.sql. Removes every Community table and all posts, comments, reactions,
-- reports, blocks, bans and the moderation log. The API keeps working afterwards (the Community page says it is not switched on).
begin;
drop table if exists public.community_reactions;
drop table if exists public.community_reports;
drop table if exists public.community_comments;
drop table if exists public.community_posts;
drop table if exists public.community_moderation_log;
drop table if exists public.community_blocks;
drop table if exists public.community_bans;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_community';
  end if;
end $$;

commit;
