-- Undo of 20261016_bubbles_rls_tightening.sql: gives browsers back the write access they had (the state before the tightening).
begin;
do $$
declare t text;
begin
  foreach t in array array['health_events','menstrual_cycles','symptoms','medications','medical_reports','activity_logs','sleep_logs',
    'hydration_logs','weight_logs','vital_signs','mood_logs','medical_conditions','allergies','lab_results','doctor_visits',
    'exercise_logs','user_preferences','chat_conversations','chat_messages','extracted_health_events','memory_items'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop policy if exists "coco_owner_read" on public.%I', t);
      execute format('drop policy if exists "coco_owner_all" on public.%I', t);
      execute format('create policy "coco_owner_all" on public.%I for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id)', t);
      execute format('grant insert, update, delete on table public.%I to authenticated', t);
    end if;
  end loop;
end $$;
do $$
begin
  if to_regclass('public.profiles') is not null then
    drop policy if exists "coco_profile_owner_read" on public.profiles;
    drop policy if exists "coco_profile_owner" on public.profiles;
    create policy "coco_profile_owner" on public.profiles for all to authenticated using (auth.uid() = id) with check (auth.uid() = id);
    grant insert, update, delete on table public.profiles to authenticated;
  end if;
  if to_regclass('public.health_events') is not null then
    drop policy if exists bubbles_doc_backend_only on public.health_events;
  end if;
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_rls_tightening';
  end if;
end $$;
commit;
