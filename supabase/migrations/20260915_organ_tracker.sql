-- COCO Organ Tracker foundation.
-- Scores are derived snapshots, not diagnoses. Keep source provenance.

create table if not exists public.organ_assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  organ_code text not null,
  score numeric null check (score is null or (score >= 0 and score <= 100)),
  score_semantics text not null default 'risk_context_indicator'
    check (score_semantics = 'risk_context_indicator'),
  status text not null,
  confidence numeric not null check (confidence >= 0 and confidence <= 1),
  data_completeness numeric not null check (data_completeness >= 0 and data_completeness <= 1),
  signals jsonb not null default '[]'::jsonb,
  interactions jsonb not null default '[]'::jsonb,
  recommended_actions jsonb not null default '[]'::jsonb,
  limitations jsonb not null default '[]'::jsonb,
  source_event_ids uuid[] not null default '{}',
  evidence_version text not null default 'organ-v2',
  created_at timestamptz not null default now(),
  expires_at timestamptz null
);

create index if not exists organ_assessments_user_organ_idx
  on public.organ_assessments(user_id, organ_code, created_at desc);

alter table public.organ_assessments enable row level security;

drop policy if exists "Users can read their organ assessments" on public.organ_assessments;
create policy "Users can read their organ assessments"
  on public.organ_assessments
  for select
  to authenticated
  using (auth.uid() = user_id);

-- Writes should be performed by the trusted backend in production.
revoke insert, update, delete on public.organ_assessments from authenticated;
