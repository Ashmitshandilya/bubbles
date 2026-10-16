-- Bubbles: indexes for the hottest reads, and removal of three exact duplicates. Additive and safe to run twice.
--
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after reading it.
-- Nothing here changes data, RLS or grants. The app works the same before and after; it is just faster.
-- Undo: supabase/undo/20261016_bubbles_indexes_v2_undo.sql
--
-- Why: most "whole health" features (consent, notifications, plans, chat feedback, partner links) are signed documents stored in
-- public.health_events with event_type = 'bubbles_doc' and title = '<kind>:<key>' (backend/doc_store.py). Only (user_id, event_date)
-- was indexed, so every document read scanned the person's rows. Chat reads extracted_health_events by (user_id, event_type, created_at)
-- and by (user_id, message_id) on every turn; memory reads active rows newest first.

begin;

-- documents: doc_store find / put / delete / list
create index if not exists bubbles_doc_user_title_idx
  on public.health_events (user_id, title, created_at desc)
  where event_type = 'bubbles_doc';

-- tracker and analytics reads by type
create index if not exists health_events_user_type_date_idx
  on public.health_events (user_id, event_type, event_date desc);

-- chat: reads by type, and by message on every turn
create index if not exists extracted_events_user_type_created_idx
  on public.extracted_health_events (user_id, event_type, created_at desc);
create index if not exists extracted_events_user_message_idx
  on public.extracted_health_events (user_id, message_id);

-- memory: active rows newest first, and the duplicate check by source
create index if not exists memory_items_user_active_updated_idx
  on public.memory_items (user_id, updated_at desc) where is_active;
create index if not exists memory_items_user_source_idx
  on public.memory_items (user_id, source_id) where source_id is not null;

-- exact duplicates (pure write cost). Each is dropped only if its identical twin exists.
do $$
begin
  if to_regclass('public.idx_health_events_user_date') is not null then
    drop index if exists public.idx_health_events_user_time;
  end if;
  if to_regclass('public.idx_chat_messages_conversation_created') is not null then
    drop index if exists public.idx_chat_messages_conversation_time;
  end if;
end $$;

commit;

-- Verify (each should return one row per index name listed):
--   select indexname from pg_indexes where schemaname = 'public' and indexname in (
--     'bubbles_doc_user_title_idx', 'health_events_user_type_date_idx', 'extracted_events_user_type_created_idx',
--     'extracted_events_user_message_idx', 'memory_items_user_active_updated_idx', 'memory_items_user_source_idx');
--   -- the two duplicates should be gone:
--   select indexname from pg_indexes where schemaname = 'public' and indexname in ('idx_health_events_user_time', 'idx_chat_messages_conversation_time');
--   -- and a document read should now use the new index (look for bubbles_doc_user_title_idx in the plan):
--   explain select * from public.health_events where user_id = '00000000-0000-0000-0000-000000000000' and event_type = 'bubbles_doc' and title = 'consent:ai_chat';

-- Record that this migration was applied (only if 20261016_bubbles_schema_migrations.sql has been run). Safe to run twice.
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_indexes_v2') on conflict (name) do nothing;
  end if;
end $$;
