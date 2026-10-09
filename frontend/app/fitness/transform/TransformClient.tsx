"use client";

import { useState } from "react";
import { BTN_PRIMARY, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { ClinicalNote, Disclaimer, FitnessPage, Notice, PageHeading, Section } from "../../../components/fitness/ui";
import { fmt, formatWeight } from "../../lib/fitness-calc";
import { formatWhen } from "../../lib/dates";
import { useUnits } from "../../../components/fitness/useUnits";
import type { PlanResponse } from "../../lib/fitness-types";
import { TransformStepper } from "./TransformStepper";
import { Dashboard } from "./TransformDashboard";

export function TransformClient() {
  return (
    <FitnessPage title="Strict transformation" subnav={false}>
      <Transform />
    </FitnessPage>
  );
}

function Transform() {
  const [q, reload] = useBubblesQuery<PlanResponse>("/fitness/transform/plan");
  const units = useUnits();
  const [again, setAgain] = useState(false);

  if (q.status === "loading")
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4" role="status" aria-label="Loading your plan">
        <Skeleton className="h-10 w-1/2 rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-3xl" />
      </div>
    );
  if (q.status === "error") return <ErrorCard title="Couldn't load your plan" message={q.message} onRetry={reload} />;

  const { plan, review } = q.data;

  // Active or paused: the dashboard. The review banner stays visible above everything.
  if (plan && (plan.status === "active" || plan.status === "paused"))
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
        <PageHeading kicker="Strict transformation" title={plan.status === "paused" ? "Your plan is paused" : "Your plan"} />
        <ClinicalNote review={review} />
        <Dashboard plan={plan} units={units} reload={reload} />
        <Disclaimer />
      </div>
    );

  if (plan && plan.status === "completed" && !again)
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
        <PageHeading kicker="Strict transformation" title="You finished a plan" text="Whatever the scale says, finishing a structured plan took real effort." />
        <ClinicalNote review={review} />
        <Section title="Where you ended up">
          <p className="m-0 text-body text-ink">Started {formatWhen(plan.start_date, true)} at {formatWeight(plan.start_weight_kg, units)}. Target was {formatWeight(plan.target_weight_kg, units)}.</p>
          {plan.maintenance && plan.maintenance.length > 0 && (
            <>
              <h3 className="m-0 mt-4 font-display text-h4 text-ink">Easing back to maintenance</h3>
              <p className="m-0 text-body-sm text-muted">Calories rise a little each week so your body settles. Estimates, not rules.</p>
              <ul className="m-0 mt-2 list-none p-0 text-body-sm text-ink">
                {plan.maintenance.map((m) => <li key={m.week} className="py-1">Week {m.week}: about {fmt(m.kcal)} kcal</li>)}
              </ul>
            </>
          )}
        </Section>
        <div><button type="button" className={BTN_PRIMARY} onClick={() => setAgain(true)}>Start a new plan</button></div>
        <Disclaimer />
      </div>
    );

  return (
    <div className="flex flex-col gap-4">
      <div className="mx-auto w-full max-w-2xl"><ClinicalNote review={review} /></div>
      <TransformStepper onStarted={() => { setAgain(false); reload(); }} />
      <div className="mx-auto w-full max-w-2xl"><Notice tone="plain">Strict mode never replaces your doctor or dietitian. You can leave at any step and come back later.</Notice></div>
    </div>
  );
}
