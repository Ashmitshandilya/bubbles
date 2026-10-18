// Pure reader for GET /nutrients/nudges (backend deficiency_map.py): soft "might be worth a blood test" items for Today,
// and plain notes on logged lab results for Care. The wording comes from the server; this only checks the shape, so an odd
// answer shows less, never something invented. Missing data stays a gap line, never "fine".
export type NudgeLevel = "low" | "medium";

export interface Nudge {
  id: string;
  headline: string;
  level: NudgeLevel;
  reasons: string[];
  gaps: string[];
  ask: string;
}

export type LabNoteStatus = "below" | "above" | "within" | "no_range" | "no_number";

export interface LabNote {
  label: string;
  status: LabNoteStatus;
  text: string;
  /** Day the result was logged, YYYY-MM-DD. */
  date: string | null;
  ask: string | null;
}

const STATUSES: readonly string[] = ["below", "above", "within", "no_range", "no_number"];
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const str = (v: unknown): string => (typeof v === "string" ? v.trim() : "");
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.map(str).filter(Boolean) : []);

export function readNudges(raw: unknown): Nudge[] {
  const list = rec(raw)?.nudges;
  if (!Array.isArray(list)) return [];
  return list.flatMap((item): Nudge[] => {
    const n = rec(item);
    const headline = str(n?.headline);
    if (!n || !headline) return [];
    return [{ id: str(n.id) || headline, headline, level: n.level === "medium" ? "medium" : "low", reasons: strings(n.reasons), gaps: strings(n.gaps), ask: str(n.ask) }];
  });
}

export function readLabNotes(raw: unknown): LabNote[] {
  const list = rec(raw)?.lab_notes;
  if (!Array.isArray(list)) return [];
  return list.flatMap((item): LabNote[] => {
    const n = rec(item);
    const text = str(n?.text);
    if (!n || !text || !STATUSES.includes(str(n.status))) return [];
    return [{ label: str(n.label), status: str(n.status) as LabNoteStatus, text, date: str(n.date).slice(0, 10) || null, ask: str(n.ask) || null }];
  });
}

/** The note for one lab row: same test name and same day. Older results of the same test get none (the server notes the latest). */
export function noteForLab(notes: readonly LabNote[], title: string, date: string | undefined): LabNote | null {
  const day = (date ?? "").slice(0, 10);
  return notes.find((n) => n.label.toLowerCase() === title.trim().toLowerCase() && n.date === day) ?? null;
}

/** The label on a nudge chip. Plain words for how sure the server is. */
export const LEVEL_TEXT: Record<NudgeLevel, string> = { low: "A small hint", medium: "A stronger hint" };
