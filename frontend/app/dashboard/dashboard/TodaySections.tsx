"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BubblesMascot, type BubblesMood } from "../../../components/BubblesMascot";
import { askHref } from "../../lib/ask-handoff";
import { formatDay, SIGNAL_META, type CycleInfo, type PatternItem, type PillKind, type SignalSummary, type TodayItem } from "./today";
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
  cycle: { ink: "text-bubbles-pink-deep", border: "border-line", dashed: "border-bubbles-pink", bar: "bg-bubbles-pink", tint: "bg-tint-pink" },
  sleep: { ink: "text-bubbles-grape-deep", border: "border-[#E4DCFF]", dashed: "border-[#B9A8FF]", bar: "bg-bubbles-grape", tint: "bg-tint-grape" },
  mood: { ink: "text-bubbles-sun-deep", border: "border-[#FCE8A9]", dashed: "border-bubbles-sun", bar: "bg-bubbles-sun", tint: "bg-tint-sun" },
  activity: { ink: "text-bubbles-peach-deep", border: "border-[#FFD9C8]", dashed: "border-bubbles-peach", bar: "bg-bubbles-peach", tint: "bg-tint-peach" },
  hydration: { ink: "text-bubbles-sky-deep", border: "border-[#D3ECFF]", dashed: "border-[#9FD3FF]", bar: "bg-bubbles-sky", tint: "bg-tint-sky" },
  nutrition: { ink: "text-bubbles-mint-deep", border: "border-[#CFF1E4]", dashed: "border-bubbles-mint", bar: "bg-bubbles-mint", tint: "bg-tint-mint" },
};

const PILL: Record<PillKind, string> = {
  high: "bg-tint-mint text-bubbles-mint-deep",
  medium: "bg-tint-grape text-bubbles-grape-deep",
  low: "bg-tint-sun text-bubbles-sun-deep",
  gap: "border-2 border-dashed border-[#9FD3FF] text-bubbles-sky-deep",
};

function Pill({ kind, children }: { kind: PillKind; children: ReactNode }) {
  return <span className={`self-start rounded-full px-2.5 py-1 text-xs font-extrabold ${PILL[kind]}`}>{children}</span>;
}

const BTN = "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full px-4 text-sm font-extrabold no-underline";
const BTN_GRAPE = `${BTN} bg-bubbles-grape text-white shadow-[0_4px_0_var(--bubbles-grape-deep)]`;
const BTN_SKY = `${BTN} bg-bubbles-sky-deep text-white shadow-[0_4px_0_#0B3D6B] disabled:opacity-60`;
const BTN_QUIET = `${BTN} border-2 border-[#E4DCFF] bg-surface text-bubbles-grape-deep`;
const BTN_ON_GRAPE = `${BTN} bg-surface text-bubbles-grape-deep`;

export function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return <h2 id={id} className="m-0 font-display text-[1.375rem] font-semibold sm:text-2xl">{children}</h2>;
}

// ── Greeting + Ask Bubbles ────────────────────────────────────────────────────

