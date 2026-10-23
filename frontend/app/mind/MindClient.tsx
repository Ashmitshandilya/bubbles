"use client";

// The Mind hub: one primary tile (how are you feeling), then closed rows. Nothing here labels a person or diagnoses.

import { useState } from "react";
import Link from "next/link";
import { BTN_SECONDARY, PILL, Skeleton, useBubblesQuery } from "../../components/hub/HubKit";
import { Disclaimer, Fold, TrackerShell } from "../../components/tracking/kit";
import { PixelGrid } from "../../components/wellness/charts";
import { BTN_TEXT, EmptyNote, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";
import { askHref } from "../lib/ask-handoff";
import { readOrganMap } from "../lib/organ-map";
import type { MindInsight, MindOverview, Pixels } from "../../app/lib/wellness-types";
import { Lede } from "../../components/pearl";
import { Calm } from "./Calm";
import { CheckIn } from "./CheckIn";
import { ASK, softBrain } from "./hub";
import { Journal } from "./Journal";
import { PanicFlow } from "./PanicFlow";
import { QuickScore } from "./QuickScore";
import { Screens } from "./Screens";

export function MindClient() {
  return (
    <TrackerShell title="Mind">
      <h1 className="sr-only">Mind</h1>
      <Mind />
    </TrackerShell>
  );
}

/** One line in Bubbles' voice at the top: the person's own strongest pattern when there is one, otherwise a calm question. Never a score. */
function MindLede() {
  const [insights] = useWellnessQuery<{ insights: MindInsight[] }>("/wellness/mind/insights?days=90");
  const first = insights.status === "ready" ? insights.data.insights?.[0] : undefined;
  return <Lede>{first?.text ?? "Take a breath. How are you, right now?"}</Lede>;
}

function Mind() {
  const [overview, reloadOverview] = useWellnessQuery<MindOverview>("/wellness/mind/overview?days=30");
  const [panic, setPanic] = useState(false);

  return (
    <QueryView query={overview} onRetry={reloadOverview} what="the Mind page" skeleton={<Skeleton className="h-72 rounded-3xl" />}>
      {(o) => (
        <>
          <MindLede />
          <CheckIn overview={o} onSaved={reloadOverview} />
          {panic ? (
            <PanicFlow copy={o.support.panic} onClose={() => setPanic(false)} />
          ) : (
            <button type="button" onClick={() => setPanic(true)} className={`${BTN_SECONDARY} self-start`}>
              Feeling panicky? Breathe with me
            </button>
          )}

          <div className="flex flex-col gap-3">
            <Fold title="Anxiety check-in">
              <QuickScore kind="anxiety" onSaved={reloadOverview}>
                {(r) =>
                  r.suggest_talking_to_someone ? (
                    <button type="button" onClick={() => setPanic(true)} className={`${BTN_SECONDARY} self-start`}>
                      Breathe with me
                    </button>
                  ) : null
                }
              </QuickScore>
              <Screens screen={o.screen} onSaved={reloadOverview} />
            </Fold>

            <Fold title="Loneliness check-in">
              <p className="m-0 text-body-sm text-ink-soft">{o.support.loneliness.text}</p>
              <QuickScore kind="loneliness" onSaved={reloadOverview} />
              <Steps steps={o.support.loneliness.steps} />
              <Link href={askHref(ASK.loneliness)} className={`${BTN_SECONDARY} self-start no-underline`}>
                Talk it over with Bubbles
              </Link>
            </Fold>

            <Fold title="Missing someone / apart">
              <p className="m-0 text-body-sm text-ink-soft">{o.support.apart.text}</p>
              <Steps steps={o.support.apart.steps} />
              <Link href={askHref(ASK.apart)} className={`${BTN_SECONDARY} self-start no-underline`}>
                Talk it over with Bubbles
              </Link>
            </Fold>

            <Fold title="Breathe and ground">
              <button type="button" onClick={() => setPanic(true)} className={`${BTN_SECONDARY} self-start`}>
                Panicky right now? One tap
              </button>
              <Calm />
            </Fold>

            <Fold title="Journal">
              <Journal />
            </Fold>

            <PatternsFold />
            <BrainFold />
          </div>
          <p className="m-0 text-body-sm font-semibold text-muted">
            Mood tracking is for your own insight and doesn&apos;t replace support from a professional. The older simple form is still at{" "}
            <Link href="/mood" className="text-bubbles-grape-deep underline">
              Mood
            </Link>
            .
          </p>
          <Disclaimer />
        </>
      )}
    </QueryView>
  );
}

function Steps({ steps }: { steps: string[] }) {
  return (
    <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
      {steps.map((s) => (
        <li key={s}>{s}</li>
      ))}
    </ul>
  );
}

function PatternsFold() {
  const [open, setOpen] = useState(false);
  return (
    <Fold title="Patterns" onOpen={() => setOpen(true)}>
      {open && <Patterns />}
    </Fold>
  );
}

function Patterns() {
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const [pixels, reloadPixels] = useWellnessQuery<Pixels>(`/wellness/mind/pixels?year=${year}`);
  const [insights, reloadInsights] = useWellnessQuery<{ insights: MindInsight[]; data_gaps: string[]; days_with_mood: number }>("/wellness/mind/insights?days=90");
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0 font-display text-h4 text-default">Year in pixels</h3>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setYear((y) => y - 1)} aria-label={`Show ${year - 1}`} className={BTN_TEXT}>
            ◀ {year - 1}
          </button>
          <span className={`${PILL} bg-tint-sun text-bubbles-sun-deep`} aria-live="polite">
            {year}
          </span>
          <button type="button" onClick={() => setYear((y) => y + 1)} disabled={year >= thisYear} aria-label={`Show ${year + 1}`} className={BTN_TEXT}>
            {year + 1} ▶
          </button>
        </div>
      </div>
      <QueryView query={pixels} onRetry={reloadPixels} what="your year" skeleton={<Skeleton className="h-96 rounded-2xl" />}>
        {(p) => (p.logged_days === 0 ? <EmptyNote title={`No check-ins in ${p.year} yet`}>Each check-in colours one square.</EmptyNote> : <PixelGrid pixels={p} />)}
      </QueryView>
      <h3 className="m-0 font-display text-h4 text-default">Your own patterns</h3>
      <QueryView query={insights} onRetry={reloadInsights} what="patterns">
        {(d) =>
          d.insights.length === 0 ? (
            <EmptyNote title="Not enough check-ins yet">
              {d.data_gaps.map((g) => (
                <p key={g} className="m-0">
                  {g}
                </p>
              ))}
            </EmptyNote>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {d.insights.map((i) => (
                <li key={i.factor} className="rounded-2xl bg-blush px-4 py-3">
                  <p className="m-0 text-body font-bold text-ink">{i.text}</p>
                  <p className="m-0 mt-2 flex flex-wrap items-center gap-2 text-body-sm text-muted">
                    <span className={`${PILL} ${i.confidence === "moderate" ? "bg-tint-grape text-bubbles-grape-deep" : "bg-tint-sun text-bubbles-sun-deep"}`}>
                      {i.confidence === "moderate" ? "A steadier pattern" : "An early pattern"}
                    </span>
                    {i.with_n} days with it, {i.without_n} without
                  </p>
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
    </>
  );
}

function BrainFold() {
  const [open, setOpen] = useState(false);
  return (
    <Fold title="Your brain on the body map" onOpen={() => setOpen(true)}>
      {open && <Brain />}
    </Fold>
  );
}

function Brain() {
  const [query, reload] = useBubblesQuery<unknown>("/organs/map");
  return (
    <QueryView query={query} onRetry={reload} what="the body map" skeleton={<Skeleton className="h-16 rounded-2xl" />}>
      {(data) => {
        const brain = readOrganMap(data).find((o) => o.id === "brain");
        return (
          <>
            <p className="m-0 text-body text-ink">{softBrain(brain?.status)}</p>
            <Link href="/body?organ=brain" className={`${BTN_SECONDARY} self-start no-underline`}>
              Open on the body map
            </Link>
          </>
        );
      }}
    </QueryView>
  );
}
