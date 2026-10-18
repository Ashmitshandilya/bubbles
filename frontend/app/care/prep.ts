// Pure view-model for the Doctor prep screen (POST /doctor/prepare, POST /medical/summary, GET /health/labs|reports).
//
// /medical/summary reads the medical_reports and lab_results tables only, and flags a lab from a `flag`/`status`
// key those tables do not have (they hold `abnormal_flag` and a numeric range). Entries saved on the Labs and
// Reports pages also never reach it while the database runs in compatibility mode. So the page counts records, and
// flags results outside the range the user entered, from the same /health/<slug> lists those pages show.
import { parseRange, toNumber, type Entry } from "../../components/tracking/data";
import { parseWhen } from "../lib/dates";

export interface FlaggedLab {
  label: string;
  flag: string;
  value?: string | number | null;
  unit?: string | null;
}

export interface MedicalSummary {
  lab_count?: number;
  report_count?: number;
  flagged_labs?: FlaggedLab[];
}

/** Labs whose numeric result sits outside the "lo-hi" reference range stored with them. Never interpreted further. */
export function labsOutOfRange(labs: readonly Entry[]): FlaggedLab[] {
  return labs.flatMap((lab): FlaggedLab[] => {
    const value = toNumber(lab.value);
    const range = parseRange(lab.reference_range);
    if (value === null || !range || (value >= range[0] && value <= range[1])) return [];
    return [{
      label: String(lab.test_name || "Lab result"),
      flag: value < range[0] ? "low" : "high",
      value,
      unit: typeof lab.unit === "string" && lab.unit ? lab.unit : null,
    }];
  });
}

export interface RecordsOnFile {
  labCount: number;
  reportCount: number;
  flagged: FlaggedLab[];
}

/** `labs` / `reports` are null when their list could not be loaded; the summary alone is then all there is. */
export function mergeRecords(summary: MedicalSummary | undefined, labs: readonly Entry[] | null, reports: readonly Entry[] | null): RecordsOnFile {
  const fromBackend = summary?.flagged_labs ?? [];
  const known = new Set(fromBackend.map((l) => `${l.label}|${l.value}`));
  const fromEntries = labs ? labsOutOfRange(labs).filter((l) => !known.has(`${l.label}|${l.value}`)) : [];
  return {
    labCount: Math.max(summary?.lab_count ?? 0, labs?.length ?? 0),
    reportCount: Math.max(summary?.report_count ?? 0, reports?.length ?? 0),
    flagged: [...fromBackend, ...fromEntries],
  };
}

/* ── Visit-ready view-model: everything below uses only data the user already has on file ─────────────────────── */

const text = (e: Entry, key: string): string => {
  const v = e[key];
  return typeof v === "string" ? v.trim() : typeof v === "number" ? String(v) : "";
};

/** "5 Oct 2026", or "No date" when the record has none. Never an em dash. */
export function whenText(value: string | null | undefined): string {
  if (!value) return "No date";
  const date = parseWhen(value);
  if (Number.isNaN(date.getTime())) return "No date";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** "Dr Rao · Cardiology · Follow-up", from whatever the user filled in. */
export function visitLabel(visit: Entry): string {
  return [text(visit, "doctor_name"), text(visit, "specialty"), text(visit, "reason")].filter(Boolean).join(" · ");
}

const dayMs = (value: string): number | null => {
  const t = parseWhen(value).getTime();
  return Number.isNaN(t) ? null : t;
};

/** Newest visit that has already happened, and the soonest one still ahead. Undated visits are ignored. */
export function visitSplit(visits: readonly Entry[], now: Date = new Date()): { last: Entry | null; next: Entry | null } {
  const dated = visits.flatMap((v) => {
    const t = dayMs(v.date);
    return t === null ? [] : [{ v, t }];
  });
  const past = dated.filter((d) => d.t <= now.getTime()).sort((a, b) => b.t - a.t);
  const ahead = dated.filter((d) => d.t > now.getTime()).sort((a, b) => a.t - b.t);
  return { last: past[0]?.v ?? null, next: ahead[0]?.v ?? null };
}

/** Items logged after the calendar day of `since` (the visit day itself counts as "at the visit"). Undated items are left out. */
export function afterDay<T extends { date?: string }>(items: readonly T[], since: string): T[] {
  const start = parseWhen(since);
  if (Number.isNaN(start.getTime())) return [];
  const cutoff = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1).getTime();
  return items.filter((item) => {
    const t = item.date ? dayMs(item.date) : null;
    return t !== null && t >= cutoff;
  });
}

