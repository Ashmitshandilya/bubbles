-- Undo for 20261101_bubbles_playbook.sql: removes the Playbook tables and their register line. Nothing else is touched.
begin;
drop table if exists public.bubbles_playbook;
drop table if exists public.bubbles_playbook_candidates;
delete from public.bubbles_schema_migrations where name = '20261101_bubbles_playbook';
commit;
