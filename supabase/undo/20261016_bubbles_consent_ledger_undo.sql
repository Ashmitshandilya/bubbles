-- Undo of 20261016_bubbles_consent_ledger.sql. WARNING: this deletes the consent history held in the table.
-- Export it first if you want to keep it:  select * from public.consent_events;
-- The app then goes back to keeping decisions as signed documents; the current choices are not lost (the newest row per purpose
-- is not copied back automatically, so people may be asked again).
begin;
drop trigger if exists bubbles_consent_events_guard on public.consent_events;
drop function if exists public.bubbles_consent_events_guard();
drop table if exists public.consent_events;
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    delete from public.bubbles_schema_migrations where name = '20261016_bubbles_consent_ledger';
  end if;
end $$;
commit;
