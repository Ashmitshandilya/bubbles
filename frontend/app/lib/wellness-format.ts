// Pure helpers shared by the Whole-Health OS pages (sleep, hydration, medications, mind, notifications, settings).
// No React, no fetch: everything here is unit-tested in wellness-format.test.ts.

/** Minutes EAST of UTC, which is what the backend's `tz_offset_minutes` means. (JS's getTimezoneOffset is minutes WEST.) */
export function tzOffsetMinutes(now: Date = new Date()): number {
  const east = Math.round(-now.getTimezoneOffset());
  return Math.max(-840, Math.min(840, east)) || 0; // `|| 0` turns -0 into 0
}

/** "UTC+05:30" / "UTC-04:00" / "UTC" for a tz offset, for showing which zone Bubbles is using. */
export function tzLabel(offsetMinutes: number): string {
  if (!offsetMinutes) return "UTC";
  const abs = Math.abs(offsetMinutes);
  const hh = String(Math.floor(abs / 60)).padStart(2, "0");
  const mm = String(abs % 60).padStart(2, "0");
  return `UTC${offsetMinutes < 0 ? "-" : "+"}${hh}:${mm}`;
}

type Param = string | number | boolean | null | undefined;

/** Appends query parameters to a path, skipping null/undefined. */
export function withQuery(path: string, params: Record<string, Param>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  if (parts.length === 0) return path;
  return `${path}${path.includes("?") ? "&" : "?"}${parts.join("&")}`;
}

/** bubbles-my-data-2026-10-08.json */
export function exportFilename(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `bubbles-my-data-${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}.json`;
}

/** "7 h 30 min", "8 h", "45 min". null/NaN gives an em dash. */
export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || !Number.isFinite(hours) || hours < 0) return "—";
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

/** 250 -> "250 ml", 1500 -> "1.5 L", 2000 -> "2 L". */
export function formatMl(ml: number | null | undefined): string {
  if (ml === null || ml === undefined || !Number.isFinite(ml)) return "—";
  if (Math.abs(ml) < 1000) return `${Math.round(ml)} ml`;
  const litres = Math.round(ml / 10) / 100; // two decimals max
  return `${Number(litres.toFixed(2))} L`;
}

/** Short minute counts: 90 -> "1 h 30 min". */
export function formatMinutes(minutes: number): string {
  return formatHours(minutes / 60);
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** "late_meal" -> "Late meal" */
export function humanizeKey(value: string): string {
  const s = value.replaceAll("_", " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/** "07:30" -> "7:30 am"-style text is locale dependent; Bubbles shows the plain 24-hour value the API stores. */
export function isClock(value: unknown): value is string {
  return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}

/** Where the 0-100 sleep score sits, as words (never colour alone). */
export function scoreWords(value: number): string {
  if (value >= 80) return "Restful";
  if (value >= 65) return "Good";
  if (value >= 45) return "Okay";
  return "A lighter stretch";
}

/** "9+" for large badges. */
export function badgeText(count: number): string {
  if (!Number.isFinite(count) || count <= 0) return "";
  return count > 9 ? "9+" : String(Math.floor(count));
}

/** "just now", "5 min ago", "3 h ago", "yesterday", then a short date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  if (seconds < 172800) return "yesterday";
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** The server's own kind sentence (FastAPI `detail`) when it sent one for a client error, otherwise `fallback`. */
export function detailOf(status: number, body: unknown, fallback: string): string {
  if (status === 401 || status >= 500) return fallback;
  const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (d && typeof d === "object" && typeof (d as { msg?: unknown }).msg === "string" ? (d as { msg: string }).msg : ""))
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

/** Local calendar day as YYYY-MM-DD. */
export function localDay(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "2026-10-05" -> "5 Oct" (local calendar day, no UTC shift). */
export function shortDay(day: string, withWeekday = false): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(day);
  if (!m) return day;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.toLocaleDateString(undefined, { ...(withWeekday ? { weekday: "short" } : {}), day: "numeric", month: "short" });
}

/* ── Hydration wording ──────────────────────────────────────────────── */

export const BEVERAGE_ORDER = ["water", "tea", "coffee", "milk", "juice", "buttermilk", "coconut_water", "soda", "alcohol", "other"];

export function beverageLabel(type: string): string {
  return type === "coconut_water" ? "Coconut water" : humanizeKey(type);
}

/** Plain-language hint about the next reminder. Empty when there is nothing useful to say (e.g. no target). */
export function reminderHint(r: { enabled: boolean; next: string | null; due_now: string | null; reason: string | null } | null | undefined): string {
  if (!r) return "";
  if (r.reason === "no_target") return "";
  if (r.reason === "goal_reached") return "You're at your target, so there are no more reminders today.";
  if (r.reason === "not_today") return "Reminders only apply to today.";
  if (r.reason === "unsupported_hours") return "Reminders stay quiet for night-time schedules.";
  if (r.enabled && r.due_now) return "A sip would be nice around now. This is a gentle nudge, nothing more.";
  if (r.enabled && r.next) return `Next gentle reminder around ${r.next}.`;
  if (r.enabled) return "You're keeping pace, so no more reminders are needed today.";
  return "";
}

/** What to say right after a drink is logged. Alcohol and other low-factor drinks are explained, never judged. */
export function loggedMessage(ml: number, type: string, hydratingMl: number): string {
  const name = beverageLabel(type).toLowerCase();
  if (hydratingMl <= 0) return `Logged ${formatMl(ml)} of ${name}. It doesn't count toward your drinks target.`;
  if (Math.round(hydratingMl) < Math.round(ml)) return `Added ${formatMl(ml)} of ${name}, which counts as about ${formatMl(hydratingMl)} toward your target.`;
  return `Added ${formatMl(ml)} of ${name}.`;
}
