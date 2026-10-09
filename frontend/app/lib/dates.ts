// Calendar-day helpers shared by the trackers, the Today screen and the hub pages.
//
// A backend `date` is one of three things:
//   - a calendar day: "2026-10-05" (sleep, cycle, reports);
//   - an instant: "2026-10-05T14:03:11+00:00" (most logs), shown in the viewer's local time;
//   - UTC midnight: "2026-10-02T00:00:00+00:00", which is what the API returns when the user picked only a day
//     (visit and lab dates). That is a calendar day, not an instant: read as an instant it lands on the previous
//     day west of UTC and grows an invented "5:30 AM" east of it.

const DAY = /^(\d{4}-\d{2}-\d{2})$/;
const UTC_MIDNIGHT = /^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?(?:Z|\+00:00)$/;

/** "YYYY-MM-DD" when `value` names a calendar day (date-only or UTC midnight), otherwise null. */
export function calendarDay(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const match = DAY.exec(value) ?? UTC_MIDNIGHT.exec(value);
  return match ? match[1] : null;
}

/** Calendar days as LOCAL midnight; instants as themselves. Unparseable input gives an Invalid Date. */
export function parseWhen(value: string): Date {
  const day = calendarDay(value);
  if (!day) return new Date(value);
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "5 Oct" / "5 Oct 2026" in the viewer's locale; an em dash when there is nothing usable. */
export function formatWhen(value: string | null | undefined, withYear = false): string {
  if (!value) return "—";
  const date = parseWhen(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}) });
}
