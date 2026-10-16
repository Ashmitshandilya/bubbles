-- Undo of 20261016_bubbles_indexes_v2.sql: drop the new indexes and put the two duplicates back.
begin;
drop index if exists public.bubbles_doc_user_title_idx;
drop index if exists public.health_events_user_type_date_idx;
drop index if exists public.extracted_events_user_type_created_idx;
drop index if exists public.extracted_events_user_message_idx;
drop index if exists public.memory_items_user_active_updated_idx;
drop index if exists public.memory_items_user_source_idx;
create index if not exists idx_health_events_user_time on public.health_events (user_id, event_date desc);
create index if not exists idx_chat_messages_conversation_time on public.chat_messages (conversation_id, created_at asc);
commit;
