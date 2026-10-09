-- ============================================================================================
-- PROPOSAL ONLY — NOT APPLIED. Bubbles "Whole-Health OS" schema proposal.
-- Nothing in the application requires this file: until it is approved and applied, every new feature
-- stores its data as owner-scoped, server-signed JSON documents in the existing public.health_events table
-- (event_type = 'bubbles_doc', title = '<kind>:<key>', data = {kind, key, payload, version, sig}; see backend/doc_store.py).
-- That works with the live schema today and survives this migration: backend/doc_store.py can be
-- pointed at these tables later by a one-file change, and a one-off script can copy the documents over.
--
-- Why propose tables at all?  Relational tables give: real constraints, indexes for the heavy ones
-- (food/exercise logs), cheaper range queries, and easier export/delete. Review and adjust before applying.
-- Conventions copied from the existing migrations: RLS enabled, owner-scoped SELECT for authenticated users,
-- all writes by the trusted backend (service_role), no anon access, updated_at triggers.
-- After approval, validate each insert/select shape against the live database with the "ghost user"
-- technique (insert with a random non-existent user_id; the FK rejects it after Postgres validated
-- columns/types/constraints, so nothing is written).
-- ============================================================================================

-- 0. helper (idempotent) ---------------------------------------------------------------------
create or replace function public.bubbles_touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

-- 1. body profile & goals (extends what profiles/user_preferences hold) ---------------------------
-- Why not profiles/user_preferences: user_preferences has no id column and no typed fields; profiles is auth-adjacent.
create table if not exists public.body_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  birth_date date,
  height_cm numeric(5,1) check (height_cm between 120 and 230),
  formula_basis text check (formula_basis in ('male','female','average')),
  activity_level text check (activity_level in ('sedentary','light','moderate','very_active','extra_active')),
  units text not null default 'metric' check (units in ('metric','imperial')),
  diet_style text,                       -- veg, vegan, eggetarian, jain, halal, none ...
  cuisines text[] not null default '{}',
  liked_foods text[] not null default '{}',
  disliked_foods text[] not null default '{}',
  equipment text[] not null default '{}',
  budget text, cooking_minutes int, fasting_practice text,
  eating_screen_positive boolean not null default false,   -- SCOFF >= 2 (kept as a flag, not the answers)
  clinician_cleared_until date,                            -- strict-mode clearance acknowledgement
  extra jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- 2. food catalogue and logs -----------------------------------------------------------------------
create table if not exists public.food_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references auth.users(id) on delete cascade,  -- null = shared reference food
  name text not null, aliases text[] not null default '{}',
  serving_desc text not null, serving_grams numeric(7,1),
  kcal numeric(7,1) not null, protein_g numeric(6,1), carbs_g numeric(6,1), fat_g numeric(6,1),
  fibre_g numeric(6,1), sugar_g numeric(6,1), sodium_mg numeric(7,1),
  micros jsonb not null default '{}'::jsonb,                 -- iron, calcium, b12, vit d, folate ...
  source text not null, verified boolean not null default false, licence text,
  created_at timestamptz not null default now()
);
create index if not exists food_items_name_idx on public.food_items using gin (to_tsvector('simple', name));

create table if not exists public.food_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  meal text check (meal in ('breakfast','lunch','dinner','snack')),
  description text not null,
  items jsonb not null default '[]'::jsonb,                  -- resolved items with portion + nutrient snapshot
  kcal_low numeric(7,1), kcal numeric(7,1) not null, kcal_high numeric(7,1),
  protein_g numeric(6,1), carbs_g numeric(6,1), fat_g numeric(6,1), fibre_g numeric(6,1),
  confidence text check (confidence in ('exact','reference','estimate')),
  source text not null default 'user_logged'
);
create index if not exists food_logs_user_time on public.food_logs (user_id, logged_at desc);

-- 3. plans -----------------------------------------------------------------------------------------
create table if not exists public.transformation_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null check (status in ('draft','active','paused','completed','cancelled')),
  mode text not null check (mode in ('gentle','strict')),
  start_weight_kg numeric(5,1) not null, target_weight_kg numeric(5,1) not null,
  start_date date not null, pace_pct_per_week numeric(4,2), daily_kcal numeric(6,1),
  targets jsonb not null default '{}'::jsonb,
  screening jsonb not null default '{}'::jsonb,              -- screening answers + decision (versioned)
  acknowledged_at timestamptz, constants_version text,        -- ties the plan to a reviewed constants version
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.plan_versions (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.transformation_plans(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(), reason text, snapshot jsonb not null
);
create table if not exists public.meal_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_id uuid references public.transformation_plans(id) on delete set null,
  week_start date not null, days jsonb not null, locked jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create table if not exists public.workout_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_id uuid references public.transformation_plans(id) on delete set null,
  week_start date not null, sessions jsonb not null, week_index int not null default 1,
  created_at timestamptz not null default now()
);
create table if not exists public.workout_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  done_at timestamptz not null default now(), title text not null, minutes int,
  rpe numeric(3,1), sets jsonb not null default '[]'::jsonb, kcal_estimate numeric(6,1), notes text
);

