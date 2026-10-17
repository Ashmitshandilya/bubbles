// One confidence scale for every place a pattern, link or Today card shows "how sure".
// Words only (High / Medium / Low) with a plain reason; the rules live on the server (pattern_engine.py) and these
// functions only read its word, or fall back to the same rule when an older response has none.

export type Level = "High" | "Medium" | "Low";

export const LEVEL_RANK: Record<Level, number> = { High: 0, Medium: 1, Low: 2 };

/** The server's `confidence_label` ("low" | "medium" | "high"), or null when it sent none. */
export function levelFromLabel(label: unknown): Level | null {
  const word = typeof label === "string" ? label.trim().toLowerCase() : "";
  return word === "high" ? "High" : word === "medium" ? "Medium" : word === "low" ? "Low" : null;
}

/** Older responses carry only a 0..1 number (the same cut-offs the backend uses for its own word). */
export function levelFromScore(score: number): Level {
  return score >= 0.75 ? "High" : score >= 0.5 ? "Medium" : "Low";
}

/** A link between two logged series: a repeated link counts for more, a weak one never reads as High. */
export function associationLevel(strength: string, status: string): Level {
  const weak = strength !== "moderate" && strength !== "strong";
  if (status === "repeated_pattern") return weak ? "Medium" : "High";
  return strength === "strong" ? "Medium" : "Low";
}

/** `level` as the lower-case pill kind Today uses. */
export const kindOf = (level: Level): "high" | "medium" | "low" => level.toLowerCase() as "high" | "medium" | "low";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** A plain reason for a repeated item. Never claims more than the count supports. */
export function recurrenceReason(level: Level, count: number, spanDays: number, averageConfidence: number): string {
  if (averageConfidence < 0.5) return "Bubbles was not sure how to read several of these entries, so treat this as a hint.";
  const span = Math.max(1, Math.round(spanDays));
  if (level === "High") return `It came up ${plural(count, "time")} over about ${plural(span, "day")}, which is a steady pattern in your logs.`;
  if (level === "Medium") return `It came up ${plural(count, "time")}. That is enough to notice, but not enough to call it steady yet.`;
  return `It has only come up ${plural(count, "time")} so far, so it could easily be chance.`;
}

export function togetherReason(level: Level, pairs: number, gapDays: number): string {
  const within = `within ${plural(gapDays, "day")} of each other`;
  if (level === "High") return `They showed up ${within} ${plural(pairs, "time")}, which is more than chance alone usually gives.`;
  if (level === "Medium") return `They showed up ${within} ${plural(pairs, "time")}. Worth watching, but not settled.`;
  return `They showed up ${within} only ${plural(pairs, "time")}, so this could easily be chance.`;
}

export function associationReason(level: Level, days: number, repeated: boolean | null | undefined): string {
  const base = `Based on ${plural(days, "day")} where both were logged.`;
  if (repeated) return `${base} The same direction showed up in two separate stretches of your logs.`;
  if (level === "Low") return `${base} It is a small difference and has not repeated across two stretches yet.`;
  return `${base} It has not yet been seen repeating across two separate stretches.`;
}
