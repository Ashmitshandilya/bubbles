-- R7: make chat persistence backend-owned and idempotent.
-- The browser may read its own history, but it no longer writes chat rows directly.
alter table if exists public.chat_messages
  add column if not exists client_message_id text;

create unique index if not exists uq_chat_messages_user_client_message
  on public.chat_messages(user_id, client_message_id)
  where client_message_id is not null;

create index if not exists idx_chat_messages_user_conversation_created
  on public.chat_messages(user_id, conversation_id, created_at asc);

-- Chat history is client-readable but server-writable only.
revoke insert, update, delete on table public.chat_messages from authenticated;
revoke insert, update, delete on table public.chat_conversations from authenticated;
grant select on table public.chat_messages to authenticated;
grant select on table public.chat_conversations to authenticated;

drop policy if exists "Users can manage their own chat messages" on public.chat_messages;
drop policy if exists "Users can manage their own conversations" on public.chat_conversations;

create policy "Users can view their own chat messages"
  on public.chat_messages for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can view their own conversations"
  on public.chat_conversations for select to authenticated
  using ((select auth.uid()) = user_id);

-- Derived/event-extraction tables are backend-owned; do not expose them through Data API.
revoke all on table public.extracted_health_events from anon, authenticated;
revoke all on table public.memory_items from anon, authenticated;
revoke all on table public.rag_documents from anon, authenticated;
revoke all on table public.rag_chunks from anon, authenticated;

-- Memory integrity: preserve replacement history and make freshness explicit.
alter table if exists public.memory_items
  add column if not exists verification_status text not null default 'unverified',
  add column if not exists last_confirmed_at timestamptz,
  add column if not exists review_after timestamptz,
  add column if not exists supersedes_memory_id uuid references public.memory_items(id) on delete set null,
  add column if not exists superseded_by uuid references public.memory_items(id) on delete set null;

alter table if exists public.memory_items
  drop constraint if exists memory_items_verification_status_check;
alter table if exists public.memory_items
  add constraint memory_items_verification_status_check
  check (verification_status in ('unverified','user_confirmed','system_derived','rejected','superseded'));

create index if not exists idx_memory_items_user_active_review
  on public.memory_items(user_id, is_active, review_after);