/** [type, count] pairs, most frequent first. */
export function typeCounts(events: readonly { event_type?: string }[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const e of events) {
    const type = e.event_type || "entry";
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

export type RangeStatus = "within" | "below" | "above" | "none";

/** Where a lab value sits against the reference range the user entered. "none" = no number or no range to compare. Never interpreted. */
export function labRangeStatus(lab: Entry): { status: RangeStatus; range: string | null } {
  const range = parseRange(lab.reference_range);
  const value = toNumber(lab.value);
  if (!range) return { status: "none", range: null };
  const label = `${range[0]}-${range[1]}`;
  if (value === null) return { status: "none", range: label };
  return { status: value < range[0] ? "below" : value > range[1] ? "above" : "within", range: label };
}

export type RecordKind = "medications" | "conditions" | "allergies" | "labs" | "reports" | "visits";

export interface RecordRow {
  id: string;
  title: string;
  meta: string;
  range?: { status: RangeStatus; range: string | null };
  /** Labs only: the day the result was logged, to match the server's note for it. */
  date?: string;
}

const join = (...parts: string[]) => parts.filter(Boolean).join(" · ");

/** One scannable row per record, newest first. Values are shown as the user entered them. */
export function recordRows(kind: RecordKind, entries: readonly Entry[]): RecordRow[] {
  const sorted = [...entries].sort((a, b) => (dayMs(b.date) ?? -Infinity) - (dayMs(a.date) ?? -Infinity));
  return sorted.map((e): RecordRow => {
    switch (kind) {
      case "medications":
        return { id: e.id, title: text(e, "name") || "Unnamed medicine", meta: join(text(e, "dosage"), text(e, "reason")) };
      case "conditions":
        return { id: e.id, title: text(e, "condition_name") || "Unnamed condition", meta: join(text(e, "status"), e.diagnosed_date ? `Since ${whenText(String(e.diagnosed_date))}` : "") };
      case "allergies":
        return { id: e.id, title: text(e, "allergen") || "Unnamed allergen", meta: join(text(e, "reaction_type"), text(e, "severity")) };
      case "labs": {
        const value = text(e, "value");
        return { id: e.id, title: text(e, "test_name") || "Lab result", meta: join(value ? `${value}${text(e, "unit") ? ` ${text(e, "unit")}` : ""}` : "No value", whenText(e.date)), range: labRangeStatus(e), date: e.date };
      }
      case "reports":
        return { id: e.id, title: text(e, "title") || "Report", meta: join(text(e, "report_type"), whenText(e.date)) };
      case "visits":
        return { id: e.id, title: visitLabel(e) || "Visit", meta: whenText(e.date) };
    }
  });
}

/** Plain text for copy / share: a heading and a numbered list. Empty string when there is nothing to send. */
export function questionsText(questions: readonly string[], heading = "Questions for my visit"): string {
  return questions.length ? [`${heading}:`, ...questions.map((q, i) => `${i + 1}. ${q}`)].join("\n") : "";
}

export const QUESTION_MAX = 200;

/** Adds the user's own question: trimmed, capped, and never a duplicate (case-insensitive). */
export function addQuestion(list: readonly string[], input: string): string[] {
  const q = input.trim().slice(0, QUESTION_MAX);
  if (!q || list.some((x) => x.toLowerCase() === q.toLowerCase())) return [...list];
  return [...list, q];
}

export interface SummaryInput {
  generatedOn: string;
  concern: string;
  lastVisit: string | null;
  nextVisit: string | null;
  logLine: string;
  /** e.g. "Since my last visit: 12 logs, 2 lab results added". Null when no visit is on file. */
  sinceLine: string | null;
  questions: readonly string[];
  bring: readonly string[];
  flagged: readonly string[];
  /** Record lists as the user entered them. A list with no rows is left out, never described as "none". */
  lists: ReadonlyArray<{ heading: string; rows: readonly string[] }>;
  timeline: readonly string[];
}

/** The plain-text visit summary for copy / share. Organised from the user's own logs, never interpreted. */
export function summaryText(i: SummaryInput): string {
  const section = (heading: string, rows: readonly string[], bullet = "- ") => (rows.length ? ["", `${heading}:`, ...rows.map((r) => `${bullet}${r}`)] : []);
  return [
    `Visit summary prepared with Bubbles, ${i.generatedOn}`,
    "Organized from my own logs. Not a diagnosis.",
    ...(i.concern ? [`What I want to discuss: ${i.concern}`] : []),
    ...(i.lastVisit ? [`Last visit on file: ${i.lastVisit}`] : []),
    ...(i.nextVisit ? [`Next visit on file: ${i.nextVisit}`] : []),
    i.logLine,
    ...(i.sinceLine ? [i.sinceLine] : []),
    ...(i.questions.length ? ["", "Questions:", ...i.questions.map((q, n) => `${n + 1}. ${q}`)] : []),
    ...section("To bring", i.bring),
    ...section("Lab results outside the reference range (flagged by the lab, or against the range entered; not interpreted by Bubbles)", i.flagged),
    ...i.lists.flatMap((l) => section(l.heading, l.rows)),
    ...section("Recent timeline", i.timeline),
  ].join("\n");
}
