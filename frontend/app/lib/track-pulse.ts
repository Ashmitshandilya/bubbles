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
}

const DAY_MS = 86_400_000;

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function buildPulse(entries: Array<{ date: string }>, now = new Date()): Pulse {
  const week = Array<number>(7).fill(0);
  let lastAgo: number | null = null;
  for (const entry of entries) {
    const when = parseWhen(entry.date);
    if (Number.isNaN(when.getTime())) continue;
    const ago = Math.round((startOfDay(now) - startOfDay(when)) / DAY_MS);
    if (ago < 0) continue; // a future date is not something that was logged yet
    if (lastAgo === null || ago < lastAgo) lastAgo = ago;
    if (ago <= 6) week[6 - ago] += 1;
  }
  return { week, daysLogged: week.filter((n) => n > 0).length, lastAgo };
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
