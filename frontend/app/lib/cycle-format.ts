// Wording and formatting helpers for the cycle section. Pure: no React, no network.
// Copy rules: hedged ("around", "between"), never "safe days", predictions are estimates.

import { parseISO } from "./cycle-calendar";
import type {
  CalendarDay, Confidence, DayLog, NextPeriod, OvulationEstimate, PhaseId, PregnancyInfo,
} from "./cycle-types";

export const PHASE_LABEL: Record<PhaseId, string> = {
  menstrual: "Menstrual", follicular: "Follicular", ovulatory: "Ovulatory", luteal: "Luteal",
};

/** Calendar days as local midnight (never `new Date("YYYY-MM-DD")`, which is UTC). */
function localDate(iso: string): Date | null {
  const p = parseISO(iso);
  return p ? new Date(p.y, p.m - 1, p.d) : null;
}

export function fmtDay(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" }, locale?: string): string {
  const date = iso ? localDate(iso) : null;
  return date ? date.toLocaleDateString(locale, opts) : "—";
}

export const longDay = (iso: string, locale?: string) => fmtDay(iso, { day: "numeric", month: "long" }, locale);
export const fullDay = (iso: string, locale?: string) => fmtDay(iso, { weekday: "long", day: "numeric", month: "long", year: "numeric" }, locale);
export const shortDay = (iso: string | null | undefined, locale?: string) => fmtDay(iso, { day: "numeric", month: "short" }, locale);

/** "12 Oct" for a single day, "12 Oct to 15 Oct" for a range. */
export function formatRange(earliest: string, latest: string, locale?: string): string {
  return earliest === latest ? shortDay(earliest, locale) : `${shortDay(earliest, locale)} to ${shortDay(latest, locale)}`;
}

export function relativeDays(n: number): string {
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n === -1) return "yesterday";
  return n > 0 ? `in ${n} days` : `${-n} days ago`;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export interface NextPeriodLines { range: string; likely: string; relative: string }

/** "Between 8 Nov to 12 Nov" is clumsy, so the range and the best guess are returned separately. */
export function nextPeriodLines(np: NextPeriod, locale?: string): NextPeriodLines {
  let relative: string;
  if (np.status === "late" && np.late_by_days) {
    relative = `${plural(np.late_by_days, "day")} later than the estimate. Cycles vary, so this is not unusual`;
  } else if (np.status === "due" || np.in_days === 0) {
    relative = "Due around now";
  } else {
    relative = `Expected ${relativeDays(np.in_days)}`;
  }
  return {
    range: `Between ${shortDay(np.earliest, locale)} and ${shortDay(np.latest, locale)}`,
    likely: `most likely ${shortDay(np.date, locale)}`,
    relative,
  };
}

const OVULATION_SOURCE: Record<OvulationEstimate["source"], string> = {
  calendar: "estimated from your past cycles",
  bbt: "estimated from your temperature pattern",
  lh_test: "estimated from your ovulation tests",
};
export const ovulationSourceText = (source: OvulationEstimate["source"]) => OVULATION_SOURCE[source];

const CONFIDENCE: Record<Confidence, { label: string; note: string }> = {
  learning: { label: "Still learning", note: "Bubbles needs about three logged cycles before estimates get steadier." },
  low: { label: "Low confidence", note: "Your cycles vary, so these estimates are wide. Treat them as a rough guide." },
  medium: { label: "Medium confidence", note: "Your recent cycles are fairly consistent. Estimates can still be off." },
  high: { label: "Higher confidence", note: "Your recent cycles are steady. Estimates can still be wrong." },
};
export const confidenceCopy = (c: Confidence) => CONFIDENCE[c];

/** Pregnancy: `week` is COMPLETED weeks and `day` is 0-6 extra days. */
export function pregnancyProgress(p: Pick<PregnancyInfo, "week" | "day">): string {
  return p.day > 0 ? `${p.week} weeks + ${plural(p.day, "day")}` : `${plural(p.week, "week")}`;
}

/* ── Calendar day labels ────────────────────────────────── */