export function Greeting({ title, context, mood, showMascot }: { title: string; context: string; mood: BubblesMood; showMascot: boolean }) {
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
        {showMascot && (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[20px] bg-tint-pink sm:h-[72px] sm:w-[72px] sm:rounded-[24px]">
            <BubblesMascot size={56} mood={mood} className="scale-[0.82] sm:scale-100" />
          </span>
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 font-display text-[1.75rem] font-semibold leading-tight tracking-tight sm:text-[2.25rem]">{title}</h1>
          <p className="m-0 text-[0.9375rem] font-semibold text-ink-soft sm:text-base">{context}</p>
        </div>
      </div>
      <form onSubmit={ask} className="flex w-full min-w-0 items-center gap-2.5 rounded-full border-2 border-[#E4DCFF] bg-surface py-1.5 pl-[18px] pr-1.5 shadow-[0_8px_20px_rgba(106,69,245,0.08)] focus-within:border-bubbles-grape sm:w-auto sm:min-w-[300px] sm:flex-[0_1_420px]">
        <label htmlFor="today-ask" className="sr-only">Ask Bubbles</label>
        <input
          id="today-ask"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask Bubbles anything about your health…"
          maxLength={500}
          className="min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none focus-visible:outline-none"
        />
        <button type="submit" aria-label="Send to Bubbles" disabled={!question.trim()} className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-bubbles-grape text-white disabled:opacity-50">
          <Icon name="arrow" size={20} />
        </button>
      </form>
    </div>
  );
}

// ── What matters today ─────────────────────────────────────────────────────

export type HeroState = "loading" | "error" | "empty" | "clear" | "items";

interface WaterProps {
  onAddWater: () => void;
  waterBusy: boolean;
}

export function WhatMatters({ state, items, showMascot, onRetry, onAddWater, waterBusy }: { state: HeroState; items: TodayItem[]; showMascot: boolean; onRetry: () => void } & WaterProps) {
  return (
    <section aria-labelledby="today-matters" aria-busy={state === "loading"} className="flex flex-col gap-4 rounded-[28px] bg-bubbles-grape p-5 text-white shadow-[0_8px_0_var(--bubbles-grape-deep)] sm:gap-[18px] sm:rounded-[32px] sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="today-matters" className="m-0 flex items-center gap-2.5 font-display text-[1.375rem] font-semibold text-white sm:text-[1.625rem]">
          <Icon name="sparkle" size={24} className="text-bubbles-sun" />
          What matters today
        </h2>
        <span className="rounded-full bg-bubbles-grape-deep px-3 py-1.5 text-[0.8125rem] font-extrabold">From your logs · last 4 weeks</span>
      </div>

      {state === "loading" && (
        <div className="flex flex-wrap gap-3.5">
          {[0, 1].map((i) => <div key={i} className="bubbles-skeleton h-[172px] min-w-0 flex-[1_1_280px] rounded-[24px]" />)}
          <span className="sr-only">Loading what matters today…</span>
        </div>
      )}

      {state === "error" && (
        <HeroMessage title="Bubbles couldn't load your signals right now." body="Your data is safe. This is usually a connection hiccup.">
          <button type="button" onClick={onRetry} className={BTN_ON_GRAPE}><Icon name="refresh" size={18} />Try again</button>
        </HeroMessage>
      )}

      {state === "empty" && (
        <HeroMessage
          mascot={showMascot}
          title="Bubbles is ready when you are."
          body="Log your first signal or tell Bubbles how your day is going. Your picture builds from what you share, and nothing is assumed."
        >
          <Link href="/companion" className={BTN_ON_GRAPE}>Talk to Bubbles</Link>
          <Link href="/cycle" className={`${BTN} border-2 border-white/70 text-white`}>Log your period</Link>
        </HeroMessage>
      )}

      {state === "clear" && (
        <HeroMessage
          title="Nothing stands out today."
          body="That's based only on what you've logged, not proof that everything is fine. Keep logging and Bubbles will point out changes as they appear."
        />
      )}

      {state === "items" && (
        <div className="bubbles-stagger flex flex-wrap gap-3.5">
          {items.map((item) => <MattersCard key={item.id} item={item} onAddWater={onAddWater} waterBusy={waterBusy} />)}
        </div>
      )}
    </section>
  );
}

function HeroMessage({ title, body, mascot = false, children }: { title: string; body: string; mascot?: boolean; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-[24px] bg-white/10 p-5">
      {mascot && (
        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-surface">
          <BubblesMascot size={52} mood="calm" />
        </span>
      )}
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-1.5">
        <strong className="font-display text-xl font-semibold leading-snug">{title}</strong>
        <p className="m-0 text-[0.9375rem] leading-relaxed text-white">{body}</p>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

function MattersCard({ item, onAddWater, waterBusy }: { item: TodayItem } & WaterProps) {
  return (
    <article className="flex min-w-0 flex-[1_1_280px] flex-col gap-2.5 rounded-[24px] bg-surface p-5 text-ink">
      <Pill kind={item.pill.kind}>{item.label} · {item.pill.text}</Pill>
      <strong className="font-display text-xl font-semibold leading-snug">{item.headline}</strong>
      <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">{item.body}</p>
      <div className="mt-auto flex flex-wrap items-start gap-2 pt-1">
        {item.primary === "add-water" ? (
          <button type="button" onClick={onAddWater} disabled={waterBusy} className={BTN_SKY}>+ 250 ml</button>
        ) : (
          <Link href={item.primary.href} className={BTN_GRAPE}>{item.primary.label}</Link>
        )}
        {item.secondary && <Link href={item.secondary.href} className={BTN_QUIET}>{item.secondary.label}</Link>}
        {item.whyHref ? (
          <Link href={item.whyHref} className={BTN_QUIET}>Why does Bubbles think this?</Link>
        ) : item.evidence?.length ? (
          <details className="group min-w-0 open:basis-full">
            <summary className={`${BTN_QUIET} cursor-pointer list-none [&::-webkit-details-marker]:hidden`}>Why does Bubbles think this?</summary>
            <ul className="bubbles-rise mt-3 flex list-disc flex-col gap-1.5 rounded-[18px] bg-tint-grape py-3 pl-8 pr-4 text-sm leading-relaxed text-ink">
              {item.evidence.map((line) => <li key={line}>{line}</li>)}
            </ul>
          </details>
        ) : null}
      </div>
    </article>
  );
}

// ── Quick log ──────────────────────────────────────────────────────────────

const QUICK_LOG: Array<{ slug: SignalSlug | "symptom"; label: string; href: string; icon: keyof typeof ICONS; tone: SignalSlug }> = [
  { slug: "cycle", label: "Period", href: "/cycle", icon: "cycle", tone: "cycle" },
  { slug: "symptom", label: "Symptom", href: "/symptoms", icon: "symptom", tone: "cycle" },
  { slug: "sleep", label: "Sleep", href: "/sleep", icon: "sleep", tone: "sleep" },
  { slug: "mood", label: "Mood", href: "/mood", icon: "mood", tone: "mood" },
  { slug: "hydration", label: "+250 ml water", href: "/hydration", icon: "hydration", tone: "hydration" },
  { slug: "nutrition", label: "Meal", href: "/nutrition", icon: "nutrition", tone: "nutrition" },
];

export function QuickLog({ onAddWater, waterBusy, status }: WaterProps & { status: { text: string; tone: "ok" | "error" } | null }) {
  return (
    <section aria-labelledby="today-quick-log" className="flex flex-col gap-2.5">
      <h2 id="today-quick-log" className="m-0 font-display text-[1.1875rem] font-semibold sm:sr-only">Quick log</h2>
      <ul className="m-0 grid list-none grid-cols-3 gap-2.5 p-0 sm:flex sm:flex-wrap">
        {QUICK_LOG.map((entry) => {
          const tone = TONE[entry.tone];
          const className = `bubbles-press flex min-h-[76px] w-full flex-col items-center justify-center gap-1.5 rounded-[20px] px-2 text-center text-xs font-extrabold no-underline ${tone.tint} ${tone.ink} sm:min-h-[48px] sm:w-auto sm:flex-row sm:rounded-full sm:border-2 sm:bg-surface sm:px-[18px] sm:text-[0.9375rem] ${tone.border}`;
          return (
            <li key={entry.slug}>
              {entry.slug === "hydration" ? (
                <button type="button" onClick={onAddWater} disabled={waterBusy} className={`${className} disabled:opacity-60`}>
                  <Icon name={entry.icon} size={20} />{entry.label}
                </button>
              ) : (
                <Link href={entry.href} className={className}>
                  <Icon name={entry.icon} size={20} />{entry.label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
      <p role="status" className="m-0 min-h-[1.5rem] text-sm font-bold">
        {status && (
          <span className={`bubbles-pop-in inline-flex rounded-full px-3 py-1 ${status.tone === "ok" ? "bg-tint-mint text-bubbles-mint-deep" : "bg-tint-urgent text-bubbles-urgent"}`}>{status.text}</span>
        )}
      </p>
    </section>
  );
}

// ── Signals this week ──────────────────────────────────────────────────────

export type Tile =
  | { slug: SignalSlug; state: "loading" }
  | { slug: SignalSlug; state: "error" }
  | { slug: SignalSlug; state: "ready"; value?: string; detail: string; bars?: number[]; logged: boolean };

export function tileFromSignal(s: SignalSummary): Tile {
  return { slug: s.slug, state: "ready", value: s.value, detail: s.detail, bars: s.value ? s.bars : undefined, logged: s.logged };
}

export function tileFromCycle(c: CycleInfo): Tile {
  return { slug: "cycle", state: "ready", value: c.value, detail: c.detail, logged: c.logged };
}

export function SignalTiles({ tiles }: { tiles: Tile[] }) {
  return (
    <section aria-labelledby="today-signals" className="flex min-w-0 flex-[2_1_520px] flex-col gap-3.5">
      <SectionHeading id="today-signals">Your signals this week</SectionHeading>
      <ul className="bubbles-stagger m-0 grid list-none grid-cols-2 gap-2.5 p-0 sm:grid-cols-3 sm:gap-3.5">
        {tiles.map((tile) => <li key={tile.slug} className="min-w-0"><SignalTile tile={tile} /></li>)}
      </ul>
    </section>
  );
}

function SignalTile({ tile }: { tile: Tile }) {
  const tone = TONE[tile.slug];
  const meta = SIGNAL_META[tile.slug];
  if (tile.state === "loading") return <div className="bubbles-skeleton h-[148px] rounded-[22px] sm:rounded-[24px]" aria-label={`Loading ${meta.label.toLowerCase()}`} />;

  const base = "bubbles-lift flex h-full min-h-[148px] flex-col gap-2 rounded-[22px] border-2 bg-surface p-4 text-ink no-underline sm:gap-2.5 sm:rounded-[24px] sm:p-[18px]";
  const label = <span className={`text-sm font-extrabold ${tone.ink}`}>{meta.label}</span>;
  if (tile.state === "error") {
    return (
      <Link href={meta.href} className={`${base} ${tone.border}`}>
        {label}
        <span className="font-display text-lg font-semibold text-ink-soft">Couldn&apos;t load</span>
        <span className={`text-[0.8125rem] font-extrabold ${tone.ink}`}>Open tracker</span>
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
          <span className={`text-[0.8125rem] font-extrabold ${tone.ink}`}>{tile.detail}</span>
        </>
      ) : (
        <>
          <span className="font-display text-[1.625rem] font-semibold leading-tight sm:text-[1.875rem]">{tile.value}</span>
          {tile.bars && (
            <span className="flex h-[34px] items-end gap-[5px]" aria-hidden="true">
              {tile.bars.map((height, i) => (
                <span
                  key={i}
                  className={`bubbles-bar flex-1 rounded-md ${height > 0 ? tone.bar : tone.tint}`}
                  style={{ height: `${height > 0 ? Math.max(height * 100, 12) : 8}%`, animationDelay: `${i * 40}ms` }}
                />
              ))}
            </span>
          )}
          <span className="mt-auto text-[0.8125rem] font-semibold text-ink-soft">{tile.detail}</span>
        </>
      )}
    </Link>
  );
}

// ── Patterns + coming up ───────────────────────────────────────────────────

const CARD = "flex flex-col gap-2 rounded-[24px] border-2 border-line bg-surface p-[18px]";
const TEXT_LINK = "inline-flex min-h-[44px] items-center self-start text-sm font-extrabold text-bubbles-pink-ink";

export function Patterns({ state, items, note, onRetry }: { state: "loading" | "error" | "ready"; items: PatternItem[]; note?: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-3.5">
      <SectionHeading id="today-patterns">Patterns Bubbles noticed</SectionHeading>
      {state === "loading" && <div className="bubbles-skeleton h-[120px] rounded-[24px]" aria-label="Loading patterns" />}
      {state === "error" && (
        <div className={CARD}>
          <strong className="text-base">Bubbles couldn&apos;t load patterns right now.</strong>
          <button type="button" onClick={onRetry} className={`${TEXT_LINK} gap-1.5`}><Icon name="refresh" size={16} />Try again</button>
        </div>
      )}
      {state === "ready" && items.length === 0 && (
        <div className={CARD}>
          <Pill kind="gap">Not enough data yet</Pill>
          <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">Bubbles looks for repeats once you&apos;ve logged for a week or two, and won&apos;t guess before then.</p>
        </div>
      )}
      {state === "ready" && items.length > 0 && (
        <ul className="bubbles-stagger m-0 flex list-none flex-col gap-3.5 p-0">
          {items.map((item) => (
            <li key={item.id} className={CARD}>
              <Pill kind={item.pill.kind}>{item.pill.text}</Pill>
              <strong className="text-base leading-snug">{item.title}</strong>
              {item.detail && <p className="m-0 text-sm leading-relaxed text-ink-soft">{item.detail}</p>}
              <Link href="/insights" className={TEXT_LINK}>See the evidence</Link>
            </li>
          ))}
        </ul>
      )}
      {note && <p className="m-0 text-[0.8125rem] font-semibold text-ink-soft">{note}</p>}
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
      <h3 id="today-coming-up" className="m-0 font-display text-lg font-semibold">Coming up</h3>
      {loading ? (
        <div className="bubbles-skeleton h-12 rounded-2xl" aria-label="Loading what's coming up" />
      ) : rows.length ? (
        <>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {rows.map((row) => (
              <li key={row.id} className="flex items-center gap-3 text-[0.9375rem] font-bold">
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
          <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">
            Nothing on the calendar yet. Bubbles can estimate your next period after two logged period starts.
          </p>
          <Link href="/visits" className={TEXT_LINK}>Add a doctor visit</Link>
        </>
      )}
      {failed && rows.length > 0 && <p className="m-0 text-[0.8125rem] font-semibold text-ink-soft">Some dates couldn&apos;t load right now.</p>}
    </section>
  );
}

export function BodyMapCard() {
  return (
    <section aria-labelledby="today-body-map" className="flex flex-col gap-3 rounded-[24px] border-2 border-[#E4DCFF] bg-tint-grape p-5">
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-surface text-bubbles-grape-deep"><Icon name="body" size={24} /></span>
      <h2 id="today-body-map" className="m-0 font-display text-xl font-semibold">Your body map</h2>
      <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">See which body systems Bubbles has evidence for, and where it still needs data. It organises evidence; it doesn&apos;t measure organ health.</p>
      <Link href="/health" className={`${BTN_QUIET} self-start`}>See your body map <Icon name="arrow" size={18} /></Link>
    </section>
  );
}
