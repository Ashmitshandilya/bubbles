"use client";

import { useState } from "react";
import Link from "next/link";
import { Skeleton } from "../../components/hub/HubKit";
import { Disclaimer, TrackerHero, TrackerShell } from "../../components/tracking/kit";
import { PixelGrid } from "../../components/wellness/charts";
import { BTN_TEXT, EmptyNote, Panel, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";
import { PILL } from "../../components/hub/HubKit";
import type { MindInsight, MindOverview, Pixels } from "../../app/lib/wellness-types";
import { Calm } from "./Calm";
import { CheckIn } from "./CheckIn";
import { Journal } from "./Journal";
import { Screens } from "./Screens";

const SECTIONS = [
  { id: "checkin", label: "Check-in" },
  { id: "year", label: "Year in pixels" },
  { id: "check-ins", label: "Gentle check-ins" },
  { id: "journal", label: "Journal" },
  { id: "calm", label: "Calm space" },
  { id: "patterns", label: "Patterns" },
];

export function MindClient() {
  return (
    <TrackerShell title="Mind">
      <Mind />
    </TrackerShell>
  );
}

function Mind() {
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const [overview, reloadOverview] = useWellnessQuery<MindOverview>("/wellness/mind/overview?days=30");
  const [pixels, reloadPixels] = useWellnessQuery<Pixels>(`/wellness/mind/pixels?year=${year}`);
  const [insights, reloadInsights] = useWellnessQuery<{ insights: MindInsight[]; data_gaps: string[]; days_with_mood: number }>("/wellness/mind/insights?days=90");

  const refresh = () => {
    reloadOverview();
    reloadPixels();
    reloadInsights();
  };

  return (
    <>
      <TrackerHero
        signal="sun"
        icon="mood"
        kicker="MIND & MOOD"
        title="Mind"
        why="A quick check-in, a private journal and a few calm tools. Bubbles notices patterns over time and never diagnoses."
        action={
          <a href="#checkin" className="bubbles-press inline-flex min-h-[52px] w-full items-center justify-center rounded-full bg-bubbles-sun px-6 text-body font-extrabold text-ink shadow-[0_5px_0_var(--bubbles-sun-deep)] sm:w-auto">
            Check in
          </a>
        }
      />

      <nav aria-label="On this page">
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border-2 border-line bg-surface px-4 text-body-sm font-extrabold text-ink-soft hover:border-line-strong hover:text-ink">
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <QueryView query={overview} onRetry={reloadOverview} what="your check-in" skeleton={<Skeleton className="h-72 rounded-3xl" />}>
        {(o) => <CheckIn overview={o} onSaved={refresh} />}
      </QueryView>

      <Panel
        id="year"
        title="Year in pixels"
        kicker="One square a day"
        action={
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
        }
      >
        <QueryView query={pixels} onRetry={reloadPixels} what="your year" skeleton={<Skeleton className="h-96 rounded-2xl" />}>
          {(p) => (p.logged_days === 0 ? <EmptyNote title={`No check-ins in ${p.year} yet`}>Each check-in colours one square. Over time you can see how your year has felt.</EmptyNote> : <PixelGrid pixels={p} />)}
        </QueryView>
      </Panel>

      <QueryView query={overview} onRetry={reloadOverview} what="gentle check-ins" skeleton={<Skeleton className="h-40 rounded-3xl" />}>
        {(o) => <Screens screen={o.screen} onSaved={reloadOverview} />}
      </QueryView>

      <Journal />
      <Calm />

      <Panel id="patterns" title="Patterns" kicker="Your own logs, not proof of a cause">
        <QueryView query={insights} onRetry={reloadInsights} what="patterns">
          {(d) =>
            d.insights.length === 0 ? (
              <EmptyNote title="Not enough check-ins yet">
                {d.data_gaps.map((g) => (
                  <p key={g} className="m-0">{g}</p>
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
      </Panel>

      <p className="m-0 text-body-sm font-semibold text-muted">
        Mood tracking is for your own insight and doesn&apos;t replace support from a professional. Prefer the older simple form? It&apos;s still at{" "}
        <Link href="/mood" className="text-bubbles-grape-deep underline">
          Mood
        </Link>
        .
      </p>
      <Disclaimer />
    </>
  );
}
