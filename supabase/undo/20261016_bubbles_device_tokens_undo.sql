-- Undo for supabase/migrations/20261016_bubbles_device_tokens.sql. Removes the phone-token table and its rows.
-- The API keeps working afterwards (push registration answers "not ready"; in-app reminders are unchanged).
begin;
drop table if exists public.device_tokens;
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_device_tokens';
  end if;
end $$;
commit;
