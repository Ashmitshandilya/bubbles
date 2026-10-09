-- Coco baseline: the 20 canonical tables exactly as they exist in the live
-- Supabase project (captured 2026-10-06 from pg_catalog), plus the
-- extracted_health_events staging table that health_events references.
--
-- Why this file exists: the earlier repo migration
-- (20260919_coco_storage_reconciliation.sql) described different columns than
-- production (profiles.full_name vs live display_name, health_events.occurred_at
-- vs live event_date, ...), so a fresh install built a schema the backend could
-- not use. The live schema is the source of truth; every statement here is
-- `if not exists`, so applying it to the live project is a no-op.
--
-- RLS enablement and owner policies are applied by the later reconciliation
-- migration; privileges by 20261006_coco_service_role_grants.sql.

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  date_of_birth date,
  height_cm numeric,
  gender text,
  timezone text default 'Asia/Kolkata',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chat_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.chat_conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null,
  content text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  client_message_id text
);

create table if not exists public.extracted_health_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  message_id uuid,
  event_type text not null,
  extracted_data jsonb not null default '{}'::jsonb,
  confidence numeric,
  extraction_status text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.health_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null,
  event_date timestamptz not null default now(),
  title text,
  description text,
  data jsonb default '{}'::jsonb,
  source text,
  confidence numeric,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  source_extracted_event_id uuid references public.extracted_health_events(id) on delete set null,
  source_message_id uuid references public.chat_messages(id) on delete set null
);

create table if not exists public.menstrual_cycles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  start_date date not null,
  end_date date,
  cycle_length_days integer,
  period_length_days integer,
  flow_notes text,
  symptoms jsonb default '[]'::jsonb,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.symptoms (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  symptom_name text not null,
  severity integer check (severity >= 1 and severity <= 10),
  started_at timestamptz,
  ended_at timestamptz,
  notes text,
  body_location text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.medications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  medication_name text not null,
  dosage text,
  frequency text,
  start_date date,
  end_date date,
  reason text,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.medical_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  report_name text not null,
  report_type text,
  report_date date,
  doctor_name text,
  hospital_name text,
  file_path text,
  extracted_text text,
  extracted_data jsonb default '{}'::jsonb,
  processing_status text default 'pending',
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.activity_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  activity_date timestamptz not null default now(),
  activity_type text not null,
  duration_minutes integer,
  distance_km numeric,
  calories_burned numeric,
  steps integer,
  intensity text,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.sleep_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  sleep_date date not null,
  bedtime timestamptz,
  wake_time timestamptz,
  duration_minutes integer,
  sleep_quality integer check (sleep_quality >= 1 and sleep_quality <= 10),
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.hydration_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  amount_ml integer not null,
  drink_type text default 'water',
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.weight_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  weight_kg numeric not null,
  body_fat_percent numeric,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.vital_signs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  measured_at timestamptz not null default now(),
  heart_rate_bpm integer,
  systolic_bp integer,
  diastolic_bp integer,
  temperature_c numeric,
  spo2_percent numeric,
  respiratory_rate integer,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.mood_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  mood text not null,
  intensity integer check (intensity >= 1 and intensity <= 10),
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.medical_conditions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  condition_name text not null,
  status text default 'active',
  diagnosed_date date,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.allergies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  allergen text not null,
  reaction text,
  severity text,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.lab_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  medical_report_id uuid references public.medical_reports(id) on delete set null,
  test_name text not null,
  value numeric,
  unit text,
  reference_min numeric,
  reference_max numeric,
  abnormal_flag text,
  tested_at timestamptz,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.doctor_visits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  visit_date timestamptz not null default now(),
  doctor_name text,
  specialty text,
  reason text,
  diagnosis text,
  notes text,
  recommendations text,
  medical_report_id uuid references public.medical_reports(id) on delete set null,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.exercise_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  performed_at timestamptz not null default now(),
  exercise_name text not null,
  duration_minutes integer,
  sets integer,
  reps integer,
  weight_kg numeric,
  calories_burned numeric,
  intensity text,
  notes text,
  source text,
  user_confirmed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  units_system text default 'metric',
  language text default 'en',
  notifications_enabled boolean default true,
  hydration_reminders boolean default true,
  cycle_reminders boolean default true,
  weekly_reports boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
