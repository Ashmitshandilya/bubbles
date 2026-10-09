-- UNDO for supabase/migrations/20261010_bubbles_rename.sql. Run it ONLY if you must go back to the old (Coco-named) backend.
-- It lives outside supabase/migrations on purpose so it is never applied automatically.
-- Value-based, so it also reverts rows written after the rename (the old backend cannot read the new values).

do $$
declare r record;
begin
  for r in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind = 'r' and c.relname in ('bubbles_games', 'bubbles_preferences')
  loop
    execute format('alter table public.%I rename to %I', r.relname, replace(r.relname, 'bubbles', 'coco'));
  end loop;
  for r in select conrelid::regclass::text as tbl, conname from pg_constraint
           where connamespace = 'public'::regnamespace and conname ~ '^bubbles_(games|preferences)_'
  loop
    execute format('alter table %s rename constraint %I to %I', r.tbl, r.conname, replace(r.conname, 'bubbles', 'coco'));
  end loop;
  for r in select indexname from pg_indexes where schemaname = 'public' and indexname ~ '^bubbles_(games|preferences)_'
  loop
    execute format('alter index public.%I rename to %I', r.indexname, replace(r.indexname, 'bubbles', 'coco'));
  end loop;
  for r in select schemaname, tablename, policyname from pg_policies where schemaname = 'public' and policyname ilike '%bubbles%'
  loop
    execute format('alter policy %I on %I.%I rename to %I', r.policyname, r.schemaname, r.tablename,
                   replace(replace(r.policyname, 'Bubbles', 'Coco'), 'bubbles', 'coco'));
  end loop;
  update public.chat_messages set role = 'coco'            where role = 'bubbles';
  update public.health_events set event_type = 'coco_doc'   where event_type = 'bubbles_doc';
  update public.health_events set source = 'coco_feature'   where source = 'bubbles_feature';
  update public.health_events set source = 'coco_confirmed_extraction' where source = 'bubbles_confirmed_extraction';
  update public.rag_documents set source_name = replace(source_name, 'Bubbles editorial', 'Coco editorial') where source_name like 'Bubbles editorial%';
end $$;
