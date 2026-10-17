// One detail view for every insight: a repeated pattern, two things that show up together, a link between logged series
// (association engine) and a Today card. Pure: the same six sections in the same order for all of them.
//
// What Bubbles saw / The days and numbers / How sure / What this does not mean / One thing to try / Ask Bubbles about it.
// Everything is built from numbers and wording the server already sent. Nothing here claims a cause or a diagnosis,
// and a missing list of days is said out loud as a gap.
import { askHref } from "../lib/ask-handoff";
import { parseWhen, formatWhen } from "../lib/dates";
import { associationLevel, associationReason, levelFromLabel, recurrenceReason, togetherReason, type Level } from "./confidence";
import { caveats, sentence, topic, whatToTry, type Association } from "./associations";
import { recurrenceConfidence, type CoOccurrence, type Recurrence } from "./patterns";

export interface DetailTable {
  caption: string;
  head: string[];
  rows: string[][];
}

export interface InsightDetail {
  id: string;
  /** Short label above the title: "Repeated", "Together", "Link" or the Today card's area. */
  kindLabel: string;
  title: string;
  saw: string;
  numbers: { table: DetailTable } | { gap: string };
  sure: { word: Level | "Not enough data"; reason: string };
  not: string[];
  tryThis: string;
  ask: { label: string; href: string };
}

/** A Today card, reduced to what the sheet needs (built in today.ts / DashboardClient, never fetched). */
export interface TodayDetailSource {
  id: string;
  label: string;
  title: string;
  body?: string | null;
  evidence?: string[];
  /** null = a data gap: there is nothing to be sure about. */
  level: Level | null;
  sureReason?: string;
  /** From the brief's deviations: this week against the person's usual. */
  change?: { name: string; current: number; usual: number; percent: number | null };
  tryThis: string;
  askQuestion: string;
}

export type DetailInput =
  | { kind: "pattern"; item: Recurrence; days: number }
  | { kind: "correlation"; item: CoOccurrence; days: number }
  | { kind: "association"; item: Association }
  | { kind: "today"; item: TodayDetailSource };

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const num = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));
const day = (value: string) => formatWhen(value, true);

const NOT_A_DIAGNOSIS = "It is not a diagnosis, and it does not mean something is wrong.";
const BLANKS = "Days with no log are blanks, not good days.";

// Units for the numbers table, in the same words as the rest of the app.
const UNIT: Record<string, string> = {
  sleep_hours: " (hours)",
  hydration_ml: " (ml)",
  activity_minutes: " (minutes)",
  calories: " (kcal)",
  resting_hr: " (bpm)",
  screen_hours: " (hours)",
};

function ask(label: string, question: string) {
  return { label, href: askHref(question) };
}

function patternDetail(p: Recurrence): InsightDetail {
  const level = levelFromLabel(p.confidence_label) ?? recurrenceConfidence(p);
  const word = p.subject;
  const list = p.occurrences ?? [];
  const perDay = new Map<string, number>();
  for (const o of list) perDay.set(o.date, (perDay.get(o.date) ?? 0) + 1);
  const shown = list.length;
  const caption =
    `Days when ${word} was logged, newest first` +
    (shown && p.occurrence_count > shown ? `. Showing the newest ${shown} of ${p.occurrence_count} entries` : "");
  return {
    id: p.id ?? `rec:${p.event_type}:${p.subject}`,
    kindLabel: "Repeated",
    title: `${cap(word)} came up ${p.occurrence_count} times`,
    saw: `${cap(word)} was logged ${p.occurrence_count} times, between ${day(p.first_seen)} and ${day(p.last_seen)}.`,
    numbers: perDay.size
      ? { table: { caption, head: ["Day", "Entries"], rows: [...perDay].map(([date, n]) => [day(date), String(n)]) } }
      : { gap: `Bubbles has the count (${plural(p.occurrence_count, "time")}) but not the single days for this one yet.` },
    sure: { word: level, reason: recurrenceReason(level, p.occurrence_count, p.span_days, p.average_confidence) },
    not: [NOT_A_DIAGNOSIS, BLANKS],
    tryThis: "Keep logging when it happens, with what you were doing. If it bothers you, it is worth mentioning to a clinician.",
    ask: ask(`Ask Bubbles about ${word}`, `What do my logs say about my ${word}?`),
  };
}

function daysApart(a: string, b: string): number {
  return Math.round(Math.abs(parseWhen(a).getTime() - parseWhen(b).getTime()) / 86_400_000);
}

function correlationDetail(c: CoOccurrence): InsightDetail {
  const level = levelFromLabel(c.confidence_label) ?? (c.pair_count >= 6 ? "High" : c.pair_count >= 4 ? "Medium" : "Low");
  const a = c.a.subject;
  const b = c.b.subject;
  const pairs = c.pairs ?? [];
  return {
    id: c.id ?? `co:${c.a.event_type}:${a}|${c.b.event_type}:${b}`,
    kindLabel: "Together",
    title: `${cap(a)} and ${b} often show up together`,
    saw: c.interpretation || `${cap(a)} and ${b} were logged within ${plural(c.window_days, "day")} of each other ${plural(c.pair_count, "time")}.`,
    numbers: pairs.length
      ? {
          table: {
            caption:
              `Days when ${a} and ${b} were logged close together, newest first` +
              (c.pair_count > pairs.length ? `. Showing the newest ${pairs.length} of ${c.pair_count} pairs` : ""),
            head: [`${cap(a)} day`, `${cap(b)} day`, "Days apart"],
            rows: pairs.map((p) => [day(p.a.date), day(p.b.date), String(daysApart(p.a.date, p.b.date))]),
          },
        }
      : { gap: `Bubbles has the count (${plural(c.pair_count, "pair")}) but not the single days for this one yet.` },
    sure: { word: level, reason: togetherReason(level, c.pair_count, c.window_days) },
    not: ["It does not show that one thing causes the other.", "Two things close together can both come from something else, like a busy week or being unwell.", BLANKS],
    tryThis: "Keep logging both for a few more weeks and see whether they still show up together.",
    ask: ask(`Ask Bubbles about ${a} and ${b}`, `Do my ${a} and my ${b} seem connected in my logs?`),
  };
}