export function dayAriaLabel(iso: string, day: CalendarDay | undefined, locale?: string): string {
  const parts = [longDay(iso, locale)];
  if (day) {
    if (day.is_today) parts.push("today");
    if (day.cycle_day) parts.push(`day ${day.cycle_day}`);
    if (day.period === "logged") parts.push(day.period_start ? "first day of period logged" : "period logged");
    else if (day.period === "predicted") parts.push("period predicted");
    else if (day.period === "possible") parts.push("period possible");
    if (day.fertile === "predicted") parts.push("fertile window likely");
    else if (day.fertile === "possible") parts.push("fertile window possible");
    if (day.ovulation === "confirmed") parts.push("ovulation confirmed");
    else if (day.ovulation === "predicted") parts.push("ovulation estimated");
    if (day.has_log) {
      parts.push("has a log");
      if (day.pain_level !== null) parts.push(`pain ${day.pain_level} of 10`);
    }
  }
  return parts.join(", ");
}

/* ── Temperature ────────────────────────────────────────── */

export const BBT_MIN_C = 34;
export const BBT_MAX_C = 40;

const round1 = (n: number) => Math.round(n * 10) / 10;
export const cToF = (c: number) => round1((c * 9) / 5 + 32);
export const fToC = (f: number) => round1(((f - 32) * 5) / 9);

/** Accepts "36.6", "36,6" and surrounding spaces. Null when it is not a plain number. */
export function parseTemp(text: string): number | null {
  const cleaned = text.trim().replace(",", ".");
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(cleaned)) return null;
  return Number(cleaned);
}

/** An error message, or null when the temperature (blank allowed) is fine. */
export function validateBbt(text: string, unit: "c" | "f"): string | null {
  if (!text.trim()) return null;
  const value = parseTemp(text);
  if (value === null) return "Enter the temperature as a number, like 36.5.";
  const c = unit === "f" ? fToC(value) : value;
  if (c < BBT_MIN_C || c > BBT_MAX_C) {
    return unit === "f"
      ? `Temperature should be between ${cToF(BBT_MIN_C)} and ${cToF(BBT_MAX_C)} °F.`
      : `Temperature should be between ${BBT_MIN_C} and ${BBT_MAX_C} °C.`;
  }
  return null;
}

export function formatTemp(c: number | null | undefined, unit: "c" | "f"): string {
  if (c === null || c === undefined) return "—";
  return unit === "f" ? `${cToF(c).toFixed(1)} °F` : `${c.toFixed(2).replace(/0$/, "")} °C`;
}

/* ── Short summary of a day's log ───────────────────────── */

const words = (id: string) => id.replaceAll("_", " ");

export function summarizeLog(log: DayLog | null, unit: "c" | "f" = "c"): string[] {
  if (!log) return [];
  const out: string[] = [];
  if (log.period_start) out.push("Period started");
  if (log.period_end) out.push("Period ended");
  if (log.flow && log.flow !== "none") out.push(`Flow: ${log.flow}`);
  if (log.soaking_hourly) out.push("Heavy bleeding noted");
  if (log.pain_level !== null) out.push(`Pain ${log.pain_level} of 10`);
  if (log.energy !== null) out.push(`Energy ${log.energy} of 5`);
  if (log.sleep_quality !== null) out.push(`Sleep ${log.sleep_quality} of 5`);
  const count = log.factors.length + log.custom_factors.length;
  if (count) out.push(`${count} ${count === 1 ? "symptom or feeling" : "symptoms or feelings"} noted`);
  if (log.discharge && log.discharge !== "none") out.push(`Discharge: ${words(log.discharge)}`);
  if (log.ovulation_test) out.push(`Ovulation test: ${log.ovulation_test}`);
  if (log.pregnancy_test) out.push(`Pregnancy test: ${log.pregnancy_test}`);
  if (log.bbt_c !== null) out.push(`Temperature ${formatTemp(log.bbt_c, unit)}`);
  if (log.medications.length) out.push(`Took: ${log.medications.join(", ")}`);
  if (log.notes) out.push("Note added");
  return out;
}

/** Plain text read by the length chart's text alternative. */
export function lengthsSentence(lengths: number[]): string {
  if (!lengths.length) return "No completed cycles yet.";
  const shortest = Math.min(...lengths);
  const longest = Math.max(...lengths);
  return `Your last ${plural(lengths.length, "cycle")} lasted ${lengths.join(", ")} days (oldest first). Shortest ${shortest}, longest ${longest}. A typical range is 21 to 35 days.`;
}
