"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Gap, Row, Rows } from "../../../components/pearl";
import { askHref } from "../../lib/ask-handoff";
import { formatDay, SIGNAL_META, type CycleInfo, type TodayItem } from "./today";
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
  refresh: "M20 11a8 8 0 1 0-1.5 5.5M20 4v7h-7",
  sparkle: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18",
} as const;

export function Icon({ name, size = 20, className = "" }: { name: keyof typeof ICONS; size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={`shrink-0 ${className}`}>
      <path d={ICONS[name]} />
    </svg>
  );
}

export function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return <h2 id={id} className="m-0 font-display text-[1.375rem] font-semibold sm:text-2xl">{children}</h2>;
}

// ── Header: date, greeting, the one lead line, and the one input ────────────────

/** "Log something": one line that goes to Bubbles, which logs what it understands ("slept 7h, 2 glasses water, felt calm"). */
export function LogInput() {
  const router = useRouter();
  const [text, setText] = useState("");
  function send(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (value) router.push(askHref(value));
  }
  return (
    <form onSubmit={send} className="pearl-log">
      <label htmlFor="today-log" className="pearl-eyebrow">Log something</label>
      <div className="pearl-log-row">
        <input id="today-log" type="text" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} placeholder="slept 7h, 2 glasses water, felt calm" className="pearl-log-input" />
        <button type="submit" className="pearl-btn primary" disabled={!text.trim()}>Send</button>
      </div>
    </form>
  );
}

// ── Worth a look: the brief's own next steps as plain rows ───────────────────────

export function WorthALook({ items, onAddWater, waterBusy }: { items: TodayItem[]; onAddWater: () => void; waterBusy: boolean }) {
  if (!items.length) return null;
  return (
    <Rows>
      {items.slice(0, 3).map((item) =>
        item.primary === "add-water" ? (
          <Row key={item.id} label={item.headline} value={waterBusy ? "Saving…" : "Add 250 ml"} onClick={waterBusy ? undefined : onAddWater} />
        ) : (
          <Row key={item.id} label={item.headline} value={item.primary.label} href={item.primary.href} />
        ),
      )}
    </Rows>
  );
}

/** A quiet row that opens on tap. Today keeps its secondary detail in these instead of stacking boxes. */
export function MoreFold({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  // The contents mount only once opened, so a closed fold never starts its own requests.
  const [opened, setOpened] = useState(false);
  return (
    <details className="group border-b border-[color:var(--hairline)]" onToggle={(e) => setOpened((was) => was || e.currentTarget.open)}>
      <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-display text-lg font-semibold text-ink">{title}</span>
        <span className="flex items-center gap-2 text-sm font-semibold text-ink-soft">
          {hint}
          <span className="transition-transform group-open:rotate-90"><Icon name="arrow" size={16} /></span>
        </span>
      </summary>
      {opened && <div className="flex flex-col gap-4 pb-5 pt-1">{children}</div>}
    </details>
  );
}

// ── Quick log ──────────────────────────────────────────────────────────────
// Chips open the tracker with its log sheet already open (`?log=1`). Cycle has no such flag, so it opens the page.

const QUICK_LOG: Array<{ slug: SignalSlug | "symptom"; label: string; href: string; icon: keyof typeof ICONS }> = [
  { slug: "cycle", label: "Period", href: SIGNAL_META.cycle.log, icon: "cycle" },
  { slug: "symptom", label: "Symptom", href: "/symptoms?log=1", icon: "symptom" },
  { slug: "sleep", label: "Sleep", href: SIGNAL_META.sleep.log, icon: "sleep" },
  { slug: "mood", label: "Mood", href: SIGNAL_META.mood.log, icon: "mood" },
  { slug: "activity", label: "Movement", href: SIGNAL_META.activity.log, icon: "activity" },
  { slug: "hydration", label: "+250 ml water", href: SIGNAL_META.hydration.log, icon: "hydration" },
  { slug: "nutrition", label: "Meal", href: SIGNAL_META.nutrition.log, icon: "nutrition" },
];

export function QuickLog({ onAddWater, waterBusy, status, cycle = true }: { onAddWater: () => void; waterBusy: boolean; status: { text: string; tone: "ok" | "error" } | null; cycle?: boolean }) {
  return (
    <section aria-labelledby="today-quick-log" className="pearl-section">
      <h2 id="today-quick-log" className="pearl-eyebrow">Log in a tap</h2>
      <ul className="pearl-chips" style={{ listStyle: "none", padding: 0 }}>
        {QUICK_LOG.filter((entry) => cycle || entry.slug !== "cycle").map((entry) => (
          <li key={entry.slug}>
            {entry.slug === "hydration" ? (
              <button type="button" onClick={onAddWater} disabled={waterBusy} className="pearl-chip" style={{ opacity: waterBusy ? 0.6 : 1 }}>{entry.label}</button>
            ) : (
              <Link href={entry.href} className="pearl-chip" style={{ display: "inline-flex", alignItems: "center", textDecoration: "none" }}>{entry.label}</Link>
            )}
          </li>
        ))}
      </ul>
      <p role="status" className="pearl-note empty:hidden">{status?.text}</p>
    </section>
  );
}

// ── Patterns + coming up ───────────────────────────────────────────────────

/** Rows for what is next: the period window and any booked visits. Always returns the rows, so Today can also show the first one up top. */
export function comingUpRows(cycle: CycleInfo | null, visits: TrackerEntry[] | null): Array<{ id: string; label: string; value: string; href: string }> {
  const period = cycle?.next && cycle.daysUntil !== undefined && cycle.daysUntil >= -7 ? cycle.next : null;
  return [
    ...(period ? [{ id: "period", label: "Period expected", value: `around ${formatDay(period)}`, href: "/cycle" }] : []),
    ...(visits ?? []).map((v) => ({
      id: v.id,
      label: `${v.specialty ? `${v.specialty} visit` : "Doctor visit"}${v.doctor_name ? ` with ${v.doctor_name}` : ""}`,
      value: formatDay(v.date),
      href: "/care",
    })),
  ];
}

export function ComingUp({ cycle, visits, loading, failed }: { cycle: CycleInfo | null; visits: TrackerEntry[] | null; loading: boolean; failed: boolean }) {
  const rows = comingUpRows(cycle, visits);
  if (loading) return <Gap>Loading what&apos;s coming up…</Gap>;
  return (
    <div data-private>
      {rows.length ? (
        <Rows>{rows.map((row) => <Row key={row.id} label={row.label} value={row.value} href={row.href} />)}</Rows>
      ) : failed ? (
        <Gap>Bubbles couldn&apos;t load what&apos;s coming up right now.</Gap>
      ) : (
        <Gap>Nothing coming up. <Link href="/visits" className="pearl-link">Add a doctor visit</Link></Gap>
      )}
      {failed && rows.length > 0 && <p className="pearl-note">Some dates couldn&apos;t load right now.</p>}
    </div>
  );
}

export function BodyMapRow() {
  return <Rows><Row label="Your body map" href="/body" /></Rows>;
}
