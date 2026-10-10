"use client";

import { useState } from "react";
import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import {
  BTN_SECONDARY,
  CARD,
  ErrorCard,
  HubPage,
  PILL,
  Skeleton,
  TONE,
  humanize,
  toneFor,
  useBubblesQuery,
} from "../../components/hub/HubKit";
import { formatWhen } from "../lib/dates";
import {
  CARD_LIMIT,
  toCards,
  weeklyCounts,
  type Confidence,
  type LongitudinalResponse,
  type PatternCard,
  type PatternsResponse,
} from "./patterns";

const CONFIDENCE_PILL: Record<Confidence, string> = {
  High: "bg-tint-mint text-bubbles-mint-deep",
  Medium: "bg-tint-grape text-bubbles-grape-deep",
  Low: "bg-tint-sun text-bubbles-sun-deep",
};

const DOMAIN_LABEL: Record<string, string> = {
  sleep: "Sleep",
  stress: "Stress",
  mood: "Mood",
  weight: "Weight",
  hydration: "Water",
  exercise: "Activity",
  symptom: "Symptoms",
  cycle: "Cycle",
  nutrition: "Food",
};

const LOG_LINKS = [
  { href: "/symptoms", label: "Log a symptom", tone: "pink" },
  { href: "/sleep", label: "Log sleep", tone: "grape" },
  { href: "/mood", label: "Log mood", tone: "sun" },
  { href: "/cycle", label: "Log your cycle", tone: "pink" },
] as const;

/* ── Page ─────────────────────────────────────────────── */

export function InsightsClient() {
  return (
    <HubPage title="Patterns">
      <Patterns />
    </HubPage>
  );
}

function Patterns() {
  const [days, setDays] = useState(30);
  const [patterns, reloadPatterns] = useBubblesQuery<PatternsResponse>("/patterns/analyze", { days });
  const [trend, reloadTrend] = useBubblesQuery<LongitudinalResponse>("/intelligence/longitudinal", { days });

  const analysis = patterns.status === "ready" ? patterns.data.analysis ?? {} : null;
  const cards = analysis ? toCards(analysis, days) : [];
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? cards : cards.slice(0, CARD_LIMIT);
  const mood = patterns.status === "loading" ? "thinking" : cards.length ? "happy" : "calm";

  return (
    <div className="space-y-8">
      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-tint-grape">
          <BubblesMascot size={60} mood={mood} animated={patterns.status === "loading"} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">Patterns</h1>
          <p className="mt-1 text-body font-semibold text-muted">
            What keeps showing up in your logs — in plain words, with how sure Bubbles is.
          </p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Time window">
        {[30, 90].map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={days === value}
            onClick={() => setDays(value)}
            className={`bubbles-press min-h-[44px] rounded-full px-5 text-body-sm font-extrabold ${
              days === value ? "bg-ink text-white" : "border-2 border-line bg-surface text-ink-soft hover:border-line-strong"
            }`}
          >
            Last {value} days
          </button>
        ))}
      </div>

      <LinksSection />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section aria-labelledby="pattern-list-title" aria-busy={patterns.status === "loading"}>
          <h2 id="pattern-list-title" className="sr-only">
            Patterns Bubbles noticed
          </h2>
          {patterns.status === "loading" && (
            <div className="space-y-3" role="status" aria-label="Looking for patterns">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-40 rounded-3xl" />
              ))}
            </div>
          )}
          {patterns.status === "error" && (
            <ErrorCard title="Patterns didn't load" message={patterns.message} onRetry={reloadPatterns} />
          )}
          {analysis && cards.length === 0 && <EmptyPatterns logs={analysis.event_count ?? 0} days={days} />}
          {cards.length > 0 && (
            <ul className="bubbles-stagger m-0 list-none space-y-4 p-0">
              {visible.map((card) => (
                <li key={card.key}>
                  <PatternCardView card={card} />
                </li>
              ))}
            </ul>
          )}
          {cards.length > CARD_LIMIT && (
            <button type="button" aria-expanded={showAll} onClick={() => setShowAll((v) => !v)} className={`${BTN_SECONDARY} mt-4`}>
              {showAll ? "Show fewer patterns" : `Show all ${cards.length} patterns`}
            </button>
          )}
        </section>

        <aside className="space-y-4" aria-label="Your logging over time">
          {trend.status === "loading" && <Skeleton className="h-64 rounded-3xl" />}
          {trend.status === "error" && (
            <ErrorCard title="Your trend didn't load" message={trend.message} onRetry={reloadTrend} />
          )}
          {trend.status === "ready" && <TrendView analysis={trend.data.analysis ?? {}} days={days} />}
          <div className={`${CARD} p-5`}>
            <p className="font-display text-h4 text-ink">Curious about a pattern?</p>
            <p className="mt-1 text-body-sm text-muted">Bubbles can talk it through with you and help you decide what to track next.</p>
            <Link href="/companion" className={`${BTN_SECONDARY} mt-3 no-underline`}>
              Talk to Bubbles
            </Link>
          </div>
        </aside>
      </div>

      <p className="text-body-sm text-muted">
        Patterns are observations from your own logs — not diagnoses, and not proof that one thing causes another.
      </p>
    </div>
  );
}

