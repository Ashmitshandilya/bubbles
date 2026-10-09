// Pure geometry and grouping for the hand-rolled SVG charts (weekday sleep bars, score ring, year in pixels, garden).
// No React: unit-tested in wellness-chart.test.ts.

import type { PixelDay } from "./wellness-types";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

export interface WeekdayBar {
  index: number;
  short: string;
  full: string;
  /** Average hours, or null when fewer than `minNights` nights were logged on that weekday. */
  hours: number | null;
  nights: number;
}

/** Monday-first averages from the overview `series`. A weekday with too little data is a gap (null), never zero. */
export function weekdayAverages(series: { date: string; hours: number }[] | undefined, minNights = 2): WeekdayBar[] {
  const sums = Array.from({ length: 7 }, () => ({ total: 0, n: 0 }));
  for (const row of series ?? []) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(row.date);
    if (!m || !Number.isFinite(row.hours)) continue;
    const day = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getDay(); // 0 = Sunday
    const slot = sums[(day + 6) % 7];
    slot.total += row.hours;
    slot.n += 1;
  }
  return sums.map((s, index) => ({
    index,
    short: WEEKDAYS[index].slice(0, 3),
    full: WEEKDAYS[index],
    hours: s.n >= minNights ? Math.round((s.total / s.n) * 10) / 10 : null,
    nights: s.n,
  }));
}

export interface BarBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Bar rectangles for `values` inside a width x height plot. null values get no bar. `max` defaults to the largest value. */
export function barBoxes(values: (number | null)[], width: number, height: number, max?: number, gap = 0.3): (BarBox | null)[] {
  const ceiling = Math.max(max ?? 0, ...values.map((v) => v ?? 0), 0.0001);
  const slot = width / Math.max(values.length, 1);
  const barWidth = slot * (1 - gap);
  return values.map((v, i) => {
    if (v === null || !Number.isFinite(v)) return null;
    const h = Math.max(2, (Math.max(0, v) / ceiling) * height);
    return { x: i * slot + (slot - barWidth) / 2, y: height - h, width: barWidth, height: h };
  });
}

/** stroke-dasharray values for a ring showing `percent` (0-100). */
export function ringDash(percent: number, radius: number): { circumference: number; dash: number; gap: number } {
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0));
  const dash = (clamped / 100) * circumference;
  return { circumference, dash, gap: circumference - dash };
}

/* ── Year in pixels ─────────────────────────────────────────────────── */

export const MOOD_WORDS: Record<number, string> = { 1: "Rough", 2: "Low", 3: "Okay", 4: "Good", 5: "Great" };
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export interface PixelCell {
  date: string;
  level: number | null;
  /** Text for screen readers and tooltips: "5 January: Good" or "5 January: no check-in". */
  label: string;
}

export interface PixelTable {
  /** Twelve month names, January first. */
  months: string[];
  /** 31 rows (day of month 1..31) x 12 columns (month). A day that does not exist in that month (30 February) is null. */
  rows: (PixelCell | null)[][];
}

/** Classic "year in pixels": columns are months, rows are days. Every cell carries a text label, so colour is never the only signal. */
export function pixelTable(days: PixelDay[], year: number): PixelTable {
  const byDate = new Map(days.map((d) => [d.date, d]));
  const pad = (n: number) => String(n).padStart(2, "0");
  const rows: (PixelCell | null)[][] = [];
  for (let day = 1; day <= 31; day += 1) {
    const row: (PixelCell | null)[] = [];
    for (let month = 0; month < 12; month += 1) {
      const real = new Date(year, month, day);
      if (real.getMonth() !== month) {
        row.push(null);
        continue;
      }
      const iso = `${year}-${pad(month + 1)}-${pad(day)}`;
      const level = byDate.get(iso)?.level ?? null;
      row.push({ date: iso, level, label: `${day} ${MONTHS[month]}: ${level ? MOOD_WORDS[level] : "no check-in"}` });
    }
    rows.push(row);
  }
  return { months: [...MONTHS], rows };
}

/** One-sentence text alternative for the whole year view. */
export function pixelSummary(logged: number, counts: Record<string, number>, year: number): string {
  if (logged === 0) return `No check-ins in ${year} yet.`;
  const parts = [5, 4, 3, 2, 1].filter((l) => (counts[String(l)] ?? 0) > 0).map((l) => `${counts[String(l)]} ${MOOD_WORDS[l].toLowerCase()}`);
  return `${logged} ${logged === 1 ? "day" : "days"} checked in during ${year}: ${parts.join(", ")}.`;
}

/* ── Garden ─────────────────────────────────────────────────────────── */

export const GARDEN_STAGES = ["seed", "sprout", "leaves", "blossom", "pond", "oasis"] as const;
export type GardenStage = (typeof GARDEN_STAGES)[number];

/** The API's garden level number (0-5) as a stage name; unknown values fall back to the nearest valid stage. */
export function gardenStage(level: number | null | undefined): GardenStage {
  const i = Math.max(0, Math.min(GARDEN_STAGES.length - 1, Math.floor(Number.isFinite(level as number) ? (level as number) : 0)));
  return GARDEN_STAGES[i];
}

/** Text alternative for the garden picture. Numbers only appear when the API sent a goal. */
export function gardenAlt(stage: GardenStage, percent: number | null): string {
  const base: Record<GardenStage, string> = {
    seed: "A seed resting in soil",
    sprout: "A small sprout",
    leaves: "A plant with fresh leaves",
    blossom: "A plant in blossom",
    pond: "A flowering garden beside a small pond",
    oasis: "A palm oasis with a pond and flowers",
  };
  return percent === null ? base[stage] : `${base[stage]}. Today's water gauge is ${Math.round(percent)} percent full.`;
}
