-- Bubbles: the indexes 20261016_bubbles_indexes_v2.sql did not cover, a small counting function, and the last duplicate index.
-- Apply ONCE in the Supabase SQL editor after 20261016_bubbles_schema_migrations.sql and 20261016_bubbles_indexes_v2.sql. Safe to run twice.
-- Nothing here changes data, RLS or the grants of any table. The app works the same before and after; it is just faster.
-- Undo: supabase/undo/20261016_bubbles_lookup_indexes_undo.sql
--
-- Why:
--   * /health/summary reads (user_id, created_at) of every tracker table; most had no index for that.
--   * The partner link and invite code look a document up by its title alone (no user id), which v2's index cannot serve.
--   * Every tracker list used to read up to 1000 whole rows of extracted_health_events to look for entries saved in compat mode.
--     A small partial index makes that read cheap for the few people who have such rows.
--   * /chat/history counted the messages of each conversation with one query per conversation.

begin;

-- 1. tracker tables: (user_id, created_at desc), created only where the table and its created_at column exist
do $$
declare t text;
begin
  foreach t in array array['sleep_logs','symptoms','activity_logs','menstrual_cycles','hydration_logs','mood_logs','weight_logs',
    'vital_signs','medications','medical_conditions','allergies','lab_results','medical_reports','doctor_visits'] loop
    if to_regclass('public.' || t) is not null and exists (
         select 1 from information_schema.columns where table_schema = 'public' and table_name = t and column_name = 'created_at') then
      execute format('create index if not exists %I on public.%I (user_id, created_at desc)', t || '_user_created_idx', t);
    end if;
  end loop;
end $$;

-- nutrition and eye checks live in health_events with an event_type
create index if not exists health_events_tracker_created_idx
  on public.health_events (user_id, created_at desc)
  where event_type in ('nutrition', 'eye_check');

-- 2. public lookups by document title (partner quick link, invite code)
create index if not exists bubbles_doc_title_idx
  on public.health_events (title)
  where event_type = 'bubbles_doc';

-- 3. compat-mode tracker entries (extracted_data->_prov->>store = 'compat')
create index if not exists extracted_events_compat_idx
  on public.extracted_health_events (user_id, created_at desc)
  where (extracted_data -> '_prov' ->> 'store') = 'compat';

-- 4. message counts for a page of conversations in one round trip (the backend falls back to counting one by one if this is missing)
create or replace function public.bubbles_chat_counts(p_user uuid, p_ids uuid[])
returns table (conversation_id uuid, message_count bigint)
language sql stable security invoker
as $$
  select m.conversation_id, count(*)::bigint
  from public.chat_messages m
  where m.user_id = p_user and m.conversation_id = any(p_ids)
  group by m.conversation_id
$$;
revoke all on function public.bubbles_chat_counts(uuid, uuid[]) from public, anon, authenticated;
grant execute on function public.bubbles_chat_counts(uuid, uuid[]) to service_role;

-- 5. the last exact duplicate: user_preferences.user_id is already the primary key
do $$
begin
  if exists (select 1 from pg_index i join pg_attribute a on a.attrelid = i.indrelid and a.attnum = i.indkey[0]
             where i.indrelid = to_regclass('public.user_preferences') and i.indisprimary and i.indnatts = 1 and a.attname = 'user_id') then
    drop index if exists public.idx_user_preferences_user;
  end if;
end $$;

commit;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_lookup_indexes') on conflict (name) do nothing;
  end if;
end $$;

-- Verify (three queries):
--   1. select indexname from pg_indexes where schemaname = 'public' and (indexname like '%\_user\_created\_idx' or indexname in
--        ('health_events_tracker_created_idx', 'bubbles_doc_title_idx', 'extracted_events_compat_idx')) order by 1;
--   2. select proname from pg_proc where proname = 'bubbles_chat_counts';                                  -- expect: one row
--   3. explain select id from public.extracted_health_events
--        where user_id = '00000000-0000-0000-0000-000000000000' and (extracted_data -> '_prov' ->> 'store') = 'compat'
--        order by created_at desc limit 1000;                                                           -- look for extracted_events_compat_idx