/* ── Links between the things you log (association engine) ── */

interface AssociationSource {
  title?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  snippet?: string | null;
}
interface Association {
  id: string;
  status: string;
  strength: "weak" | "moderate" | "strong";
  n_days: number;
  text: string;
  sources?: AssociationSource[];
}
interface AssociationGap {
  id: string;
  text: string;
}
interface AssociationsResponse {
  insights?: Association[];
  gaps?: AssociationGap[];
  message?: string;
}

const STRENGTH_PILL = {
  weak: "bg-tint-sun text-bubbles-sun-deep",
  moderate: "bg-tint-grape text-bubbles-grape-deep",
  strong: "bg-tint-mint text-bubbles-mint-deep",
} as const;

// The server sends "<sentence> (N days logged). <caveats>": show the sentence, keep the caveats one tap away.
const sentence = (text: string) => text.split(" (")[0];
const caveats = (text: string) => text.slice(text.indexOf(". ") + 2);

function LinksSection() {
  const [links, reload] = useBubblesQuery<AssociationsResponse>("/wellness/associations?days=90");
  const insights = links.status === "ready" ? links.data.insights ?? [] : [];
  const gaps = links.status === "ready" ? links.data.gaps ?? [] : [];

  return (
    <section aria-labelledby="links-title" aria-busy={links.status === "loading"} className="space-y-3">
      <div>
        <h2 id="links-title" className="text-h3 text-ink">
          Links between what you log
        </h2>
        <p className="mt-1 text-body-sm text-muted">
          Bubbles compares your sleep, mood, activity, drinks, food, symptoms and cycle over the last 90 days. A link only shows when it is clear and repeated enough to trust.
        </p>
      </div>
      {links.status === "loading" && <Skeleton className="h-28 rounded-3xl" />}
      {links.status === "error" && <ErrorCard title="Links didn't load" message={links.message} onRetry={reload} />}
      {links.status === "ready" && insights.length > 0 && (
        <ul className="bubbles-stagger m-0 grid list-none gap-3 p-0 md:grid-cols-2">
          {insights.map((item) => (
            <li key={item.id} className={`${CARD} p-5`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`${PILL} ${STRENGTH_PILL[item.strength] ?? STRENGTH_PILL.weak}`}>{item.strength} link</span>
                {item.status === "repeated_pattern" && <span className={`${PILL} bg-tint-mint text-bubbles-mint-deep`}>seen in two periods</span>}
                <span className="text-[0.8125rem] font-bold text-muted">{item.n_days} days</span>
              </div>
              <p className="mt-3 text-body font-bold text-ink">{sentence(item.text)}.</p>
              <details className="mt-2">
                <summary className="cursor-pointer text-body-sm font-extrabold text-bubbles-grape-deep">Things to keep in mind</summary>
                <p className="mt-1 text-body-sm text-muted">{caveats(item.text)}</p>
              </details>
              {item.sources && item.sources.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-body-sm font-extrabold text-bubbles-grape-deep">What published sources say</summary>
                  <ul className="m-0 mt-1 list-none space-y-2 p-0">
                    {item.sources.map((source, i) => (
                      <li key={`${source.source_url ?? source.title}-${i}`} className="text-body-sm text-muted">
                        {source.snippet}
                        {source.source_url?.startsWith("https://") && (
                          <>
                            {" "}
                            <a href={source.source_url} target="_blank" rel="noopener noreferrer" className="font-bold text-bubbles-grape-deep">
                              {source.source_name ?? "Source"}
                            </a>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
      {links.status === "ready" && insights.length === 0 && (
        <div className={`${CARD} p-5`}>
          <p className="m-0 text-body text-muted">{links.data.message ?? "No reliable link between the things you log yet."}</p>
          {gaps.length > 0 && (
            <ul className="m-0 mt-3 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
              {gaps.map((gap) => (
                <li key={gap.id}>{gap.text}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function PatternCardView({ card }: { card: PatternCard }) {
  return (
    <article className={`${CARD} p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${PILL} ${CONFIDENCE_PILL[card.confidence]}`}>{card.confidence} confidence</span>
        <span className="text-[0.8125rem] font-bold text-muted">{card.window}</span>
      </div>
      <h3 className="mt-3 text-h3 text-ink">{card.headline}</h3>
      <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0" aria-label="Signals involved">
        {card.signals.map((signal) => {
          const tone = TONE[toneFor(signal.toneKey)];
          return (
            <li key={signal.subject} className={`${PILL} ${tone.chip}`}>
              <span className={`h-2 w-2 rounded-full ${tone.dot}`} aria-hidden="true" />
              {humanize(signal.subject)}
            </li>
          );
        })}
      </ul>
      <details className="group mt-4 rounded-2xl bg-blush">
        <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-2 rounded-2xl px-4 text-body-sm font-extrabold text-bubbles-grape-deep [&::-webkit-details-marker]:hidden">
          Why Bubbles thinks this
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-open:rotate-180">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </summary>
        <div className="px-4 pb-4">
          <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
            {card.evidence.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="mt-3 text-body-sm text-muted">{card.note}</p>
        </div>
      </details>
    </article>
  );
}

function EmptyPatterns({ logs, days }: { logs: number; days: number }) {
  const few = logs < 14;
  return (
    <div className={`${CARD} p-6 text-center sm:p-8`}>
      <BubblesMascot size={88} mood="resting" animated={false} className="mx-auto" />
      <h3 className="mt-3 text-h3 text-ink">
        {few ? "Bubbles needs about two weeks of logs to spot patterns" : "Nothing repeats often enough yet"}
      </h3>
      <p className="mx-auto mt-2 max-w-md text-body text-muted">
        {few
          ? `You have ${logs} ${logs === 1 ? "log" : "logs"} in the last ${days} days. A few quick entries a day is plenty.`
          : `Bubbles looked at ${logs} logs. A pattern needs the same thing to show up at least three times.`}
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {LOG_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`bubbles-press inline-flex min-h-[44px] items-center rounded-full px-4 text-body-sm font-extrabold no-underline ${TONE[link.tone].chip}`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

function TrendView({ analysis, days }: { analysis: NonNullable<LongitudinalResponse["analysis"]>; days: number }) {
  const counts = weeklyCounts(analysis.timeline, days);
  const weeks = counts.length;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const total = counts.reduce((a, b) => a + b, 0);
  const peak = Math.max(...counts);
  const weekLabel = (i: number) => {
    const start = new Date(today.getTime() - ((weeks - 1 - i) * 7 + 6) * 86_400_000);
    return i === weeks - 1 ? "This week" : `Week of ${formatWhen(start.toISOString())}`;
  };
  const domains = Object.entries(analysis.domains ?? {}).filter(([key]) => DOMAIN_LABEL[key]);

  return (
    <>
      {total > 0 && (
        <figure className={`${CARD} m-0 p-5`}>
          <figcaption>
            <span className="block font-display text-h4 text-ink">Your logging rhythm</span>
            <span className="block text-body-sm text-muted">
              Logs per week, last {days} days · busiest week {peak}, this week {counts[weeks - 1]}
            </span>
          </figcaption>
          <div className="mt-4 flex h-32 items-end gap-0.5 border-b-2 border-line" aria-hidden="true">
            {counts.map((count, i) => (
              <div key={i} className="flex h-full flex-1 items-end" title={`${weekLabel(i)}: ${count} logs`}>
                <div
                  className={`bubbles-bar w-full rounded-t ${count ? "bg-bubbles-grape" : "bg-line"}`}
                  style={{ height: count ? `${Math.max(6, (count / peak) * 100)}%` : "3px", animationDelay: `${i * 40}ms` }}
                />
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex justify-between text-[0.75rem] font-bold text-muted" aria-hidden="true">
            <span>{weekLabel(0).replace("Week of ", "")}</span>
            <span>This week</span>
          </div>
          <table className="sr-only">
            <caption>Logs per week</caption>
            <tbody>
              {counts.map((count, i) => (
                <tr key={i}>
                  <th scope="row">{weekLabel(i)}</th>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      )}

      {domains.length > 0 && (
        <div className={`${CARD} p-5`}>
          <p className="font-display text-h4 text-ink">What Bubbles can see</p>
          <p className="text-body-sm text-muted">Gaps stay gaps — Bubbles never reads missing logs as &ldquo;fine&rdquo;.</p>
          <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
            {domains.map(([key, domain]) => {
              const status = domain.coverage_status ?? "missing";
              const style =
                status === "observed"
                  ? "bg-tint-mint text-bubbles-mint-deep"
                  : status === "sparse"
                    ? "bg-tint-sun text-bubbles-sun-deep"
                    : "border-2 border-dashed border-line-strong text-ink-soft";
              const word = status === "observed" ? "regular logs" : status === "sparse" ? "a few logs" : "nothing yet";
              return (
                <li key={key} className={`${PILL} ${style}`}>
                  {DOMAIN_LABEL[key]} · {word}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </>
  );
}
