// The one detail view every insight opens: patterns, links between logs and Today's items all become an InsightDetail,
// so the sections, the confidence words and the "what this does not mean" wording are the same everywhere. Pure, no React.
import { caveats, sentence, topic, whatToTry, type Association } from "./associations";
import type { PatternCard } from "./patterns";

export type Sureness = "Early" | "Fairly steady" | "Steadier";

export interface InsightDetail {
  id: string;
  title: string;
  /** What Bubbles saw, in a sentence or two. */
  saw: string;
  /** The days and numbers: a real table, or null with `gap` saying why there is none. */
  table: { caption: string; head: string[]; rows: string[][] } | null;
  gap: string;
  how: { word: Sureness; reason: string };
  /** What this does NOT mean. */
  not: string[];
  /** One thing to try. */
  tryThis: string;
  /** Text handed to the chat when the person taps "Ask Bubbles about it". */
  ask: string;
}

/** One scale for every surface. An unknown level reads as the weakest, never the strongest. */
export function sureness(level: string): Sureness {
  const l = level.toLowerCase();
  return l === "high" || l === "strong" ? "Steadier" : l === "medium" || l === "moderate" ? "Fairly steady" : "Early";
}

const REASON: Record<Sureness, string> = {
  Early: "There are only a few entries so far, so this could change as you keep logging.",
  "Fairly steady": "It has shown up several times, but more weeks of logging would make it clearer.",
  Steadier: "It has shown up many times over a longer stretch.",
};

const NOT_CAUSE = "It does not mean one thing causes the other, and it is not a diagnosis.";
const NOT_PERSON = "It says nothing about days you did not log. Missing days are gaps, not good days.";

export function fromPattern(card: PatternCard): InsightDetail {
  const word = sureness(card.confidence);
  return {
    id: card.key,
    title: card.headline,
    saw: `${card.headline}. ${card.window}.`,
    table: { caption: "What Bubbles counted", head: ["Detail"], rows: card.evidence.map((line) => [line]) },
    gap: "",
    how: { word, reason: REASON[word] },
    not: [card.note, NOT_PERSON],
    tryThis: "Keep logging as you normally do. If it bothers you, mention it at your next visit with the dates.",
    ask: `Tell me more about this pattern: ${card.headline}`,
  };
}

export function fromAssociation(item: Association): InsightDetail {
  const word = sureness(item.strength);
  const [x, y] = item.domains ?? [];
  const rows: string[][] = [];
  if (x && y) rows.push(["Compared", `${topic(x)} and ${topic(y)}`]);
  rows.push(["Days with both logged", String(item.n_days)]);
  if (typeof item.lag_days === "number") rows.push(["Gap between them", item.lag_days === 0 ? "Same day" : `${item.lag_days} day${item.lag_days === 1 ? "" : "s"}`]);
  if (item.direction) rows.push(["Direction", item.direction === "up" ? "Tend to be high together" : "One high when the other is low"]);
  const note = caveats(item.text);
  return {
    id: item.id,
    title: sentence(item.text),
    saw: sentence(item.text),
    table: { caption: "The numbers behind this link", head: ["What", "Value"], rows },
    gap: "",
    how: { word, reason: REASON[word] },
    not: [NOT_CAUSE, ...(note ? [note] : []), NOT_PERSON],
    tryThis: whatToTry(item),
    ask: `Tell me more about this link: ${sentence(item.text)}`,
  };
}

export interface TodayInsight {
  id: string;
  title: string;
  detail?: string;
  pill?: { text: string };
}

/** Today's items carry a headline and a sentence but no numbers, so the table is a stated gap rather than an invented one. */
export function fromToday(item: TodayInsight): InsightDetail {
  const word: Sureness = "Early";
  return {
    id: item.id,
    title: item.title,
    saw: item.detail ? `${item.title} ${item.detail}` : item.title,
    table: null,
    gap: "Today's note is a short summary. The Patterns page shows the days behind it.",
    how: { word, reason: REASON[word] },
    not: [NOT_CAUSE, NOT_PERSON],
    tryThis: "Keep logging as you normally do and check Patterns again in a few weeks.",
    ask: `Tell me more about this: ${item.title}`,
  };
}

/** `?item=` value to open, or null. Only a short URL-safe id is accepted. */
export function itemFromSearch(search: string): string | null {
  const value = new URLSearchParams(search).get("item");
  return value && /^[\w:|>.\-]{1,120}$/.test(value) ? value : null;
}
