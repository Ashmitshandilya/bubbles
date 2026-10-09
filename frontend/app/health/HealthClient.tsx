"use client";

import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { CARD, ErrorCard, HubPage, Icon, Skeleton, TONE, useBubblesQuery, type Query, type Tone } from "../../components/hub/HubKit";
import { readHealthSummary, type HealthSummary } from "../lib/api-adapters";
import { formatWhen } from "../lib/dates";
import { OrganTracker } from "./OrganTracker";

interface Tracker {
  id: string;
  title: string;
  why: string;
  tone: Tone;
}

const DAILY: Tracker[] = [
  { id: "cycle", title: "Cycle", why: "Periods and phases, so Bubbles can see what's cycle-linked.", tone: "pink" },
  { id: "symptoms", title: "Symptoms", why: "Aches, cramps, headaches — when and how strong.", tone: "pink" },
  { id: "sleep", title: "Sleep", why: "Hours and quality, the base for energy and mood.", tone: "grape" },
  { id: "mood", title: "Mood", why: "How you feel day to day, stress included.", tone: "sun" },
  { id: "hydration", title: "Water", why: "Quick sips add up — gaps stay visible.", tone: "sky" },
  { id: "nutrition", title: "Food", why: "Meals and patterns, without calorie guilt.", tone: "mint" },
  { id: "activity", title: "Activity", why: "Walks, workouts and rest days.", tone: "peach" },
  { id: "weight", title: "Weight", why: "Only if it helps you — trends, not judgement.", tone: "peach" },
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
  const hasLogs = summary.status === "ready" && readHealthSummary(summary.data).entries > 0;

  return (
    <div className="space-y-10">
      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="bubbles-breathe flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-tint-pink">
          <BubblesMascot size={60} mood={hasLogs ? "happy" : "calm"} animated={false} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">My health</h1>
          <p className="mt-1 text-body font-semibold text-muted">Everything you log, in one friendly place.</p>
        </div>
      </header>

      <section aria-labelledby="overview-title">
        <h2 id="overview-title" className="text-h3 text-ink">
          Your logging so far
        </h2>
        <div className="mt-3">
          <Overview summary={summary} onRetry={reload} />
        </div>
      </section>

      <TrackerGroup id="daily" title="Daily signals" items={DAILY} />
      <TrackerGroup id="care-records" title="Care records" items={CARE} />

      <OrganTracker />
    </div>
  );
}

function Overview({ summary, onRetry }: { summary: Query<unknown>; onRetry: () => void }) {
  if (summary.status === "loading") {
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status" aria-label="Loading your summary">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[104px] rounded-3xl" />
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
      <div className={`${CARD} flex flex-wrap items-center gap-4 p-5`}>
        <BubblesMascot size={56} mood="resting" animated={false} />
        <div className="min-w-0 flex-1">
          <p className="font-display text-h4 text-ink">Nothing logged yet</p>
          <p className="text-body-sm text-muted">
            Pick any tracker below — even one entry gives Bubbles something to learn from.
          </p>
        </div>
      </div>
    );
  }

  const tiles: Array<{ label: string; value: string; tone: Tone }> = [
    { label: "Trackers in use", value: `${data.categories} of ${DAILY.length + CARE.length}`, tone: "pink" },
    { label: "Entries logged", value: String(data.entries), tone: "grape" },
    { label: "Days with a log", value: String(data.days), tone: "mint" },
    { label: "Last logged", value: formatWhen(data.lastUpdate), tone: "sky" },
  ];
  return (
    <dl className="bubbles-stagger m-0 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className={`${CARD} p-4 sm:p-5`}>
          <dt className={`text-body-sm font-extrabold ${TONE[tile.tone].ink}`}>{tile.label}</dt>
          <dd className="m-0 mt-2 font-display text-[1.75rem] font-semibold leading-tight text-ink sm:text-[1.875rem]">{tile.value}</dd>
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
      <ul className="bubbles-stagger m-0 mt-3 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={`/${item.id}`}
              className={`${CARD} bubbles-lift group flex h-full items-start gap-4 p-4 no-underline hover:border-line-strong`}
            >
              <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${TONE[item.tone].bubble}`}>
                <Icon id={item.id} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-h4 text-ink">{item.title}</span>
                <span className="mt-0.5 block text-body-sm text-muted">{item.why}</span>
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
