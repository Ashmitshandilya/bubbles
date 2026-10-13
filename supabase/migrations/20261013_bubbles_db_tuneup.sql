-- Bubbles database tune-up: archive the dead tables, link every user-owned table to its user, index every link.
--
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run), after reading it.
-- The result grid lists every action taken and every table skipped, with the reason. Undo: supabase/undo/20261013_bubbles_db_tuneup_undo.sql
--
-- Finding (live audit 2026-10-13): public held 248 tables; the app (backend + frontend) uses 34. The rest are empty
-- dashboard-era tables the backend cannot even read (no service_role grant). They clutter the API schema and the RLS surface.
--
-- 1. Archive: every public table NOT in the keep list below moves to schema "archive" (not dropped; rows, indexes, policies
--    and constraints move with it). A table is left in public, and reported, if it has any row, if a kept table points to it,
--    if a view depends on it, or if any public function mentions its name (e.g. a signup trigger) - so nothing live breaks.
-- 2. Link: every kept table with a uuid user_id (rag_documents: owner_user_id) and no foreign key on it gets
--    references auth.users(id) on delete cascade, the convention the baseline schema already uses. Skipped, and reported,
--    if existing rows point to users that no longer exist.
-- 3. Index: every foreign key column in a kept table gets an index if none leads with it (cascades and RLS user_id filters).
begin;

create temp table _tuneup (step text, tbl text, detail text) on commit preserve rows;
create schema if not exists archive;
revoke all on schema archive from public, anon, authenticated;

do $$
declare
  keep text[] := array[
    'activity_logs','allergies','bubbles_admin_settings','bubbles_ops_events','chat_conversations','chat_messages',
    'doctor_visits','exercise_logs','extracted_health_events','family_medical_history','health_events','hydration_logs',
    'lab_results','medical_conditions','medical_reports','medications','memory_items','menstrual_cycles','mood_logs',
    'notifications','ovulation_tests','pregnancy_tests','profiles','rag_chunks','rag_documents','rl_arm_stats',
    'rl_interactions','sleep_logs','supplements','symptoms','user_preferences','vaccinations','vital_signs','weight_logs'];
  r record; n bigint; why text;
begin
  -- 1. archive
  for r in select c.oid, c.relname from pg_class c join pg_namespace s on s.oid = c.relnamespace
           where s.nspname = 'public' and c.relkind in ('r', 'p') and not c.relispartition and c.relname <> all(keep)
           order by c.relname loop
    execute format('select count(*) from public.%I', r.relname) into n;
    why := case
      when n > 0 then n || ' rows'
      when exists (select 1 from pg_constraint k join pg_class f on f.oid = k.conrelid
                   where k.contype = 'f' and k.confrelid = r.oid and f.oid <> r.oid
                     and f.relnamespace = 'public'::regnamespace and f.relname = any(keep)) then 'a kept table references it'
      when exists (select 1 from pg_depend d join pg_rewrite w on w.oid = d.objid
                   where d.refobjid = r.oid and w.ev_class <> r.oid) then 'a view depends on it'
      when exists (select 1 from pg_proc p where p.pronamespace = 'public'::regnamespace
                     and p.prosrc ~* ('\m' || r.relname || '\M')) then 'a public function mentions it'
    end;
    if why is null then
      execute format('alter table public.%I set schema archive', r.relname);
      insert into _tuneup values ('archived', r.relname, '');
    else
      insert into _tuneup values ('kept in public', r.relname, why);
    end if;
  end loop;

  -- 2. link user-owned rows to their user
  for r in select c.oid, c.relname, a.attnum, a.attname from pg_class c join pg_attribute a on a.attrelid = c.oid
           where c.relnamespace = 'public'::regnamespace and c.relname = any(keep) and not a.attisdropped
             and a.atttypid = 'uuid'::regtype
             and (a.attname = 'user_id' or (c.relname, a.attname) = ('rag_documents', 'owner_user_id'))
             and not exists (select 1 from pg_constraint k where k.contype = 'f' and k.conrelid = c.oid and k.conkey = array[a.attnum])
           order by c.relname loop
    execute format('select count(*) from public.%I x where x.%I is not null and not exists (select 1 from auth.users u where u.id = x.%I)',
                   r.relname, r.attname, r.attname) into n;
    if n > 0 then
      insert into _tuneup values ('NOT linked', r.relname, n || ' rows point to deleted users; clean them, then re-run');
    else
      execute format('alter table public.%I add constraint %I foreign key (%I) references auth.users(id) on delete cascade',
                     r.relname, r.relname || '_' || r.attname || '_auth_fkey', r.attname);
      insert into _tuneup values ('linked', r.relname, r.attname || ' -> auth.users.id (on delete cascade)');
    end if;
  end loop;

  -- 3. index every foreign key column
  for r in select c.relname, a.attname from pg_constraint k join pg_class c on c.oid = k.conrelid
           join pg_attribute a on a.attrelid = c.oid and a.attnum = k.conkey[1]
           where k.contype = 'f' and c.relnamespace = 'public'::regnamespace and c.relname = any(keep)
             and not exists (select 1 from pg_index i where i.indrelid = c.oid and i.indkey[0] = k.conkey[1])
           order by 1, 2 loop
    execute format('create index if not exists %I on public.%I (%I)', r.relname || '_' || r.attname || '_fk_idx', r.relname, r.attname);
    insert into _tuneup values ('indexed', r.relname, r.attname);
  end loop;
end $$;

commit;

notify pgrst, 'reload schema';

select step, count(*) as tables, string_agg(tbl || coalesce(nullif(' (' || detail || ')', ' ()'), ''), ', ' order by tbl) as detail
from _tuneup group by step order by step;
