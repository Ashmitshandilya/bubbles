-- Undo for supabase/migrations/20261013_bubbles_db_tuneup.sql. Moves every archived table back to public and drops the
-- user links and indexes that migration added (named *_auth_fkey and *_fk_idx). No row is touched.
begin;
do $$
declare r record;
begin
  for r in select c.relname from pg_class c where c.relnamespace = 'archive'::regnamespace and c.relkind in ('r', 'p') loop
    execute format('alter table archive.%I set schema public', r.relname);
  end loop;
  for r in select conrelid::regclass as t, conname from pg_constraint
           where contype = 'f' and connamespace = 'public'::regnamespace and conname like '%\_auth\_fkey' loop
    execute format('alter table %s drop constraint %I', r.t, r.conname);
  end loop;
  for r in select indexrelid::regclass as i from pg_index x join pg_class c on c.oid = x.indexrelid
           where c.relnamespace = 'public'::regnamespace and c.relname like '%\_fk\_idx' loop
    execute format('drop index %s', r.i);
  end loop;
end $$;
drop schema if exists archive;
commit;
notify pgrst, 'reload schema';
