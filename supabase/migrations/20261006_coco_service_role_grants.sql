-- Restore trusted-backend (service_role) table privileges.
--
-- Finding (live audit 2026-10-06): service_role held SELECT on only 6 of 246
-- public tables and no privileges at all on profiles, health_events,
-- user_preferences, the 12 canonical domain tables, rl_* and organ_assessments.
-- The FastAPI backend authenticates to PostgREST with the service key, so every
-- read/write against those tables failed with 42501 "permission denied" and was
-- silently degraded to empty results by the backend's best-effort wrappers.
--
-- Scope: service_role only. anon/authenticated privileges, RLS policies and
-- table definitions are NOT changed: browsers still cannot write AI-derived
-- health data, and chat history stays server-writable only.
-- Idempotent: GRANT is a no-op when the privilege already exists.

do $$
declare t text;
begin
  foreach t in array array[
    -- canonical 20-table baseline
    'profiles','health_events','menstrual_cycles','symptoms','medications','medical_reports',
    'activity_logs','sleep_logs','hydration_logs','weight_logs','vital_signs','mood_logs',
    'medical_conditions','allergies','lab_results','doctor_visits','exercise_logs',
    'user_preferences','chat_conversations','chat_messages',
    -- backend-owned derived/infrastructure tables
    'extracted_health_events','memory_items','rag_documents','rag_chunks',
    'rl_interactions','rl_arm_stats','organ_assessments'
  ] loop
    if to_regclass(format('public.%I', t)) is not null then
      execute format('grant select, insert, update, delete on table public.%I to service_role', t);
    end if;
  end loop;
end $$;
