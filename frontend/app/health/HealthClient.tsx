"use client";

import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { ErrorCard, HubPage, Icon, Skeleton, TONE, useBubblesQuery, type Query, type Tone } from "../../components/hub/HubKit";
import { readHealthSummary, type HealthSummary } from "../lib/api-adapters";
import { formatWhen } from "../lib/dates";
import { OrganTracker } from "./OrganTracker";
import { QuickLog } from "./QuickLogGrid";

interface Tracker {
  id: string;
  title: string;
  why: string;
  tone: Tone;
}

const DAILY: Tracker[] = [
  { id: "cycle", title: "Cycle", why: "Periods and phases, so Bubbles can see what's cycle-linked.", tone: "pink" },
  { id: "symptoms", title: "Symptoms", why: "Aches, cramps, headaches: when and how strong.", tone: "pink" },
  { id: "sleep", title: "Sleep", why: "Hours and quality, the base for energy and mood.", tone: "grape" },
  { id: "mood", title: "Mood", why: "How you feel day to day, stress included.", tone: "sun" },
  { id: "hydration", title: "Water", why: "Quick sips add up. Gaps stay visible.", tone: "sky" },
  { id: "nutrition", title: "Food", why: "Meals and patterns, without calorie guilt.", tone: "mint" },
  { id: "activity", title: "Activity", why: "Walks, workouts and rest days.", tone: "peach" },
  { id: "weight", title: "Weight", why: "Only if it helps you: trends, not judgement.", tone: "peach" },
  { id: "vitals", title: "Vitals", why: "Heart rate, blood pressure and similar readings.", tone: "grape" },
];

const CARE: Tracker[] = [
  { id: "medications", title: "Medications", why: "What you take and when.", tone: "sky" },
  { id: "conditions", title: "Conditions", why: "Diagnoses your clinician has given you.", tone: "sky" },
  { id: "allergies", title: "Allergies", why: "Triggers and reactions to keep handy.", tone: "sun" },
  { id: "labs", title: "Lab results", why: "Blood tests and values with their ranges.", tone: "sky" },
  { id: "reports", title: "Reports", why: "Scans, imaging and clinic letters.", tone: "sky" },
  { id: "visits", title: "Visits", why: "Appointments and what was decided.", tone: "sky" },
];

export function HealthClient() {
  return (
    <HubPage title="My health">
      <HealthHub />
    </HubPage>
  );
}

function HealthHub() {
  const [summary, reload] = useBubblesQuery<unknown>("/health/summary");

  return (
    <div className="space-y-10">
      <h1 className="bubbles-rise text-h1 text-ink">My health</h1>

      <QuickLog items={DAILY} />

      <section aria-label="Your logging so far">
        <Overview summary={summary} onRetry={reload} />
      </section>

      <TrackerGroup id="care-records" title="Care records" items={CARE} />

      <details className="group border-b border-[color:var(--hairline)]">
        <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 py-3 font-display text-lg font-semibold text-ink [&::-webkit-details-marker]:hidden">
          Body systems
          <span className="transition-transform group-open:rotate-90"><Icon id="arrow" size={18} /></span>
        </summary>
        <div className="pb-4">
          <OrganTracker />
        </div>
      </details>
    </div>
  );
}

function Overview({ summary, onRetry }: { summary: Query<unknown>; onRetry: () => void }) {
  if (summary.status === "loading") {
    return (
      <div className="flex flex-col gap-3" role="status" aria-label="Loading your summary">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[40px] rounded-2xl" />
        ))}
      </div>
    );
  }
  if (summary.status === "error") {
    return <ErrorCard title="Your summary didn't load" message={summary.message} onRetry={onRetry} />;
  }

  const data: HealthSummary = readHealthSummary(summary.data);
  if (!data.entries) {
    return (
      <div className="flex flex-wrap items-center gap-4 py-2">
        <BubblesMascot size={56} mood="resting" animated={false} />
        <div className="min-w-0 flex-1">
          <p className="font-display text-h4 text-ink">Nothing logged yet</p>
          <p className="text-body-sm text-muted">Tap any tracker above to start.</p>
        </div>
      </div>
    );
  }

  const tiles: Array<{ label: string; value: string; tone: Tone }> = [
    { label: "Trackers in use", value: `${data.categories} of ${DAILY.length + CARE.length}`, tone: "pink" },
    { label: "Entries logged", value: String(data.entries), tone: "grape" },
    { label: "Days with a log", value: String(data.days), tone: "mint" },
    { label: "Last logged", value: data.lastUpdate ? formatWhen(data.lastUpdate) : "No date", tone: "sky" },
  ];
  return (
    <dl className="bubbles-stagger m-0 flex flex-col">
      {tiles.map((tile) => (
        <div key={tile.label} className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-[color:var(--hairline)] py-3">
          <dt className={`text-body-sm font-extrabold ${TONE[tile.tone].ink}`}>{tile.label}</dt>
          <dd className="m-0 font-display text-h4 text-ink">{tile.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function TrackerGroup({ id, title, items }: { id: string; title: string; items: Tracker[] }) {
  return (
    <section aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="text-h3 text-ink">
        {title}
      </h2>
      <ul className="bubbles-stagger m-0 mt-3 flex list-none flex-col p-0">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={`/${item.id}`}
              className="group flex items-center gap-3 border-b border-[color:var(--hairline)] py-3 no-underline"
            >
              <span aria-hidden="true" className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${TONE[item.tone].bubble}`}>
                <Icon id={item.id} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-h4 text-ink">{item.title}</span>
              </span>
              <span className="mt-1 text-ink-faint transition-colors group-hover:text-bubbles-pink-ink">
                <Icon id="arrow" size={18} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
