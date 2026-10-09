-- Coco storage reconciliation for the 33->45 prototype.
-- Canonical user data remains the original 20-domain-table model.
-- Compatibility/infrastructure tables used by the existing intelligence stack
-- (memory_items, extracted_health_events, RAG, RL, organ_assessments) are kept
-- separate and explicitly treated as derived infrastructure, not replacement
-- domain tables.

-- The 20 canonical tables and extracted_health_events are defined, matching the live
-- project, in 20260901_coco_baseline_live_schema.sql (this file previously described
-- a different shape, e.g. profiles.full_name / health_events.occurred_at).

alter table if exists public.health_events
  add column if not exists source_extracted_event_id uuid null references public.extracted_health_events(id) on delete set null;
create unique index if not exists uq_health_events_confirmed_extraction
  on public.health_events(user_id, source_extracted_event_id)
  where source_extracted_event_id is not null;
alter table if exists public.extracted_health_events
  add column if not exists extraction_status text not null default 'pending';

update public.extracted_health_events
set extraction_status = case when user_confirmed then 'confirmed' else 'pending' end
where extraction_status is null or extraction_status = '';

create table if not exists public.memory_items (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  memory_type text not null check (memory_type in ('L0','L1','L2','L3','L4')),
  content text not null, structured_data jsonb not null default '{}',
  source_type text, source_id uuid, confidence numeric not null default 0,
  is_active boolean not null default true, created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_health_events_user_time on public.health_events(user_id, event_date desc);
create index if not exists idx_extracted_events_user_time on public.extracted_health_events(user_id, created_at desc);
create index if not exists idx_extracted_events_user_status on public.extracted_health_events(user_id, extraction_status, created_at desc);
create index if not exists idx_memory_items_user_level on public.memory_items(user_id, memory_type, updated_at desc);
create index if not exists idx_chat_messages_conversation_time on public.chat_messages(conversation_id, created_at asc);

do $$
declare t text;
begin
  foreach t in array array['profiles','health_events','menstrual_cycles','symptoms','medications','medical_reports',
    'activity_logs','sleep_logs','hydration_logs','weight_logs','vital_signs','mood_logs','medical_conditions',
    'allergies','lab_results','doctor_visits','exercise_logs','user_preferences','chat_conversations','chat_messages',
    'extracted_health_events','memory_items'] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

-- User-owned tables: default deny, then grant access only to the authenticated owner.
do $$
declare t text;
begin
  foreach t in array array['health_events','menstrual_cycles','symptoms','medications','medical_reports','activity_logs',
    'sleep_logs','hydration_logs','weight_logs','vital_signs','mood_logs','medical_conditions','allergies','lab_results',
    'doctor_visits','exercise_logs','user_preferences','chat_conversations','chat_messages','extracted_health_events','memory_items'] loop
    execute format('drop policy if exists "coco_owner_all" on public.%I', t);
    execute format('create policy "coco_owner_all" on public.%I for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id)', t);
  end loop;
end $$;

drop policy if exists "coco_profile_owner" on public.profiles;
create policy "coco_profile_owner" on public.profiles for all to authenticated
using (auth.uid() = id) with check (auth.uid() = id);
