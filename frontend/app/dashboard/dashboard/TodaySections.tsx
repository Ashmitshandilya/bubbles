"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BubblesMascot } from "../../../components/BubblesMascot";
import { askHref } from "../../lib/ask-handoff";
import { TREND_WORDS, confidenceDots, sparkPath, sparkPoints } from "./brief";
import { sourceLine } from "../../lib/track-pulse";
import { formatDay, SIGNAL_META, type CycleInfo, type PatternItem, type PillKind, type SignalSummary, type TodayItem, type Trend } from "./today";
import type { SignalSlug, TrackerEntry } from "./types";

// ── Primitives ─────────────────────────────────────────────────────────────

const ICONS = {
  cycle: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  symptom: "M13 2 4 14h7l-1 8 9-12h-7z",
  sleep: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
  mood: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8.5 14.5a4.5 4.5 0 0 0 7 0M9 10h.01M15 10h.01",
  hydration: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  nutrition: "M5 19c0-8 6-14 15-14 0 9-6 15-14 15M5 19l7-7",
  activity: "M3 12h4l3-7 4 14 3-7h4",
  arrow: "M5 12h14M13 6l6 6-6 6",
  sparkle: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18",
  body: "M12 7a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM6 10h12M12 10v5M12 15l-3 6M12 15l3 6",
  refresh: "M20 11a8 8 0 1 0-1.5 5.5M20 4v7h-7",
  trendUp: "M7 17 17 7M9 7h8v8",
  trendDown: "M7 7l10 10M17 9v8H9",
  steady: "M5 12h14",
} as const;

export function Icon({ name, size = 20, className = "" }: { name: keyof typeof ICONS; size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={`shrink-0 ${className}`}>
      <path d={ICONS[name]} />
    </svg>
  );
}

/** Literal class names per signal colour (Tailwind needs them spelled out). */
const TONE: Record<SignalSlug, { ink: string; border: string; dashed: string; bar: string; tint: string }> = {
  cycle: { ink: "text-bubbles-pink-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-pink", tint: "bg-tint-pink" },
  sleep: { ink: "text-bubbles-grape-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-grape", tint: "bg-tint-grape" },
  mood: { ink: "text-bubbles-sun-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-sun", tint: "bg-tint-sun" },
  activity: { ink: "text-bubbles-peach-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-peach", tint: "bg-tint-peach" },
  hydration: { ink: "text-bubbles-sky-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-sky", tint: "bg-tint-sky" },
  nutrition: { ink: "text-bubbles-mint-deep", border: "border-line", dashed: "border-ink-faint/70", bar: "bg-bubbles-mint", tint: "bg-tint-mint" },
};

const PILL: Record<PillKind, string> = {
  high: "bg-tint-mint text-bubbles-mint-deep",
  medium: "bg-tint-grape text-bubbles-grape-deep",
  low: "bg-tint-sun text-bubbles-sun-deep",
  gap: "border border-dashed border-[#CDB9DA] text-bubbles-sky-deep",
};

function Pill({ kind, children }: { kind: PillKind; children: ReactNode }) {
  return <span className={`self-start rounded-full px-2.5 py-1 text-xs font-extrabold ${PILL[kind]}`}>{children}</span>;
}

/** How sure Bubbles is, in the wording the data already carries ("Medium confidence · 3 cycles"), with filled dots. */
function EvidenceChip({ pill }: { pill: { text: string; kind: PillKind } }) {
  const filled = confidenceDots(pill.kind);
  return (
    <span className={`inline-flex items-center gap-2 self-start rounded-full px-2.5 py-1 text-xs font-extrabold ${PILL[pill.kind]}`}>
      <span className="flex gap-[3px]" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`h-1.5 w-1.5 rounded-full ${n <= filled ? "bg-current" : "border border-current opacity-40"}`} />
        ))}
      </span>
      {pill.text}
    </span>
  );
}

const TREND_ICON = { up: "trendUp", down: "trendDown", steady: "steady" } as const;

