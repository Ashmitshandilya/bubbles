-- Bubbles: make every person's data hang off one account, and give analysis one place to read a person's day.
-- Apply ONCE in the Supabase SQL editor (Dashboard > SQL editor > New query > paste > Run). Safe to run twice.
-- Undo: supabase/undo/20261102_bubbles_data_links_undo.sql
--
-- 1. Every table that has a user_id gets a foreign key to auth.users(id) with ON DELETE CASCADE, where one is missing. Deleting an account then
--    removes everything that person logged, in one step, in any table (checked against the live table list on 2026-10-26).
--    Rows whose user no longer exists are removed first, because they could never be read again.
-- 2. public.bubbles_daily_facts: one row per person per day (UTC date) with sleep, mood, water and activity side by side, for analysis and for
--    the admin portal. It reads the real tables as the caller (security_invoker), and only the backend (service role) may select from it.
-- Nothing here changes RLS or grants on an existing table.

begin;

do $$
declare
  t text;
  tables text[] := array[
    'activity_logs', 'allergies', 'chat_conversations', 'chat_messages', 'community_bans', 'community_blocks', 'community_reactions',
    'consent_events', 'doctor_visits', 'exercise_logs', 'extracted_health_events', 'family_medical_history', 'health_events',
    'hydration_logs', 'lab_results', 'medical_conditions', 'medical_reports', 'medications', 'memory_items', 'menstrual_cycles',
    'mood_logs', 'notifications', 'ovulation_tests', 'pregnancy_tests', 'rl_arm_stats', 'rl_interactions', 'sleep_logs', 'supplements',
    'symptoms', 'user_preferences', 'vaccinations', 'vital_signs', 'weight_logs'];
begin
  foreach t in array tables loop
    -- skip a table that is not there, has no user_id, or already has a foreign key from user_id to auth.users
    if to_regclass('public.' || t) is null then continue; end if;
    if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = t and column_name = 'user_id') then continue; end if;
    if exists (
      select 1 from pg_constraint c
      join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any (c.conkey)
      where c.contype = 'f' and c.conrelid = ('public.' || t)::regclass and c.confrelid = 'auth.users'::regclass and a.attname = 'user_id') then continue;
    end if;
    -- consent_events is append-only by design (a trigger refuses deletes), so a cleanup of orphans is left to the owner
    if t <> 'consent_events' then
      execute format('delete from public.%I x where x.user_id is not null and not exists (select 1 from auth.users u where u.id = x.user_id)', t);
    end if;
    begin
      execute format('alter table public.%I add constraint %I foreign key (user_id) references auth.users (id) on delete cascade not valid', t, t || '_user_id_auth_fk');
      begin
        execute format('alter table public.%I validate constraint %I', t, t || '_user_id_auth_fk');
      exception when others then
        raise notice 'FK on % added but not validated yet (old orphan rows?): %', t, sqlerrm;
      end;
    exception when others then
      raise notice 'FK on % skipped: %', t, sqlerrm;
    end;
  end loop;
end $$;

create or replace view public.bubbles_daily_facts with (security_invoker = true) as
with days as (
  select user_id, (sleep_date)::date as day from public.sleep_logs
  union select user_id, (logged_at at time zone 'UTC')::date from public.mood_logs
  union select user_id, (logged_at at time zone 'UTC')::date from public.hydration_logs
  union select user_id, (activity_date at time zone 'UTC')::date from public.activity_logs
)
select
  d.user_id,
  d.day,
  (select round(sum(s.duration_minutes) / 60.0, 2) from public.sleep_logs s where s.user_id = d.user_id and s.sleep_date::date = d.day) as sleep_hours,
  (select round(avg(s.sleep_quality), 2) from public.sleep_logs s where s.user_id = d.user_id and s.sleep_date::date = d.day) as sleep_quality,
  (select round(avg(m.intensity), 2) from public.mood_logs m where m.user_id = d.user_id and (m.logged_at at time zone 'UTC')::date = d.day) as mood_intensity,
  (select sum(h.amount_ml) from public.hydration_logs h where h.user_id = d.user_id and (h.logged_at at time zone 'UTC')::date = d.day) as hydration_ml,
  (select sum(a.duration_minutes) from public.activity_logs a where a.user_id = d.user_id and (a.activity_date at time zone 'UTC')::date = d.day) as activity_minutes,
  (select sum(a.steps) from public.activity_logs a where a.user_id = d.user_id and (a.activity_date at time zone 'UTC')::date = d.day) as steps
from days d
where d.user_id is not null;

revoke all on public.bubbles_daily_facts from anon, authenticated;
grant select on public.bubbles_daily_facts to service_role;

-- register (the register table comes from 20261016_bubbles_schema_migrations; skipped if it is not there yet)
do $$
begin
  if to_regclass('public.bubbles_schema_migrations') is not null then
    insert into public.bubbles_schema_migrations (name) values ('20261102_bubbles_data_links') on conflict (name) do nothing;
  end if;
end $$;

commit;

-- Verify:
--   select conrelid::regclass as tbl, convalidated from pg_constraint where conname like '%_user_id_auth_fk' order by 1;
--   select * from public.bubbles_daily_facts limit 5;   -- run as the service role (SQL editor)
