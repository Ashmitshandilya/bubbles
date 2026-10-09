// Tolerant readers for the tracker endpoints (GET /health/<slug>), shared by the tracker pages and the Today screen.
// The backend assembles these payloads by hand (no response model), so a page must survive a missing id, a missing
// date or a nested value instead of throwing during render. Pure: no React, no fetch.
// Wire shapes are documented in backend/health_logs.py and fixtured in api-contract.test.ts.
import type { Entry } from "../../components/tracking/data";

/**
 * Entries array -> well-formed entries. Drops anything that is not an object, gives every row a string id (rows
 * are React keys) and a string date ("" = undated, shown as "Undated"), and drops nested values (never rendered).
 */
export function readEntries<T extends { id: string; date: string } = Entry>(raw: unknown): T[] {
  if (!Array.isArray(raw)) return [];
  const out: T[] = [];
  raw.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) return;
    const source = row as Record<string, unknown>;
    const entry: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(source)) {
      if (value === null || typeof value !== "object") entry[key] = value;
    }
    entry.id = source.id === undefined || source.id === null || source.id === "" ? `row-${index}` : String(source.id);
    entry.date = typeof source.date === "string" ? source.date : typeof source.created_at === "string" ? source.created_at : "";
    out.push(entry as T);
  });
  return out;
}

/** GET /health/cycle `summary`, as the Cycle page shows it. Computed by the backend from logged period starts. */
export interface CycleSummary {
  count: number;
  last: string | null;
  average: number | null;
  next: string | null;
}

export function readCycleSummary(raw: unknown): CycleSummary {
  const s = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  return {
    count: typeof s.period_start_count === "number" ? s.period_start_count : 0,
    last: typeof s.last_period === "string" ? s.last_period : null,
    average: typeof s.average_cycle_length === "number" ? s.average_cycle_length : null,
    next: typeof s.next_predicted === "string" ? s.next_predicted : null,
  };
}

/** GET /health/summary, as the Health hub shows it. Missing or malformed counts read as 0 / unknown, never NaN. */
export interface HealthSummary {
  categories: number;
  entries: number;
  days: number;
  lastUpdate: string | null;
}

export function readHealthSummary(raw: unknown): HealthSummary {
  const s = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const count = (v: unknown) => (typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.floor(v) : 0);
  return {
    categories: count(s.categories_with_data),
    entries: count(s.total_entries),
    days: count(s.days_tracked),
    lastUpdate: typeof s.last_update === "string" ? s.last_update : null,
  };
}

/* ── Fields the backend folds into free text ─────────────────────────────
   POST /health/<slug> accepts a few form fields that the live tables have no column for, so the backend appends
   them to a text column (health_logs.py: mood stress/anxiety -> notes, weight time_of_day -> notes, visit
   next_visit -> recommendations). GET returns that text, not the fields. These readers put the fields back so
   the history shows what the form collected. */

const NEXT_VISIT = /^Next visit: (\d{4}-\d{2}-\d{2})$/;
const SCALES = /(?:^|\s\|\s)((?:Stress|Anxiety) \d+(?:\.\d+)?\/10(?:; (?:Stress|Anxiety) \d+(?:\.\d+)?\/10)*)$/;
const SCALE = /^(Stress|Anxiety) (\d+(?:\.\d+)?)\/10$/;
const TIME_OF_DAY = /(?:^|\s\|\s)(morning|afternoon|evening)$/;

/** `slug` is the tracker (the path after /health/). Unknown trackers and entries without folded text pass through. */
export function adaptTrackerEntry<T extends { id: string; date: string }>(slug: string, entry: T): T {
  const e: Record<string, unknown> = { ...entry };
  const notes = typeof e.notes === "string" ? e.notes : "";
  const withNotes = (text: string) => {
    if (text) e.notes = text;
    else delete e.notes;
  };

  if (slug === "visits" && typeof e.recommendations === "string") {
    const next = NEXT_VISIT.exec(e.recommendations)?.[1];
    if (next) {
      e.next_visit = next;
      delete e.recommendations;
    }
  } else if (slug === "mood") {
    const hit = SCALES.exec(notes);
    if (hit) {
      for (const part of hit[1].split("; ")) {
        const scale = SCALE.exec(part);
        if (scale) e[scale[1].toLowerCase()] = Number(scale[2]);
      }
      withNotes(notes.slice(0, hit.index).trim());
    }
  } else if (slug === "weight") {
    const hit = TIME_OF_DAY.exec(notes);
    if (hit) {
      e.time_of_day = hit[1];
      withNotes(notes.slice(0, hit.index).trim());
    }
  }
  return e as T;
}
