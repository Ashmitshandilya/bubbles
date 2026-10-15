"use client";

import { useState, type ReactNode } from "react";
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
  caveats,
  closestGap,
  directionInfo,
  emptyProgressLine,
  loggedDaysLine,
  sentence,
  strengthSteps,
  topic,
  whatToTry,
  type Association,
  type AssociationsResponse,
} from "./associations";
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

// `?log=1` opens the tracker with its log sheet ready; the Cycle page has no such flag.
const LOG_LINKS = [
  { href: "/symptoms?log=1", label: "Log a symptom", tone: "pink" },
  { href: "/sleep?log=1", label: "Log sleep", tone: "grape" },
  { href: "/mood?log=1", label: "Log mood", tone: "sun" },
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

  return (
    <div className="space-y-8">
      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">Patterns</h1>
          <p className="mt-1 text-body font-semibold text-muted">
            What keeps showing up in your logs, in plain words, with how sure Bubbles is.
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
              days === value ? "bg-bubbles-grape text-white" : "border border-line bg-surface text-ink-soft hover:border-line-strong"
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
        Patterns are observations from your own logs, not diagnoses, and not proof that one thing causes another.
      </p>
    </div>
  );
}

/* ── Links between the things you log (association engine) ── */

const ARROWS = { up: "M7 17 17 7M9 7h8v8", down: "M7 7l10 10M17 9v8H9" } as const;

function Disclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group rounded-2xl bg-blush">
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-2 rounded-2xl px-4 text-body-sm font-extrabold text-bubbles-grape-deep [&::-webkit-details-marker]:hidden">
        {title}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-open:rotate-180">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}

function StrengthBar({ strength }: { strength: string }) {
  const steps = strengthSteps(strength);
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div role="img" aria-label={`${strength} link, ${steps} of 3`} className="flex gap-1">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`h-2.5 flex-1 rounded-full ${n <= steps ? "bg-bubbles-grape" : "bg-line"}`} />
        ))}
      </div>
      <span className="text-body-sm font-extrabold capitalize text-ink">{strength} link</span>
    </div>
  );
}

function DirectionRow({ direction }: { direction: string | undefined }) {
  const info = directionInfo(direction);
  if (!info) return null;
  return (
    <div className="flex min-w-0 items-start gap-2.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-tint-grape text-bubbles-grape-deep">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d={ARROWS[info.arrow]} />
        </svg>
      </span>
      <span className="text-body-sm font-bold leading-snug text-ink-soft">{info.text}</span>
    </div>
  );
}