function cell(key: string, value: number): string {
  return key === "luteal" ? (value >= 0.5 ? "Yes" : "No") : num(value);
}

function associationDetail(item: Association): InsightDetail {
  const [x, y] = item.domains ?? [];
  const level = associationLevel(item.strength, item.status);
  const pairs = item.pairs ?? [];
  const lag = item.lag_days ?? 0;
  const topicX = x ? topic(x) : "the first thing";
  const topicY = y ? topic(y) : "the second thing";
  const fixed = (item.limitations ?? []).filter((l) => l.trim());
  const extra = caveats(item.text);
  return {
    id: item.id,
    kindLabel: "Link",
    title: `${sentence(item.text)}.`,
    saw: `${sentence(item.text)}. This comes from ${plural(item.n_days, "day")} where both were logged.`,
    numbers: pairs.length && x && y
      ? {
          table: {
            caption:
              `Days behind this link, newest first. Showing ${pairs.length} of ${plural(item.n_days, "day")}` +
              (lag > 0 ? `. ${cap(topicY)} is from ${lag === 1 ? "the next day" : `${lag} days later`}` : ""),
            head: ["Day", `${cap(topicX)}${UNIT[x] ?? ""}`, `${cap(topicY)}${UNIT[y] ?? ""}`],
            rows: pairs.map((p) => [day(p.date), cell(x, p.x), cell(y, p.y)]),
          },
        }
      : { gap: `Bubbles counted ${plural(item.n_days, "day")} for this link but does not have the single days to show yet.` },
    sure: { word: level, reason: associationReason(level, item.n_days, item.repeated) },
    not: fixed.length ? fixed : ["It does not show that one thing causes the other.", ...(extra ? [extra] : [])],
    tryThis: whatToTry({ domains: item.domains }),
    ask: ask(`Ask Bubbles about ${topicX} and ${topicY}`, `Is there a link between my ${topicX} and my ${topicY}?`),
  };
}

function todayDetail(t: TodayDetailSource): InsightDetail {
  const { change } = t;
  const gap = t.level === null;
  const numbers: InsightDetail["numbers"] = change
    ? {
        table: {
          caption: `${cap(change.name)}, this week against your usual`,
          head: ["Measure", "This week", "Your usual", "Change"],
          rows: [[cap(change.name), num(change.current), num(change.usual), change.percent === null ? "Not available" : `${change.percent > 0 ? "+" : ""}${num(change.percent)}%`]],
        },
      }
    : { gap: gap ? "There are no entries to list here. That is the gap." : "Bubbles does not keep a day-by-day list behind this card. The reasons are in the section above." };
  return {
    id: t.id,
    kindLabel: t.label,
    title: t.title,
    // The title is the sheet's heading, so it is not repeated here.
    saw: [...(t.body ? [t.body] : []), ...(t.evidence ?? [])].join(" ") || t.title,
    numbers,
    sure: {
      word: t.level ?? "Not enough data",
      reason: t.sureReason ?? (gap ? "Nothing has been logged here, so there is nothing to be sure about yet." : "This is based on a small amount of your own logs."),
    },
    not: gap
      ? ["A gap is not a sign that all is well.", "It does not mean something is wrong either."]
      : [NOT_A_DIAGNOSIS, "A change from your usual can have many ordinary reasons."],
    tryThis: t.tryThis,
    ask: ask(`Ask Bubbles about ${t.label.toLowerCase()}`, t.askQuestion),
  };
}

export function toDetail(input: DetailInput): InsightDetail {
  switch (input.kind) {
    case "pattern":
      return patternDetail(input.item);
    case "correlation":
      return correlationDetail(input.item);
    case "association":
      return associationDetail(input.item);
    case "today":
      return todayDetail(input.item);
  }
}

/** What GET /insights/{id} sends: the engine item plus its kind. Anything else reads as null (the sheet then says it is gone). */
export interface InsightApiDetail {
  kind: string;
  window_days?: number;
  [key: string]: unknown;
}

export function fromApi(raw: unknown, days: number): DetailInput | null {
  if (!raw || typeof raw !== "object") return null;
  const item = raw as InsightApiDetail;
  if (item.kind === "pattern") return { kind: "pattern", item: item as unknown as Recurrence, days };
  if (item.kind === "correlation") return { kind: "correlation", item: item as unknown as CoOccurrence, days };
  if (item.kind === "association") return { kind: "association", item: item as unknown as Association };
  return null;
}

/** Wording when a shared or old link points at something the current window no longer shows. */
export function goneMessage(days: number): string {
  return `This pattern is no longer in the last ${days} days.`;
}
