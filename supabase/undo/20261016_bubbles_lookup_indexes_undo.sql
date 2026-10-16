-- Undo of 20261016_bubbles_lookup_indexes.sql: drop the new indexes and the function, put the duplicate back.
begin;
do $$
declare t text;
begin
  foreach t in array array['sleep_logs','symptoms','activity_logs','menstrual_cycles','hydration_logs','mood_logs','weight_logs',
    'vital_signs','medications','medical_conditions','allergies','lab_results','medical_reports','doctor_visits'] loop
    execute format('drop index if exists public.%I', t || '_user_created_idx');
  end loop;
end $$;
drop index if exists public.health_events_tracker_created_idx;
drop index if exists public.bubbles_doc_title_idx;
drop index if exists public.extracted_events_compat_idx;
drop function if exists public.bubbles_chat_counts(uuid, uuid[]);
do $$
begin
  if to_regclass('public.user_preferences') is not null then
    create index if not exists idx_user_preferences_user on public.user_preferences (user_id);
  end if;
end $$;
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_lookup_indexes';
  end if;
end $$;
commit;
