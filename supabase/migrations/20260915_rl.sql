-- Coco RL / contextual-bandit foundation.
-- RL is restricted to low-risk personalization and recommendation ranking.

create table if not exists public.rl_interactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  arm_key text not null,
  context jsonb not null default '{}'::jsonb,
  policy_score double precision not null default 0,
  propensity double precision not null default 1,
  safety_level text not null default 'GREEN',
  feedback text null,
  reward double precision null,
  policy_version text not null default 'coco-bandit-v1',
  decision_mode text not null default 'contextual_bandit',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.rl_arm_stats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  arm_key text not null,
  impressions integer not null default 0,
  reward_sum double precision not null default 0,
  updated_at timestamptz not null default now(),
  unique(user_id, arm_key)
);

-- Safe to run against the first RL migration as well.
alter table public.rl_interactions add column if not exists policy_version text not null default 'coco-bandit-v1';
alter table public.rl_interactions add column if not exists decision_mode text not null default 'contextual_bandit';
alter table public.rl_interactions add column if not exists updated_at timestamptz not null default now();

alter table public.rl_interactions enable row level security;
alter table public.rl_arm_stats enable row level security;

drop policy if exists "Users can manage their own RL interactions" on public.rl_interactions;
create policy "Users can manage their own RL interactions"
on public.rl_interactions
for all
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users can manage their own RL arm stats" on public.rl_arm_stats;
create policy "Users can manage their own RL arm stats"
on public.rl_arm_stats
for all
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create index if not exists idx_rl_interactions_user_created
on public.rl_interactions(user_id, created_at desc);

create index if not exists idx_rl_interactions_user_arm
on public.rl_interactions(user_id, arm_key);

create index if not exists idx_rl_interactions_policy_version
on public.rl_interactions(policy_version);