/** Small arrow badge for "this week against your usual". Colour is the signal's own, never red or green: higher is not better. */
function TrendGlyph({ trend, slug }: { trend: Trend; slug: SignalSlug | null }) {
  const tone = slug ? TONE[slug] : null;
  return (
    <span
      role="img"
      aria-label={TREND_WORDS[trend]}
      title={TREND_WORDS[trend]}
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${tone && trend !== "steady" ? `${tone.tint} ${tone.ink}` : "bg-blush text-ink-soft"}`}
    >
      <Icon name={TREND_ICON[trend]} size={16} />
    </span>
  );
}

const SPARK_W = 64;
const SPARK_H = 24;

/** The last 7 days. Unlogged days break the line; they are never drawn as zero. */
function Spark({ bars, slug }: { bars: number[]; slug: SignalSlug }) {
  const points = sparkPoints(bars, SPARK_W, SPARK_H);
  const logged = points.filter((p) => p !== null).length;
  if (!logged) return null;
  return (
    <svg viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} width={SPARK_W} height={SPARK_H} role="img" aria-label={`Last 7 days, logged on ${logged}`} className={`hidden min-w-0 shrink min-[560px]:block ${TONE[slug].ink}`}>
      <path d={sparkPath(points)} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((p, i) => p && <circle key={i} cx={p.x} cy={p.y} r="2.2" fill="currentColor" />)}
    </svg>
  );
}

const BTN = "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full px-4 text-sm font-extrabold no-underline";
const BTN_GRAPE = `${BTN} bg-bubbles-grape text-white bubbles-glow bubbles-glow-grape`;
const BTN_SKY = `${BTN} bg-bubbles-grape text-white bubbles-glow disabled:opacity-40`;
const BTN_QUIET = `${BTN} border border-line-strong bg-surface text-ink hover:border-bubbles-grape`;

export function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return <h2 id={id} className="m-0 font-display text-[1.375rem] font-semibold sm:text-2xl">{children}</h2>;
}

// ── Greeting + Ask Bubbles ────────────────────────────────────────────────────

export function Greeting({ title, date, cycleDay }: { title: string; date: string; cycleDay?: number }) {
  const router = useRouter();
  const [question, setQuestion] = useState("");

  function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (text) router.push(askHref(text));
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-5">
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          <h1 className="m-0 font-display text-[1.75rem] font-semibold leading-tight tracking-tight sm:text-[2.25rem]">{title}</h1>
          <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[0.9375rem] font-semibold text-ink-soft sm:text-base">
            <span>{date}</span>
            {cycleDay ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-0.5 font-mono text-xs text-ink-soft">
                <span className="h-2 w-2 rounded-full bg-bubbles-pink" aria-hidden="true" />
                Cycle day {cycleDay}
              </span>
            ) : null}
          </p>
        </div>
      </div>
      <form onSubmit={ask} className="flex w-full min-w-0 items-center gap-2.5 rounded-full border border-[#E7E0EC] bg-surface py-1.5 pl-[18px] pr-1.5 shadow-[0_8px_20px_rgba(107,70,214,0.08)] focus-within:border-bubbles-grape sm:w-auto sm:min-w-[300px] sm:flex-[0_1_420px]">
        <label htmlFor="today-ask" className="sr-only">Ask Bubbles</label>
        <input
          id="today-ask"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask Bubbles…"
          maxLength={500}
          className="min-h-[44px] min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none focus-visible:outline-none"
        />
        <button type="submit" aria-label="Send to Bubbles" disabled={!question.trim()} className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-bubbles-grape text-white disabled:opacity-50">
          <Icon name="arrow" size={20} />
        </button>
      </form>
    </div>
  );
}

// ── Today's brief: one next step, then what else is worth a look ─────────────

export type HeroState = "loading" | "error" | "empty" | "clear" | "items";

interface WaterProps {
  onAddWater: () => void;
  waterBusy: boolean;
}

const BRIEF_CARD = "rounded-[24px] border border-line bg-surface shadow-sm";

export function TodayBrief({ state, items, showMascot, onRetry, onAddWater, waterBusy }: { state: HeroState; items: TodayItem[]; showMascot: boolean; onRetry: () => void } & WaterProps) {
  const lead = items[0];
  return (
    <section aria-labelledby="today-matters" aria-busy={state === "loading"} className="flex flex-col gap-4">
      <h2 id="today-matters" className="m-0 font-display text-[1.375rem] font-semibold sm:text-2xl">Your next step</h2>

      {state === "loading" && (
        <>
          <div className="bubbles-skeleton bubbles-skeleton-card h-[220px]" />
          <span className="sr-only">Loading your next step…</span>
        </>
      )}

      {state === "error" && (
        <BriefMessage title="Couldn't load your signals." body="Your data is safe. Try again.">
          <button type="button" onClick={onRetry} className={BTN_QUIET}><Icon name="refresh" size={18} />Try again</button>
        </BriefMessage>
      )}

      {state === "empty" && (
        <BriefMessage
          mascot={showMascot}
          title="Ready when you are."
          body="Log something or tell Bubbles about your day."
        >
          <Link href="/companion" className={BTN_GRAPE}>Talk to Bubbles</Link>
          <Link href="/cycle" className={BTN_QUIET}>Log your period</Link>
        </BriefMessage>
      )}

      {state === "clear" && (
        <BriefMessage
          title="Nothing stands out today."
          body="Based only on what you've logged, so not an all-clear."
        />
      )}

      {state === "items" && lead && (
        <NextStep item={lead} onAddWater={onAddWater} waterBusy={waterBusy} />
      )}
    </section>
  );
}

/** The other things worth a look: kept one tap away so Today opens on a single next step. */
export function AlsoList({ items, onAddWater, waterBusy }: { items: TodayItem[] } & WaterProps) {
  return (
    <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
      {items.map((item) => <li key={item.id} className="min-w-0"><AlsoCard item={item} onAddWater={onAddWater} waterBusy={waterBusy} /></li>)}
    </ul>
  );
}

/** A quiet row that opens on tap. Today keeps its secondary cards in these instead of stacking them. */
export function MoreFold({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <details className="group rounded-[24px] border border-line bg-surface shadow-sm">
      <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-display text-lg font-semibold text-ink">{title}</span>
        <span className="flex items-center gap-2 text-sm font-extrabold text-ink-soft">
          {hint}
          <span className="transition-transform group-open:rotate-90"><Icon name="arrow" size={16} /></span>
        </span>
      </summary>
      <div className="flex flex-col gap-4 px-4 pb-5 pt-1 sm:px-5">{children}</div>
    </details>
  );
}

function BriefMessage({ title, body, mascot = false, children }: { title: string; body: string; mascot?: boolean; children?: ReactNode }) {
  return (
    <div className={`${BRIEF_CARD} flex flex-wrap items-center gap-5 p-6`}>
      {mascot && (
        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-tint-pink">
          <BubblesMascot size={52} mood="calm" />
        </span>
      )}
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-1.5">
        <strong className="font-display text-xl font-semibold leading-snug">{title}</strong>
        <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">{body}</p>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

/** The ONE primary action. Everything else on the card is supporting evidence. */
function NextStep({ item, onAddWater, waterBusy }: { item: TodayItem } & WaterProps) {
  const tone = TONE[item.slug ?? "cycle"];
  return (
    <article className={`${BRIEF_CARD} relative flex flex-col gap-4 overflow-hidden p-6 sm:p-8`}>
      <span aria-hidden="true" className={`pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full opacity-70 ${tone.tint}`} />
      <div className="relative flex flex-wrap items-center gap-3">
        {item.trend && <TrendGlyph trend={item.trend} slug={item.slug} />}
        <span className={`text-label font-extrabold ${tone.ink}`}>{item.label}</span>
        <EvidenceChip pill={item.pill} />
      </div>
      <div data-private className="relative flex max-w-[44rem] flex-col gap-2.5">
        <strong className="font-display text-[1.5rem] font-semibold leading-snug sm:text-[2rem]">{item.headline}</strong>
        <p className="m-0 text-base leading-relaxed text-ink-soft">{item.body}</p>
      </div>
      <div className="relative flex flex-wrap items-start gap-2.5 pt-1">
        <PrimaryAction item={item} onAddWater={onAddWater} waterBusy={waterBusy} />
        {item.secondary && <Link href={item.secondary.href} className={BTN_QUIET}>{item.secondary.label}</Link>}
      </div>
      <Why item={item} />
    </article>
  );
}

function AlsoCard({ item, onAddWater, waterBusy }: { item: TodayItem } & WaterProps) {
  const tone = TONE[item.slug ?? "cycle"];
  return (
    <article className={`${BRIEF_CARD} flex h-full flex-col gap-3 p-5`}>
      <div className="flex flex-wrap items-center gap-2.5">
        {item.trend && <TrendGlyph trend={item.trend} slug={item.slug} />}
        <span className={`text-sm font-extrabold ${tone.ink}`}>{item.label}</span>
        <EvidenceChip pill={item.pill} />
      </div>
      <strong data-private className="font-display text-lg font-semibold leading-snug">{item.headline}</strong>
      <p data-private className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">{item.body}</p>
      <div className="mt-auto flex flex-wrap items-start gap-2">
        <PrimaryAction item={item} onAddWater={onAddWater} waterBusy={waterBusy} quiet />
        {item.secondary && <Link href={item.secondary.href} className={BTN_QUIET}>{item.secondary.label}</Link>}
      </div>
      <Why item={item} />
    </article>
  );
}

function PrimaryAction({ item, onAddWater, waterBusy, quiet = false }: { item: TodayItem; quiet?: boolean } & WaterProps) {
  if (item.primary === "add-water") {
    return <button type="button" onClick={onAddWater} disabled={waterBusy} className={BTN_SKY}>+ 250 ml</button>;
  }
  return <Link href={item.primary.href} className={quiet ? BTN_QUIET : BTN_GRAPE}>{item.primary.label}</Link>;
}

function Why({ item }: { item: TodayItem }) {
  if (item.whyHref) return <Link href={item.whyHref} className={`${TEXT_LINK} relative`}>Why does Bubbles think this?</Link>;
  if (!item.evidence?.length) return null;
  return (
    <details className="group relative min-w-0">
      <summary className="inline-flex min-h-[44px] cursor-pointer list-none items-center gap-1.5 text-sm font-extrabold text-bubbles-grape-deep [&::-webkit-details-marker]:hidden">
        Why does Bubbles think this?
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-open:rotate-180"><path d="m6 9 6 6 6-6" /></svg>
      </summary>
      <ul className="bubbles-rise mt-1 flex list-disc flex-col gap-1.5 rounded-[20px] bg-tint-grape py-3 pl-8 pr-4 text-sm leading-relaxed text-ink">
        {item.evidence.map((line) => <li key={line}>{line}</li>)}
      </ul>
    </details>
  );
}

// ── Quick log ──────────────────────────────────────────────────────────────
// Chips open the tracker with its log sheet already open (`?log=1`). Cycle has no such flag, so it opens the page.

const QUICK_LOG: Array<{ slug: SignalSlug | "symptom"; label: string; href: string; icon: keyof typeof ICONS; tone: SignalSlug }> = [
  { slug: "cycle", label: "Period", href: SIGNAL_META.cycle.log, icon: "cycle", tone: "cycle" },
  { slug: "symptom", label: "Symptom", href: "/symptoms?log=1", icon: "symptom", tone: "cycle" },
  { slug: "sleep", label: "Sleep", href: SIGNAL_META.sleep.log, icon: "sleep", tone: "sleep" },
  { slug: "mood", label: "Mood", href: SIGNAL_META.mood.log, icon: "mood", tone: "mood" },
  { slug: "activity", label: "Movement", href: SIGNAL_META.activity.log, icon: "activity", tone: "activity" },
  { slug: "hydration", label: "+250 ml water", href: SIGNAL_META.hydration.log, icon: "hydration", tone: "hydration" },
  { slug: "nutrition", label: "Meal", href: SIGNAL_META.nutrition.log, icon: "nutrition", tone: "nutrition" },
];

export function QuickLog({ onAddWater, waterBusy, status }: WaterProps & { status: { text: string; tone: "ok" | "error" } | null }) {
  return (
    <section aria-labelledby="today-quick-log" className="flex flex-col gap-2.5">
      <h2 id="today-quick-log" className="sr-only">Log in a tap</h2>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {QUICK_LOG.map((entry) => {
          const tone = TONE[entry.tone];
          const className = "bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full border border-line bg-surface pl-1.5 pr-4 text-[0.9375rem] font-semibold text-ink no-underline hover:border-line-strong";
          const inner = (
            <>
              <span className={`flex h-8 w-8 items-center justify-center rounded-full ${tone.tint} ${tone.ink}`}><Icon name={entry.icon} size={16} /></span>
              {entry.label}
            </>
          );
          return (
            <li key={entry.slug}>
              {entry.slug === "hydration" ? (
                <button type="button" onClick={onAddWater} disabled={waterBusy} className={`${className} disabled:opacity-60`}>{inner}</button>
              ) : (
                <Link href={entry.href} className={className}>{inner}</Link>
              )}
            </li>
          );
        })}
      </ul>
      <p role="status" className="m-0 text-sm font-bold empty:hidden">
        {status && (
          <span className={`bubbles-pop-in inline-flex rounded-full px-3 py-1 ${status.tone === "ok" ? "bg-tint-mint text-bubbles-mint-deep" : "bg-tint-urgent text-bubbles-urgent"}`}>{status.text}</span>
        )}
      </p>
    </section>
  );
}

// ── What changed this week ─────────────────────────────────────────────────

export type Tile =
  | { slug: SignalSlug; state: "loading" }
  | { slug: SignalSlug; state: "error" }
  | { slug: SignalSlug; state: "ready"; value?: string; detail: string; bars?: number[]; logged: boolean; trend?: Trend; source?: string };

export function tileFromSignal(s: SignalSummary): Tile {
  return {
    slug: s.slug, state: "ready", value: s.value, detail: s.detail, bars: s.value ? s.bars : undefined, logged: s.logged, trend: s.trend,
    source: s.value ? sourceLine(s.lastLogged) : undefined,
  };
}

export function tileFromCycle(c: CycleInfo): Tile {
  return { slug: "cycle", state: "ready", value: c.value, detail: c.detail, logged: c.logged };
}

export function SignalTiles({ tiles }: { tiles: Tile[] }) {
  return (
    <section aria-labelledby="today-signals" className="flex min-w-0 flex-col gap-3.5">
      <SectionHeading id="today-signals">This week</SectionHeading>
      <ul className="bubbles-stagger m-0 grid list-none grid-cols-2 gap-3 p-0 sm:gap-4 lg:grid-cols-3">
        {tiles.map((tile) => <li key={tile.slug} className="min-w-0"><SignalTile tile={tile} /></li>)}
      </ul>
    </section>
  );
}

function SignalTile({ tile }: { tile: Tile }) {
  const tone = TONE[tile.slug];
  const meta = SIGNAL_META[tile.slug];
  if (tile.state === "loading") return <div className="bubbles-skeleton bubbles-skeleton-card h-[120px]" aria-label={`Loading ${meta.label.toLowerCase()}`} />;

  const base = "bubbles-lift flex h-full min-h-[120px] flex-col gap-2 rounded-[24px] border bg-surface p-4 text-ink no-underline shadow-sm sm:gap-2.5 sm:p-5";
  const label = <span className={`text-sm font-extrabold ${tone.ink}`}>{meta.label}</span>;
  if (tile.state === "error") {
    return (
      <Link href={meta.href} className={`${base} ${tone.border}`}>
        {label}
        <span className="font-display text-lg font-semibold text-ink-soft">Couldn&apos;t load</span>
        <span className={`text-chip font-extrabold ${tone.ink}`}>Open tracker</span>
      </Link>
    );
  }

  const empty = !tile.value;
  return (
    <Link href={meta.href} className={`${base} ${empty ? `border-dashed ${tone.dashed}` : tone.border}`}>
      {label}
      {empty ? (
        <>
          <span className="font-display text-lg font-semibold leading-tight text-ink-soft sm:text-[1.375rem]">{tile.logged ? "Nothing this week" : "Nothing logged yet"}</span>
          <span className={`text-chip font-extrabold ${tone.ink}`}>{tile.detail}</span>
        </>
      ) : (
        <>
          <span data-private className="flex items-center justify-between gap-3">
            <span className="whitespace-nowrap font-display text-[1.625rem] font-semibold leading-tight sm:text-[1.875rem]">{tile.value}</span>
            {tile.bars && <Spark bars={tile.bars} slug={tile.slug} />}
          </span>
          <span data-private className="mt-auto flex items-center gap-2.5 text-[0.8125rem] font-medium text-ink-soft">
            {tile.trend && <TrendGlyph trend={tile.trend} slug={tile.slug} />}
            {tile.detail}
          </span>
        </>
      )}
    </Link>
  );
}

// ── Patterns + coming up ───────────────────────────────────────────────────

const CARD = "flex flex-col gap-2 rounded-[24px] border border-line bg-surface p-5 shadow-sm";
const TEXT_LINK = "inline-flex min-h-[44px] items-center self-start text-sm font-extrabold text-bubbles-pink-ink";

export function Patterns({ state, items, note, onRetry }: { state: "loading" | "error" | "ready"; items: PatternItem[]; note?: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-3.5">
      <h2 id="today-patterns" className="sr-only">Patterns Bubbles noticed</h2>
      {state === "loading" && <div className="bubbles-skeleton bubbles-skeleton-card h-[120px]" aria-label="Loading patterns" />}
      {state === "error" && (
        <div className={CARD}>
          <strong className="text-base">Bubbles couldn&apos;t load patterns right now.</strong>
          <button type="button" onClick={onRetry} className={`${TEXT_LINK} gap-1.5`}><Icon name="refresh" size={16} />Try again</button>
        </div>
      )}
      {state === "ready" && items.length === 0 && (
        <div className={CARD}>
          <Pill kind="gap">Not enough data yet</Pill>
          <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">Patterns show once you&apos;ve logged for a week or two.</p>
        </div>
      )}
      {state === "ready" && items.length > 0 && (
        <ul className="bubbles-stagger m-0 flex list-none flex-col gap-3.5 p-0">
          {items.map((item) => (
            <li key={item.id} className={CARD}>
              <EvidenceChip pill={item.pill} />
              <strong data-private className="text-base leading-snug">{item.title}</strong>
              {item.detail && <p data-private className="m-0 text-sm leading-relaxed text-ink-soft">{item.detail}</p>}
              <Link href="/insights" className={TEXT_LINK}>See the evidence</Link>
            </li>
          ))}
        </ul>
      )}
      {note && <p className="m-0 text-chip font-semibold text-ink-soft">{note}</p>}
    </div>
  );
}

export function ComingUp({ cycle, visits, loading, failed }: { cycle: CycleInfo | null; visits: TrackerEntry[] | null; loading: boolean; failed: boolean }) {
  const period = cycle?.next && cycle.daysUntil !== undefined && cycle.daysUntil >= -7 ? cycle.next : null;
  const rows = [
    ...(period ? [{ id: "period", dot: "bg-bubbles-pink", text: `Period expected · around ${formatDay(period)}` }] : []),
    ...(visits ?? []).map((v) => ({
      id: v.id,
      dot: "bg-bubbles-sky",
      text: `${v.specialty ? `${v.specialty} visit` : "Doctor visit"}${v.doctor_name ? ` with ${v.doctor_name}` : ""} · ${formatDay(v.date)}`,
    })),
  ];
  return (
    <section aria-labelledby="today-coming-up" className={`${CARD} gap-2.5`}>
      <h3 id="today-coming-up" className="sr-only">Coming up</h3>
      {loading ? (
        <div className="bubbles-skeleton h-12 rounded-2xl" aria-label="Loading what's coming up" />
      ) : rows.length ? (
        <>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {rows.map((row) => (
              <li key={row.id} data-private className="flex items-center gap-3 text-[0.9375rem] font-bold">
                <span className={`h-3 w-3 shrink-0 rounded-full ${row.dot}`} aria-hidden="true" />
                {row.text}
              </li>
            ))}
          </ul>
          {visits?.length ? <Link href="/care" className={TEXT_LINK}>Prepare questions for your visit</Link> : null}
        </>
      ) : failed ? (
        <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">Bubbles couldn&apos;t load what&apos;s coming up right now.</p>
      ) : (
        <>
          <p className="m-0 text-[0.9375rem] text-ink-soft">Nothing coming up.</p>
          <Link href="/visits" className={TEXT_LINK}>Add a doctor visit</Link>
        </>
      )}
      {failed && rows.length > 0 && <p className="m-0 text-chip font-semibold text-ink-soft">Some dates couldn&apos;t load right now.</p>}
    </section>
  );
}

export function BodyMapCard() {
  return (
    <Link href="/body" className="bubbles-lift flex min-h-[56px] items-center justify-between gap-3 rounded-[24px] border border-line bg-tint-grape px-5 py-3 text-ink no-underline shadow-sm">
      <span className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface text-bubbles-grape-deep"><Icon name="body" size={20} /></span>
        <span className="font-display text-lg font-semibold">Your body map</span>
      </span>
      <Icon name="arrow" size={18} />
    </Link>
  );
}