-- 4. cycle -----------------------------------------------------------------------------------------
create table if not exists public.cycle_day_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  log_date date not null,
  flow text check (flow in ('none','spotting','light','medium','heavy')),
  factors jsonb not null default '{}'::jsonb,                 -- chips: pain, mood, body, discharge, tests ...
  bbt_c numeric(4,2) check (bbt_c between 34 and 40),
  notes text, unique (user_id, log_date)
);
create table if not exists public.cycle_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  mode text not null default 'track' check (mode in ('track','birth_control','conceive','pregnancy','postpartum','perimenopause')),
  mode_since date, luteal_days int, privacy jsonb not null default '{}'::jsonb, partner_share jsonb not null default '{}'::jsonb
);

-- 5. medications schedule -----------------------------------------------------------------------------
create table if not exists public.medication_schedules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  medication_id uuid references public.medications(id) on delete set null,
  name text not null, dose text, times jsonb not null default '[]'::jsonb, days text[] not null default '{}',
  as_needed boolean not null default false, pill_count int, refill_alert_at int, starts_on date, ends_on date, notes text
);
create table if not exists public.medication_doses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  schedule_id uuid references public.medication_schedules(id) on delete cascade,
  due_at timestamptz not null, status text not null check (status in ('taken','skipped','snoozed','missed')),
  skip_reason text, taken_at timestamptz
);

-- 6. notifications (in-app first; push/email optional) -------------------------------------------------------
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null, title text not null, body text,        -- body must stay generic (no health values)
  created_at timestamptz not null default now(), read_at timestamptz, channel text not null default 'in_app'
);
create table if not exists public.notification_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  channels jsonb not null default '{"in_app":true}'::jsonb, quiet_hours jsonb, daily_cap int not null default 5,
  push_subscription jsonb, email text
);

-- 7. RLS + grants (same pattern as 20261006_coco_service_role_grants.sql) --------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['body_profiles','food_items','food_logs','transformation_plans','plan_versions','meal_plans',
    'workout_plans','workout_sessions','cycle_day_logs','cycle_settings','medication_schedules','medication_doses',
    'notifications','notification_settings'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on table public.%I from anon, authenticated', t);
    execute format('grant select on table public.%I to authenticated', t);
    execute format('grant all on table public.%I to service_role', t);
  end loop;
end $$;

-- owner-scoped read policies (writes only via the backend)
create policy body_profiles_read on public.body_profiles for select to authenticated using (user_id = auth.uid());
create policy food_logs_read on public.food_logs for select to authenticated using (user_id = auth.uid());
create policy food_items_read on public.food_items for select to authenticated using (owner_id is null or owner_id = auth.uid());
create policy transformation_plans_read on public.transformation_plans for select to authenticated using (user_id = auth.uid());
create policy plan_versions_read on public.plan_versions for select to authenticated using (user_id = auth.uid());
create policy meal_plans_read on public.meal_plans for select to authenticated using (user_id = auth.uid());
create policy workout_plans_read on public.workout_plans for select to authenticated using (user_id = auth.uid());
create policy workout_sessions_read on public.workout_sessions for select to authenticated using (user_id = auth.uid());
create policy cycle_day_logs_read on public.cycle_day_logs for select to authenticated using (user_id = auth.uid());
create policy cycle_settings_read on public.cycle_settings for select to authenticated using (user_id = auth.uid());
create policy medication_schedules_read on public.medication_schedules for select to authenticated using (user_id = auth.uid());
create policy medication_doses_read on public.medication_doses for select to authenticated using (user_id = auth.uid());
create policy notifications_read on public.notifications for select to authenticated using (user_id = auth.uid());
create policy notification_settings_read on public.notification_settings for select to authenticated using (user_id = auth.uid());

create trigger body_profiles_touch before update on public.body_profiles for each row execute function public.bubbles_touch_updated_at();
create trigger transformation_plans_touch before update on public.transformation_plans for each row execute function public.bubbles_touch_updated_at();
