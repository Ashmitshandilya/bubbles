// Pure helpers for the Privacy choices screen (choices.test.ts).

export interface Choice {
  purpose: string;
  title: string;
  what: string;
  available: boolean;
  granted: boolean;
  decidedAt: string | null;
}

export interface HistoryRow {
  purpose: string;
  title: string;
  granted: boolean;
  source: string | null;
  at: string | null;
}

export function readChoices(data: unknown): Choice[] {
  const list = (data as { consents?: unknown })?.consents;
  if (!Array.isArray(list)) return [];
  return list
    .filter((c): c is Record<string, unknown> => !!c && typeof c === "object" && typeof (c as { purpose?: unknown }).purpose === "string")
    .map((c) => ({
      purpose: String(c.purpose),
      title: typeof c.title === "string" ? c.title : String(c.purpose),
      what: typeof c.what === "string" ? c.what : "",
      available: c.available === true,
      granted: c.granted === true,
      decidedAt: typeof c.decided_at === "string" ? c.decided_at : null,
    }));
}

export function readHistory(data: unknown): HistoryRow[] {
  const list = (data as { history?: unknown })?.history;
  if (!Array.isArray(list)) return [];
  return list
    .filter((r): r is Record<string, unknown> => !!r && typeof r === "object")
    .map((r) => ({
      purpose: String(r.purpose ?? ""),
      title: typeof r.title === "string" ? r.title : String(r.purpose ?? ""),
      granted: r.granted === true,
      source: typeof r.source === "string" ? r.source : null,
      at: typeof r.at === "string" ? r.at : null,
    }));
}

/** "You turned this on on 12 Oct" / "You turned this off on 12 Oct" / "Off". */
export function decisionLine(choice: Choice, now: Date = new Date()): string {
  if (!choice.available) return "Coming soon";
  if (!choice.decidedAt) return "Off";
  const d = new Date(choice.decidedAt);
  if (Number.isNaN(d.getTime())) return choice.granted ? "On" : "Off";
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(d.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}) });
  return `${choice.granted ? "Turned on" : "Turned off"} ${day}`;
}
