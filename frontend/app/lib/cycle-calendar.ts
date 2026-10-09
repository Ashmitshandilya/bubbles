// Pure calendar-day helpers for the cycle section. Every date is an ISO day "YYYY-MM-DD"; arithmetic runs on UTC day
// numbers so daylight saving never shifts a day. (Never `new Date("YYYY-MM-DD")` raw: that is UTC midnight.)

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

export function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

export function parseISO(iso: string): { y: number; m: number; d: number } | null {
  const match = ISO.exec(iso);
  if (!match) return null;
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  if (m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) return null;
  return { y, m, d };
}

export const isISODate = (value: string): boolean => parseISO(value) !== null;

const pad = (n: number, width = 2) => String(n).padStart(width, "0");

export function toISO(y: number, m: number, d: number): string {
  return `${pad(y, 4)}-${pad(m)}-${pad(d)}`;
}

export function dayNumber(iso: string): number {
  const p = parseISO(iso);
  if (!p) throw new Error(`Not a calendar day: ${iso}`);
  return Date.UTC(p.y, p.m - 1, p.d) / 86400000;
}

export function fromDayNumber(n: number): string {
  const date = new Date(n * 86400000);
  return toISO(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

export const addDays = (iso: string, n: number): string => fromDayNumber(dayNumber(iso) + n);

/** Whole days from `a` to `b` (positive when b is later). */
export const diffDays = (a: string, b: string): number => dayNumber(b) - dayNumber(a);

/** The viewer's local calendar day. */
export function todayISO(now: Date = new Date()): string {
  return toISO(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** "YYYY-MM" of a day. */
export const monthOf = (iso: string): string => iso.slice(0, 7);

export function parseMonth(ym: string): { y: number; m: number } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(ym);
  if (!match) return null;
  const m = Number(match[2]);
  return m >= 1 && m <= 12 ? { y: Number(match[1]), m } : null;
}

export function addMonths(ym: string, n: number): string {
  const p = parseMonth(ym);
  if (!p) throw new Error(`Not a month: ${ym}`);
  const index = p.y * 12 + (p.m - 1) + n;
  return `${pad(Math.floor(index / 12), 4)}-${pad((index % 12) + 1)}`;
}

/** 0 = Sunday … 6 = Saturday. */
export const weekdayIndex = (iso: string): number => (((dayNumber(iso) + 4) % 7) + 7) % 7;

const SUNDAY_REGIONS = new Set(["US", "CA", "MX", "BR", "JP", "IN", "AU", "ZA", "PH", "IL", "SA", "KR", "TW", "HK"]);

/** 0 = weeks start on Sunday, 1 = Monday. Uses Intl week info when the runtime has it, else the region. */
export function defaultWeekStart(locale?: string): 0 | 1 {
  try {
    const intl = new Intl.Locale(locale ?? (typeof navigator !== "undefined" ? navigator.language : "en-GB")) as Intl.Locale & {
      weekInfo?: { firstDay: number };
      getWeekInfo?: () => { firstDay: number };
    };
    const info = intl.getWeekInfo?.() ?? intl.weekInfo;
    if (info) return info.firstDay === 7 ? 0 : 1;
    const maximized = intl.maximize();
    return maximized.region && SUNDAY_REGIONS.has(maximized.region) ? 0 : 1;
  } catch {
    return 1;
  }
}

export interface GridCell { iso: string; day: number; inMonth: boolean }

/** Rows of 7 cells covering the month, padded with days of the neighbouring months. */
export function buildMonthGrid(ym: string, weekStart: 0 | 1): GridCell[][] {
  const p = parseMonth(ym);
  if (!p) return [];
  const first = toISO(p.y, p.m, 1);
  const lead = (weekdayIndex(first) - weekStart + 7) % 7;
  const total = Math.ceil((lead + daysInMonth(p.y, p.m)) / 7) * 7;
  const start = dayNumber(first) - lead;
  const rows: GridCell[][] = [];
  for (let i = 0; i < total; i += 1) {
    const iso = fromDayNumber(start + i);
    const cell: GridCell = { iso, day: Number(iso.slice(8)), inMonth: monthOf(iso) === ym };
    if (i % 7 === 0) rows.push([]);
    rows[rows.length - 1].push(cell);
  }
  return rows;
}

export function weekdayLabels(weekStart: 0 | 1, locale?: string): Array<{ short: string; long: string }> {
  return Array.from({ length: 7 }, (_, i) => {
    const index = (weekStart + i) % 7;
    const date = new Date(2023, 0, 1 + index); // 1 Jan 2023 was a Sunday
    return {
      short: date.toLocaleDateString(locale, { weekday: "short" }),
      long: date.toLocaleDateString(locale, { weekday: "long" }),
    };
  });
}

export function monthLabel(ym: string, locale?: string, withYear = true): string {
  const p = parseMonth(ym);
  if (!p) return ym;
  return new Date(p.y, p.m - 1, 1).toLocaleDateString(locale, { month: "long", ...(withYear ? { year: "numeric" } : {}) });
}

export const yearMonths = (year: number): string[] => Array.from({ length: 12 }, (_, i) => `${pad(year, 4)}-${pad(i + 1)}`);
