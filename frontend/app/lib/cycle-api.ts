// Request-path helpers for /cycle/*. The server defaults "today" to the UTC date, which is the wrong day for people
// east or west of UTC around midnight, so every endpoint that reasons about today is sent the viewer's local day.

/** `/cycle/overview` -> `/cycle/overview?today=2026-10-08`; keeps any existing query string. */
export function withToday(path: string, today: string): string {
  return `${path}${path.includes("?") ? "&" : "?"}today=${encodeURIComponent(today)}`;
}

export const calendarPath = (arg: { month: string } | { year: number }, today: string) =>
  withToday("month" in arg ? `/cycle/calendar?month=${encodeURIComponent(arg.month)}` : `/cycle/calendar?year=${arg.year}`, today);

export const dayPath = (date: string, today: string) => withToday(`/cycle/day/${encodeURIComponent(date)}`, today);

export const reportPath = (months: number, includeNotes: boolean, today: string) =>
  withToday(`/cycle/report?months=${months}&include_notes=${includeNotes ? "true" : "false"}`, today);

/** Body for POST /cycle/period/start|end (the endpoint accepts only `date` and `today`). */
export function periodBody(date: string | null, today: string): { date?: string; today: string } {
  return date && date !== today ? { date, today } : { today };
}
