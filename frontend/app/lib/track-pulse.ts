// Pure helpers for the Track hub: "when did I last log this?" and a 7-day rhythm, both computed only from the
// entries a tracker already returns (GET /health/<slug>). A tracker with no entries is a gap, never a zero score.

import { parseWhen } from "./dates";

/** How far back the hub asks each tracker for entries. */
export const PULSE_WINDOW_DAYS = 30;

export interface Pulse {
  /** Entries per day, oldest first; the last item is today. Always 7 items. */
  week: number[];
  /** How many of those 7 days have at least one entry. */
  daysLogged: number;
  /** Whole days since the newest entry (0 = today); null when nothing is in the window. */
  lastAgo: number | null;
  /** True for each day in the whole window that has an entry, oldest first; the last item is today. */
  active: boolean[];
}

const DAY_MS = 86_400_000;

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function buildPulse(entries: Array<{ date: string }>, now = new Date()): Pulse {
  const week = Array<number>(7).fill(0);
  const active = Array<boolean>(PULSE_WINDOW_DAYS).fill(false);
  let lastAgo: number | null = null;
  for (const entry of entries) {
    const when = parseWhen(entry.date);
    if (Number.isNaN(when.getTime())) continue;
    const ago = Math.round((startOfDay(now) - startOfDay(when)) / DAY_MS);
    if (ago < 0) continue; // a future date is not something that was logged yet
    if (lastAgo === null || ago < lastAgo) lastAgo = ago;
    if (ago <= 6) week[6 - ago] += 1;
    if (ago < PULSE_WINDOW_DAYS) active[PULSE_WINDOW_DAYS - 1 - ago] = true;
  }
  return { week, daysLogged: week.filter((n) => n > 0).length, lastAgo, active };
}

export function lastLoggedText(p: Pulse): string {
  if (p.lastAgo === null) return `Nothing logged in the last ${PULSE_WINDOW_DAYS} days`;
  if (p.lastAgo === 0) return "Logged today";
  if (p.lastAgo === 1) return "Last logged yesterday";
  return `Last logged ${p.lastAgo} days ago`;
}

export function weekText(p: Pulse): string {
  if (p.daysLogged === 0) return "No entries in the last 7 days";
  return `Logged on ${p.daysLogged} of the last 7 days`;
}

export interface TodayRollup {
  /** Trackers we could check. */
  checked: number;
  done: string[];
  open: string[];
  /** Trackers whose entries failed to load: unknown, so neither done nor open. */
  unknown: string[];
}

/** `pulses` maps a label to its pulse, or null when that tracker could not be read. */
export function rollupToday(pulses: Array<{ label: string; pulse: Pulse | null }>): TodayRollup {
  const out: TodayRollup = { checked: 0, done: [], open: [], unknown: [] };
  for (const { label, pulse } of pulses) {
    if (!pulse) out.unknown.push(label);
    else {
      out.checked += 1;
      (pulse.lastAgo === 0 ? out.done : out.open).push(label);
    }
  }
  return out;
}

export interface CheckIns {
  /** Whole days in a row with at least one entry in any readable tracker. Today being empty yet never breaks it. */
  streak: number;
  /** The last 14 days, oldest first; the last item is today. */
  recent: boolean[];
  /** Days with an entry among those 14. */
  recentDays: number;
  /** How many trackers could be read. Zero means there is nothing to say. */
  readable: number;
}

/**
 * Check-in days across trackers: a day counts when ANY readable tracker has an entry. An unreadable tracker is skipped, so the
 * result can only undercount, never invent a day. Today being unfinished never breaks a streak.
 */
export function checkIns(pulses: Array<Pulse | null>): CheckIns {
  const readable = pulses.filter((p): p is Pulse => p !== null);
  const days = Array<boolean>(PULSE_WINDOW_DAYS).fill(false);
  for (const p of readable) p.active.forEach((on, i) => { if (on) days[i] = true; });
  let i = PULSE_WINDOW_DAYS - 1;
  if (!days[i]) i -= 1; // today not logged yet: count back from yesterday
  let streak = 0;
  while (i >= 0 && days[i]) {
    streak += 1;
    i -= 1;
  }
  const recent = days.slice(-14);
  return { streak, recent, recentDays: recent.filter(Boolean).length, readable: readable.length };
}

/** One calm sentence about the streak; never a number of missed days, never blame. `partial` = some tracker could not be read. */
export function streakText(c: CheckIns, partial = false): string {
  if (c.readable === 0) return "";
  if (c.streak >= 2) return `${partial ? "At least " : ""}${c.streak} days in a row with something logged.`;
  if (c.streak === 1) return "You logged something recently. One more day makes a run.";
  return "Every day is a fresh start. One entry is enough.";
}

/** Screen-reader sentence for the dots, gentle when nothing was logged. */
export function recentText(c: CheckIns, partial = false): string {
  if (c.recentDays === 0) return partial ? "Nothing found in the last 14 days from the trackers that could be read." : "Nothing logged in the last 14 days yet.";
  return `${partial ? "At least " : ""}${c.recentDays} of the last 14 days had something logged.`;
}

/** Provenance line under a number: "from your log, 2 days ago". Empty when there is no usable date (no claim is made). */
export function sourceLine(lastLogged: string | undefined, now = new Date()): string {
  if (!lastLogged) return "";
  const { lastAgo } = buildPulse([{ date: lastLogged }], now);
  if (lastAgo === null) return "";
  return `from your log, ${lastAgo === 0 ? "today" : lastAgo === 1 ? "yesterday" : `${lastAgo} days ago`}`;
}
