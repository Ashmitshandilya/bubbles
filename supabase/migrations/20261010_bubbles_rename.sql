-- Coco -> Bubbles rename. Idempotent: safe to run twice. NOT applied automatically.
--
-- ORDER OF OPERATIONS (important):
--   1. Back up / confirm you are on the intended project.
--   2. Run this script once in the Supabase SQL editor.
--   3. THEN start the renamed backend (it reads bubbles_* tables and the new role / event_type / source values).
-- Running the renamed backend before this script makes the games, preferences and stored feature documents invisible
-- until the script runs. Nothing is deleted: tables, constraints, indexes and policies are renamed, and four value
-- columns are rewritten (counts are printed at the end).
--
-- Deliberately NOT changed: rl_interactions.policy_version default 'coco-bandit-v1' (existing bandit statistics key on it),
-- past chat message text, and historical migration file names (they are the audit trail of what was applied).

begin;

-- 1. tables (rename keeps data, foreign keys and grants)
do $$
declare r record;
begin
  for r in
    select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r' and c.relname ~ '(^|_)coco(_|$)'
  loop
    execute format('alter table public.%I rename to %I', r.relname, regexp_replace(r.relname, '(^|_)coco(_|$)', '\1bubbles\2'));
  end loop;
end $$;

-- 2. constraints (renaming a primary key / unique constraint also renames its index)
do $$
declare r record;
begin
  for r in
    select conrelid::regclass::text as tbl, conname from pg_constraint
    where connamespace = 'public'::regnamespace and conname ~ '(^|_)coco(_|$)'
  loop
    execute format('alter table %s rename constraint %I to %I', r.tbl, r.conname, regexp_replace(r.conname, '(^|_)coco(_|$)', '\1bubbles\2'));
  end loop;
end $$;

-- 3. remaining indexes
do $$
declare r record;
begin
  for r in select indexname from pg_indexes where schemaname = 'public' and indexname ~ '(^|_)coco(_|$)'
  loop
    execute format('alter index public.%I rename to %I', r.indexname, regexp_replace(r.indexname, '(^|_)coco(_|$)', '\1bubbles\2'));
  end loop;
end $$;

-- 4. policies (names only; their rules are unchanged)
do $$
declare r record;
begin
  for r in select schemaname, tablename, policyname from pg_policies where schemaname = 'public' and policyname ilike '%coco%'
  loop
    execute format('alter policy %I on %I.%I rename to %I', r.policyname, r.schemaname, r.tablename,
                   replace(replace(replace(r.policyname, 'Coco', 'Bubbles'), 'coco', 'bubbles'), 'COCO', 'BUBBLES'));
  end loop;
end $$;

-- 5. values the application writes and filters on
update public.chat_messages  set role = 'bubbles'            where role = 'coco';
update public.health_events  set event_type = 'bubbles_doc'   where event_type = 'coco_doc';
update public.health_events  set source = 'bubbles_feature'   where source = 'coco_feature';
update public.health_events  set source = 'bubbles_confirmed_extraction' where source = 'coco_confirmed_extraction';
update public.rag_documents  set source_name = replace(source_name, 'Coco editorial', 'Bubbles editorial') where source_name like 'Coco editorial%';

-- 6. report (read the output: every "left" number should be 0)
select
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' and c.relname ~ '(^|_)coco(_|$)') as tables_left,
  (select count(*) from public.chat_messages where role = 'coco')           as chat_roles_left,
  (select count(*) from public.health_events where event_type = 'coco_doc') as feature_docs_left,
  (select count(*) from public.health_events where source in ('coco_feature', 'coco_confirmed_extraction')) as event_sources_left,
  (select count(*) from public.rag_documents where source_name like 'Coco editorial%') as rag_sources_left,
  (select count(*) from public.health_events where event_type = 'bubbles_doc') as feature_docs_now;

commit;
