-- Undo for 20261102_bubbles_data_links: drops the daily view and the foreign keys this migration added (only those named *_user_id_auth_fk).
-- Rows that the migration deleted because their person no longer existed cannot be restored.
begin;

drop view if exists public.bubbles_daily_facts;

do $$
declare r record;
begin
  for r in
    select c.conrelid::regclass as tbl, c.conname
    from pg_constraint c where c.contype = 'f' and c.conname like '%\_user\_id\_auth\_fk'
  loop
    execute format('alter table %s drop constraint %I', r.tbl, r.conname);
  end loop;
end $$;

delete from public.bubbles_schema_migrations where name = '20261102_bubbles_data_links';

commit;
