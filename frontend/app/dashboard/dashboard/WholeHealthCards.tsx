"use client";

// Today: two calm cards that open the Fitness and Cycle sections, plus a one-tap quick-log row.
// Each card loads on its own and fails on its own, so one slow section never blanks the day.

import Link from "next/link";
import { BTN_SECONDARY, CARD, ErrorCard, PILL, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { ProgressRing } from "../../../components/fitness/ui";
import type { Overview } from "../../lib/cycle-types";
import type { Summary } from "../../lib/fitness-types";

const QUICK = [
  { href: "/fitness/calories", label: "Log a meal" },
  { href: "/fitness/workouts", label: "Log a workout" },
  { href: "/hydration", label: "Water" },
  { href: "/cycle", label: "Period & cycle" },
  { href: "/mind", label: "Mood" },
  { href: "/medications", label: "Medicines" },
] as const;

function FitnessCard() {
  const [q, reload] = useBubblesQuery<Summary & { status: string }>("/fitness/summary");
  if (q.status === "loading") return <Skeleton className="h-44 rounded-3xl" />;
  if (q.status === "error") return <ErrorCard title="Fitness isn't loading" message={q.message} onRetry={reload} inset />;
  const s = q.data;
  const t = s.targets;
  const budget = s.budget;
  return (
    <section aria-labelledby="today-fitness" className={`${CARD} flex flex-wrap items-center gap-5 p-5`}>
      {t && budget ? (
        <ProgressRing fraction={budget.budget_kcal ? budget.eaten_kcal / budget.budget_kcal : 0} size={112} stroke={11} tone="mint" label={`${budget.eaten_kcal} of about ${budget.budget_kcal} calories eaten`}>
          {s.intake_logged === false ? (
            <span className="block text-[0.7rem] font-bold text-muted">Nothing logged yet</span>
          ) : (
            <>
              <span className="text-body-sm font-extrabold text-ink">{budget.remaining_kcal >= 0 ? budget.remaining_kcal : 0}</span>
              <span className="block text-[0.7rem] font-bold text-muted">kcal left</span>
            </>
          )}
        </ProgressRing>
      ) : null}
      <div className="min-w-[10rem] flex-1">
        <h2 id="today-fitness" className="m-0 font-display text-h3 text-ink">Fitness today</h2>
        {t && budget ? (
          <p className="m-0 mt-1 text-body-sm text-muted">
            About {budget.budget_kcal} kcal and {t.protein_g} g protein is your estimate for today. {s.transform ? `Transformation plan: ${s.transform.status}.` : ""}
          </p>
        ) : (
          <p className="m-0 mt-1 text-body-sm text-muted">{s.message ?? "Set up your details and Bubbles will work out a gentle daily plan."}</p>
        )}
        {!s.review.reviewed && <p className="m-0 mt-2"><span className={`${PILL} bg-tint-sky text-bubbles-sky-deep`}>Estimates, pending clinician review</span></p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href={t ? "/fitness" : "/fitness/setup"} className={`${BTN_SECONDARY} no-underline`}>{t ? "Open Fitness" : "Set up Fitness"}</Link>
          <Link href="/fitness/calories" className={`${BTN_SECONDARY} no-underline`}>Log a meal</Link>
        </div>
      </div>
    </section>
  );
}

function CycleCard() {
  const [q, reload] = useBubblesQuery<Overview>(`/cycle/overview?today=${new Date().toLocaleDateString("en-CA")}`);
  if (q.status === "loading") return <Skeleton className="h-44 rounded-3xl" />;
  if (q.status === "error") return <ErrorCard title="Cycle isn't loading" message={q.message} onRetry={reload} inset />;
  const o = q.data;
  const urgent = Boolean(o.urgent);
  return (
    <section aria-labelledby="today-cycle" className={`${CARD} p-5`}>
      <h2 id="today-cycle" className="m-0 font-display text-h3 text-ink">Cycle today</h2>
      {urgent ? (
        <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-ink">{o.urgent?.message ?? "Please look at your Cycle page."}</p>
      ) : !o.has_data ? (
        <p className="m-0 mt-1 text-body-sm text-muted">{o.empty_state ?? "Log your last period and Bubbles will start learning your rhythm."}</p>
      ) : (
        <>
          <p className="m-0 mt-1 text-body text-ink">
            {o.cycle_day ? <strong>Day {o.cycle_day}</strong> : null}
            {o.phase ? <> · {o.phase.label}</> : null}
            {o.phase?.estimated ? <span className="text-muted"> (estimate)</span> : null}
          </p>
          {o.weather && <p className="m-0 mt-1 text-body-sm text-muted">{o.weather.line}</p>}
          {o.next_period && (
            <p className="m-0 mt-1 text-body-sm text-muted">
              Next period, an estimate: {o.next_period.status === "late" ? "a little later than usual" : o.next_period.in_days <= 0 ? "any day now" : `in about ${o.next_period.in_days} days`}
              {o.confidence === "learning" ? " (still learning your rhythm)" : ""}.
            </p>
          )}
        </>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href="/cycle" className={`${BTN_SECONDARY} no-underline`}>Open Cycle</Link>
      </div>
    </section>
  );
}

export function WholeHealthCards() {
  return (
    <>
      <div className="grid gap-6 md:grid-cols-2">
        <FitnessCard />
        <CycleCard />
      </div>
      <nav aria-label="Quick log" className="flex flex-wrap gap-2">
        {QUICK.map((item) => (
          <Link key={item.href + item.label} href={item.href} className={`${BTN_SECONDARY} no-underline`}>{item.label}</Link>
        ))}
      </nav>
    </>
  );
}

/** A quiet pointer to Partner sharing. Never an error card: if the API is slow or down, it shows the plain link. */
export function PartnerCard() {
  const [q] = useBubblesQuery<{ shares: unknown[] }>("/partner-sharing/shared-with-me");
  const n = q.status === "ready" && Array.isArray(q.data.shares) ? q.data.shares.length : 0;
  return (
    <p className="m-0 px-1 text-body-sm text-muted">
      {n > 0 ? (
        <Link href="/partner" className="font-extrabold text-bubbles-pink-ink underline">
          {n === 1 ? "1 person shares" : `${n} people share`} with you
        </Link>
      ) : (
        <Link href="/partner" className="font-bold text-muted underline">Share with someone you trust</Link>
      )}
    </p>
  );
}
