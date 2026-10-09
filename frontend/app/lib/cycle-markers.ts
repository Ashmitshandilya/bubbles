// Which calendar markers a day gets. Each kind has its own SHAPE in the UI, so meaning never depends on colour alone.

import type { CalendarDay } from "./cycle-types";

export type MarkerKind =
  | "period-logged" | "period-predicted" | "period-possible"
  | "fertile-predicted" | "fertile-possible"
  | "ovulation-predicted" | "ovulation-confirmed"
  | "log";

export const MARKER_LEGEND: ReadonlyArray<{ kind: MarkerKind; label: string }> = [
  { kind: "period-logged", label: "Period (logged)" },
  { kind: "period-predicted", label: "Period (predicted)" },
  { kind: "period-possible", label: "Period (possible)" },
  { kind: "fertile-predicted", label: "Fertile window (likely)" },
  { kind: "fertile-possible", label: "Fertile window (possible)" },
  { kind: "ovulation-predicted", label: "Ovulation (estimated)" },
  { kind: "ovulation-confirmed", label: "Ovulation (confirmed)" },
  { kind: "log", label: "Has a log" },
];

/** All markers for a day, most important first. */
export function markersFor(day: CalendarDay | undefined): MarkerKind[] {
  if (!day) return [];
  const out: MarkerKind[] = [];
  if (day.period) out.push(`period-${day.period}` as MarkerKind);
  if (day.ovulation) out.push(`ovulation-${day.ovulation}` as MarkerKind);
  if (day.fertile) out.push(`fertile-${day.fertile}` as MarkerKind);
  if (day.has_log) out.push("log");
  return out;
}

/** The single marker the compact year view draws. */
export function primaryMarker(day: CalendarDay | undefined): MarkerKind | null {
  const order: MarkerKind[] = ["period-logged", "ovulation-confirmed", "ovulation-predicted", "period-predicted", "fertile-predicted", "period-possible", "fertile-possible", "log"];
  const have = markersFor(day);
  return order.find((k) => have.includes(k)) ?? null;
}

/** "5 period days logged, 4 predicted; 6 fertile days" for a month's aria-label. */
export function monthSummary(days: CalendarDay[]): string {
  const count = (fn: (d: CalendarDay) => boolean) => days.filter(fn).length;
  const logged = count((d) => d.period === "logged");
  const predicted = count((d) => d.period === "predicted" || d.period === "possible");
  const fertile = count((d) => d.fertile !== null);
  const parts: string[] = [];
  if (logged) parts.push(`${logged} period ${logged === 1 ? "day" : "days"} logged`);
  if (predicted) parts.push(`${predicted} predicted`);
  if (fertile) parts.push(`${fertile} fertile-window ${fertile === 1 ? "day" : "days"}`);
  return parts.length ? parts.join(", ") : "nothing marked";
}