function AssociationCard({ item }: { item: Association }) {
  const note = caveats(item.text);
  const sources = item.sources ?? [];
  return (
    <article className={`${CARD} flex h-full flex-col gap-4 p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${PILL} bg-tint-grape text-bubbles-grape-deep`}>May be linked</span>
        {item.status === "repeated_pattern" && <span className={`${PILL} bg-tint-mint text-bubbles-mint-deep`}>Seen in two periods</span>}
      </div>

      {item.domains && item.domains.length > 1 && (
        <ul className="m-0 flex list-none flex-wrap items-center gap-2 p-0" aria-label="What was compared">
          {item.domains.slice(0, 2).map((key, i) => {
            const tone = TONE[toneFor(`${key} ${topic(key)}`)];
            return (
              <li key={key} className="flex items-center gap-2">
                {i > 0 && <span className="text-body-sm font-extrabold text-muted" aria-hidden="true">+</span>}
                <span className={`${PILL} ${tone.chip}`}>
                  <span className={`h-2 w-2 rounded-full ${tone.dot}`} aria-hidden="true" />
                  {humanize(topic(key))}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <p className="m-0 font-display text-h4 text-ink">{sentence(item.text)}.</p>

      <div className="grid gap-3 sm:grid-cols-2">
        <StrengthBar strength={item.strength} />
        <DirectionRow direction={item.direction} />
      </div>

      <p className="m-0 text-body-sm text-muted">Based on {item.n_days} days where both were logged. An association in your logs, not a cause.</p>

      <div className="rounded-2xl border border-dashed border-line-strong p-4">
        <p className="m-0 text-label font-extrabold text-ink-soft">What to try</p>
        <p className="m-0 mt-1 text-body-sm text-ink">{whatToTry(item)}</p>
      </div>

      <div className="mt-auto flex flex-col gap-2">
        {note && (
          <Disclosure title="Things to keep in mind">
            <p className="m-0 text-body-sm text-muted">{note}</p>
          </Disclosure>
        )}
        {sources.length > 0 && (
          <Disclosure title={`Sources (${sources.length})`}>
            <ul className="m-0 list-none space-y-2 p-0">
              {sources.map((source, i) => (
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
          </Disclosure>
        )}
      </div>
    </article>
  );
}

function AssociationsEmpty({ data, days }: { data: AssociationsResponse; days: number }) {
  const gaps = data.gaps ?? [];
  const progress = closestGap(gaps);
  const logged = loggedDaysLine(data.data_days);
  const others = gaps.filter((gap) => gap.id !== progress?.id).slice(0, 3);
  return (
    <div className={`${CARD} flex flex-col gap-4 p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center gap-4">
        <BubblesMascot size={64} mood="resting" animated={false} />
        <div className="min-w-[12rem] flex-1">
          <p className="m-0 font-display text-h4 text-ink">No link to show yet</p>
          <p className="m-0 mt-1 text-body-sm text-muted">{data.message ?? "No reliable link between the things you log yet."}</p>
        </div>
      </div>

      {progress && (
        <div
          role="progressbar"
          aria-label={`${progress.pair}, days logged together`}
          aria-valuemin={0}
          aria-valuemax={progress.need}
          aria-valuenow={Math.min(progress.have, progress.need)}
          className="h-3 overflow-hidden rounded-full bg-line"
        >
          <div className="h-full rounded-full bg-bubbles-grape" style={{ width: `${Math.round(progress.fraction * 100)}%` }} />
        </div>
      )}
      <p className="m-0 text-body text-ink">{emptyProgressLine(progress)}</p>
      {logged && <p className="m-0 text-body-sm text-muted">{logged} The last {days} days are checked.</p>}

      {others.length > 0 && (
        <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
          {others.map((gap) => (
            <li key={gap.id}>{gap.text}</li>
          ))}
        </ul>
      )}

      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {LOG_LINKS.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className={`bubbles-press inline-flex min-h-[44px] items-center rounded-full px-4 text-body-sm font-extrabold no-underline ${TONE[link.tone].chip}`}>
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LinksSection() {
  const [links, reload] = useBubblesQuery<AssociationsResponse>("/wellness/associations?days=90");
  const insights = links.status === "ready" ? links.data.insights ?? [] : [];

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
        <ul className="bubbles-stagger m-0 grid list-none gap-4 p-0 md:grid-cols-2">
          {insights.map((item) => (
            <li key={item.id}>
              <AssociationCard item={item} />
            </li>
          ))}
        </ul>
      )}
      {links.status === "ready" && insights.length === 0 && <AssociationsEmpty data={links.data} days={90} />}
    </section>
  );
}

function PatternCardView({ card }: { card: PatternCard }) {
  return (
    <article className={`${CARD} p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${PILL} ${CONFIDENCE_PILL[card.confidence]}`}>{card.confidence} confidence</span>
        <span className="text-chip font-bold text-muted">{card.window}</span>
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
                  className={`bubbles-bar w-full rounded-t ${count ? "bg-bubbles-lilac" : "bg-line"}`}
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
          <p className="text-body-sm text-muted">Gaps stay gaps. Bubbles never reads missing logs as &ldquo;fine&rdquo;.</p>
          <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
            {domains.map(([key, domain]) => {
              const status = domain.coverage_status ?? "missing";
              const style =
                status === "observed"
                  ? "bg-tint-mint text-bubbles-mint-deep"
                  : status === "sparse"
                    ? "bg-tint-sun text-bubbles-sun-deep"
                    : "border border-dashed border-line-strong text-ink-soft";
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
