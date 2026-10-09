alter table if exists public.chat_messages add column if not exists metadata jsonb not null default '{}'::jsonb;
