// Pure helpers for "How Bubbles understands you" (understanding.test.ts). The server sends plain sentences; nothing here quotes a chat message.

export type Sureness = "Not sure yet" | "Fairly sure" | "Sure";

export interface Trait {
  id: string;
  line: string;
  why: string;
  confidence: Sureness;
  state: "inferred" | "confirmed";
}

export interface Understanding {
  traits: Trait[];
  intro: string;
  wouldUse: string[];
}

const SURENESS: readonly string[] = ["Not sure yet", "Fairly sure", "Sure"];

export function readUnderstanding(data: unknown): Understanding | null {
  if (!data || typeof data !== "object" || !Array.isArray((data as { traits?: unknown }).traits)) return null;
  const d = data as { traits: unknown[]; intro?: unknown; would_use?: unknown };
  const traits = d.traits
    .filter((t): t is Record<string, unknown> => !!t && typeof t === "object" && typeof (t as { id?: unknown }).id === "string" && typeof (t as { line?: unknown }).line === "string")
    .map((t) => ({
      id: String(t.id),
      line: String(t.line),
      why: typeof t.why === "string" ? t.why : "",
      confidence: (SURENESS.includes(String(t.confidence)) ? t.confidence : "Not sure yet") as Sureness,
      state: t.state === "confirmed" ? ("confirmed" as const) : ("inferred" as const),
    }));
  return {
    traits,
    intro: typeof d.intro === "string" ? d.intro : "Bubbles is still getting to know you.",
    wouldUse: Array.isArray(d.would_use) ? d.would_use.filter((s): s is string => typeof s === "string") : [],
  };
}

export const actionBody = (action: "confirm" | "reject") => JSON.stringify({ action });

/** "how long you like replies to be, the tone you like and when you are usually around" */
export function joinWords(items: readonly string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
