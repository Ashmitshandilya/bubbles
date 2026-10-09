-- R6: harden canonical Coco RLS roles and add ownership indexes.
do $$
declare r record; q text; wc text;
begin
  for r in select schemaname,tablename,policyname,qual,with_check from pg_policies
    where schemaname='public' and tablename in ('profiles','health_events','menstrual_cycles','symptoms','medications','medical_reports','activity_logs','sleep_logs','hydration_logs','weight_logs','vital_signs','mood_logs','medical_conditions','allergies','lab_results','doctor_visits','exercise_logs','user_preferences','chat_conversations','chat_messages') and 'public'=any(roles)
  loop
    execute format('alter policy %I on %I.%I to authenticated',r.policyname,r.schemaname,r.tablename);
    if r.qual is not null then q:=replace(r.qual,'auth.uid()','(select auth.uid())'); execute format('alter policy %I on %I.%I using %s',r.policyname,r.schemaname,r.tablename,q); end if;
    if r.with_check is not null then wc:=replace(r.with_check,'auth.uid()','(select auth.uid())'); execute format('alter policy %I on %I.%I with check %s',r.policyname,r.schemaname,r.tablename,wc); end if;
  end loop;
end $$;
create index if not exists idx_health_events_user_date on public.health_events (user_id,event_date desc);
create index if not exists idx_menstrual_cycles_user_start on public.menstrual_cycles (user_id,start_date desc);
create index if not exists idx_symptoms_user_started on public.symptoms (user_id,started_at desc);
create index if not exists idx_medications_user_start on public.medications (user_id,start_date desc);
create index if not exists idx_medical_reports_user_date on public.medical_reports (user_id,report_date desc);
create index if not exists idx_activity_logs_user_date on public.activity_logs (user_id,activity_date desc);
create index if not exists idx_sleep_logs_user_date on public.sleep_logs (user_id,sleep_date desc);
create index if not exists idx_hydration_logs_user_time on public.hydration_logs (user_id,logged_at desc);
create index if not exists idx_weight_logs_user_time on public.weight_logs (user_id,logged_at desc);
create index if not exists idx_vital_signs_user_time on public.vital_signs (user_id,measured_at desc);
create index if not exists idx_mood_logs_user_time on public.mood_logs (user_id,logged_at desc);
create index if not exists idx_medical_conditions_user on public.medical_conditions (user_id);
create index if not exists idx_allergies_user on public.allergies (user_id);
create index if not exists idx_lab_results_user_date on public.lab_results (user_id,tested_at desc);
create index if not exists idx_doctor_visits_user_date on public.doctor_visits (user_id,visit_date desc);
create index if not exists idx_exercise_logs_user_time on public.exercise_logs (user_id,performed_at desc);
create index if not exists idx_user_preferences_user on public.user_preferences (user_id);
create index if not exists idx_chat_conversations_user_updated on public.chat_conversations (user_id,updated_at desc);
create index if not exists idx_chat_messages_user_created on public.chat_messages (user_id,created_at desc);
create index if not exists idx_chat_messages_conversation_created on public.chat_messages (conversation_id,created_at asc);
