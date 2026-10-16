-- Bubbles: OPTIONAL hardening, OFF BY DEFAULT. Nothing in the app needs this to run; apply it deliberately, when you are ready.
-- Apply in the Supabase SQL editor after reading the "Before you run it" checks. Safe to run twice.
-- Undo: supabase/undo/20261016_bubbles_rls_tightening_undo.sql
--
-- What it fixes: 20260919_coco_storage_reconciliation.sql gave every signed-in browser a FOR ALL policy ("coco_owner_all") on its own rows
-- of health_events and the tracker tables, so a browser could insert, edit or delete them straight through the database API, including
-- rows marked user_confirmed = true and signed documents of type bubbles_doc (such as consent records). That file also sorts AFTER
-- 20260919_coco_r7_chat_write_authority.sql, so on a database built by replaying the files in order it brings the write policy back on the
-- chat tables too.
--
-- What it does: browsers keep READ access to their own rows and lose INSERT / UPDATE / DELETE. It also hides bubbles_doc rows from
-- browsers completely. The backend uses the service key (it skips RLS), so nothing in Bubbles changes. The website never calls these
-- tables: it only uses Supabase for sign-in (checked: the only supabase.* calls in frontend/app, components and lib are supabase.auth.*).
--
-- Before you run it:
--   1. Nobody has a tool of their own that writes to these tables with a user login. (If you do, it will stop working.)
--   2. select polname, polcmd from pg_policy where polrelid = 'public.health_events'::regclass;   -- note what is there today
--   3. Keep the undo file at hand.

begin;

do $$
declare t text;
begin
  foreach t in array array['health_events','menstrual_cycles','symptoms','medications','medical_reports','activity_logs','sleep_logs',
    'hydration_logs','weight_logs','vital_signs','mood_logs','medical_conditions','allergies','lab_results','doctor_visits',
    'exercise_logs','user_preferences','chat_conversations','chat_messages','extracted_health_events','memory_items'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop policy if exists "coco_owner_all" on public.%I', t);
      execute format('drop policy if exists "coco_owner_read" on public.%I', t);
      execute format('create policy "coco_owner_read" on public.%I for select to authenticated using ((select auth.uid()) = user_id)', t);
      execute format('revoke insert, update, delete on table public.%I from authenticated', t);
    end if;
  end loop;
end $$;

do $$
begin
  if to_regclass('public.profiles') is not null then
    drop policy if exists "coco_profile_owner" on public.profiles;
    drop policy if exists "coco_profile_owner_read" on public.profiles;
    create policy "coco_profile_owner_read" on public.profiles for select to authenticated using ((select auth.uid()) = id);
    revoke insert, update, delete on table public.profiles from authenticated;
  end if;
end $$;

-- Signed documents (consent records, plans, notifications, partner links) are for the backend only: browsers do not see them at all.
do $$
begin
  if to_regclass('public.health_events') is not null then
    drop policy if exists bubbles_doc_backend_only on public.health_events;
    create policy bubbles_doc_backend_only on public.health_events as restrictive for select to authenticated using (event_type <> 'bubbles_doc');
  end if;
end $$;

commit;

do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261016_bubbles_rls_tightening') on conflict (name) do nothing;
  end if;
end $$;

-- Verify (three queries):
--   1. select tablename, policyname, cmd from pg_policies where schemaname = 'public' and policyname in ('coco_owner_all', 'coco_owner_read');
--        -- expect: no coco_owner_all rows; one select policy per table
--   2. select grantee, privilege_type from information_schema.role_table_grants
--        where table_schema = 'public' and table_name = 'health_events' and grantee = 'authenticated';          -- expect: SELECT only
--   3. select polname, polcmd, polpermissive from pg_policy where polrelid = 'public.health_events'::regclass;  -- expect: bubbles_doc_backend_only, restrictive
