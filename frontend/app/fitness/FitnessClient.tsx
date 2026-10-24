"use client";

import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { BTN_PRIMARY, SECTION, ErrorCard, Icon, Skeleton, TONE, useBubblesQuery, type Tone } from "../../components/hub/HubKit";
import { ClinicalNote, Disclaimer, EstimateLabel, FitnessPage, MacroBars, PageHeading, Pill, ProgressRing, RangeBadge, Section } from "../../components/fitness/ui";
import { useUnits } from "../../components/fitness/useUnits";
import { cardState, fmt, formatWeeks, formatWeight, ringFraction, ringWord } from "../lib/fitness-calc";
import type { Summary } from "../lib/fitness-types";

export function FitnessClient() {
  return (
    <FitnessPage title="Fitness">
      <Hub />
    </FitnessPage>
  );
}

function Hub() {
  const [q, reload] = useBubblesQuery<Summary>("/fitness/summary");
  const units = useUnits();

  if (q.status === "loading")
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading your fitness summary">
        <Skeleton className="h-10 w-1/2 rounded-2xl" />
        <Skeleton className="h-56 w-full rounded-3xl" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-36 rounded-3xl" />
          <Skeleton className="h-36 rounded-3xl" />
        </div>
      </div>
    );
  if (q.status === "error") return <ErrorCard title="Couldn't load Fitness" message={q.message} onRetry={reload} />;

  const s = q.data;
  const t = s.targets;
  const state = { has_diet_plan: s.has_diet_plan, has_workout_plan: s.has_workout_plan, entries: s.entries, transform: s.transform, hasTargets: t !== null };
  const cards: { kind: "diet" | "workouts" | "calories" | "transform"; href: string; title: string; text: string; tone: Tone; icon: string }[] = [
    { kind: "diet", href: "/fitness/diet", title: "Diet planner", text: "A week of meals that fit your food, allergies and numbers, with swaps and a grocery list.", tone: "mint", icon: "nutrition" },
    { kind: "workouts", href: "/fitness/workouts", title: "Workouts", text: "A gentle weekly plan that adapts to your energy, sleep and any sore spots.", tone: "peach", icon: "activity" },
    { kind: "calories", href: "/fitness/calories", title: "Calorie calculator", text: "Say what you ate in your own words. Bubbles turns it into an estimate you confirm.", tone: "sun", icon: "weight" },
    { kind: "transform", href: "/fitness/transform", title: "Strict transformation", text: "A structured, safety-checked plan toward a target weight. Careful screening first.", tone: "grape", icon: "sparkle" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeading kicker="Fitness" title="Your day, gently" text="Everything here is an estimate that moves with you. Close is good enough." />

      {t === null && (
        <section className="flex flex-wrap items-center gap-5 border-b border-[color:var(--hairline)] pb-6" aria-labelledby="onboard">
          <BubblesMascot size={56} mood="happy" animated={false} />
          <div className="min-w-[14rem] flex-1">
            <h2 id="onboard" className="m-0 font-display text-h3 text-ink">Let&rsquo;s set up your numbers</h2>
            <p className="m-0 mt-1 text-body-sm text-ink-soft">{s.message ?? "Add a few details so Bubbles can work out calories, protein and water for you."}</p>
          </div>
          <Link href="/fitness/setup" className={`${BTN_PRIMARY} no-underline`}>
            Add my details
          </Link>
        </section>
      )}

      {s.readiness && (
        <Section title="How ready you look today">
          <p className="m-0 font-display text-h3 text-ink">{s.readiness.label}</p>
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0 text-body-sm text-muted">
            {s.readiness.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
          <p className="m-0 mt-2 text-body-sm text-muted">A guide to effort from your own logs, not a medical check. How you feel comes first.</p>
        </Section>
      )}

      {t !== null && s.budget && (
        <Section title="Today" aside={<EstimateLabel />}>
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
            <ProgressRing
              fraction={ringFraction(s.budget.eaten_kcal, s.budget.budget_kcal)}
              label={`${fmt(s.budget.eaten_kcal)} of about ${fmt(s.budget.budget_kcal)} kilocalories eaten today (estimate)`}
              tone="mint"
            >
              <span className="font-display text-metric text-ink">{s.intake_logged === false ? "–" : fmt(s.budget.eaten_kcal)}</span>
              <span className="text-body-sm text-muted">of about {fmt(s.budget.budget_kcal)} kcal</span>
            </ProgressRing>
            <div className="w-full min-w-0 flex-1">
              <p className="m-0 mb-1 text-body font-extrabold text-ink" aria-live="polite">{ringWord(s.budget.eaten_kcal, s.budget.budget_kcal)}</p>
              {s.eaten.kcal > 0 && (
                <p className="m-0 mb-3 text-body-sm text-muted">
                  Eaten so far <RangeBadge value={s.eaten.kcal} low={s.eaten.kcal_low} high={s.eaten.kcal_high} />
                  {s.budget.exercise_credit_kcal > 0 && <> · includes about {fmt(s.budget.exercise_credit_kcal)} kcal credit for movement</>}
                </p>
              )}
              <MacroBars eaten={s.eaten} target={t} />
              <ul className="m-0 mt-4 flex list-none flex-wrap gap-2 p-0">
                <li><Pill tone="sky">Water goal about {(t.water_ml / 1000).toFixed(1)} L</Pill></li>
                <li><Pill tone="peach">Steps goal {fmt(t.steps)}</Pill></li>
                {s.workout_kcal > 0 && <li><Pill tone="mint">Workout burn about {fmt(s.workout_kcal)} kcal</Pill></li>}
              </ul>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link href="/fitness/calories" className={`${BTN_PRIMARY} no-underline`}>Log a meal</Link>
              </div>
            </div>
          </div>
        </Section>
      )}

      <section aria-labelledby="fit-tools">
        <h2 id="fit-tools" className="m-0 mb-2 text-label font-extrabold uppercase tracking-wide text-subtle">Plan and log</h2>
        <ul className={`${SECTION} m-0 list-none divide-y divide-line overflow-hidden`} aria-label="Fitness tools">
          {cards.map((c) => {
            const st = cardState(c.kind, state);
            return (
              <li key={c.kind}>
                <Link href={c.href} className="bubbles-press flex items-center gap-4 px-4 py-3.5 text-ink no-underline hover:bg-tint-grape/40 sm:px-5">
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${TONE[c.tone].bubble}`}>
                    <Icon id={c.icon} size={20} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-display text-body font-bold">{c.title}</span>
                    <span className="block truncate text-body-sm text-muted">{c.text}</span>
                  </span>
                  <Pill tone={st === "Active" ? "mint" : st === "Plan ready" ? "sky" : "plain"}>{st}</Pill>
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <Section title="Progress">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <Stat label="Latest weight" value={formatWeight(s.latest_weight_kg, units)} />
          <Stat label="Target" value={t?.target_weight_kg ? formatWeight(t.target_weight_kg, units) : "Not set"} />
          {t?.time_to_goal && t.time_to_goal.gap_kg > 0 && <Stat label="Estimated time" value={formatWeeks(t.time_to_goal.weeks_low, t.time_to_goal.weeks_high)} />}
          {s.transform && <Stat label="Transformation" value={s.transform.status === "active" ? "In progress" : s.transform.status === "paused" ? "Paused" : "Finished"} />}
        </div>
        <p className="m-0 mt-3">
          <Link href="/fitness/progress" className="inline-flex min-h-[44px] items-center text-body-sm font-extrabold text-bubbles-grape-deep">See weight trend and measurements</Link>
        </p>
      </Section>
      <ClinicalNote review={s.review} />
      <Disclaimer />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="m-0 text-label font-extrabold uppercase tracking-wide text-subtle">{label}</p>
      <p className="m-0 font-display text-h3 text-ink">{value}</p>
    </div>
  );
}
