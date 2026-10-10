// "Your week" recap on Today, built only from GET /insights/weekly. Pure: no fetching, no clock.
// It counts and quotes what was recorded. It never diagnoses, suggests a dose or says one thing caused another,
// and a missing record is stated as a gap, never read as "fine".
import type { InsightItem, WeeklyInsights } from "./types";

export interface WeekRecap {
  /** Up to three plain-language lines about the last 7 days. May be empty when nothing was recorded. */
  highlights: string[];
  /** Always present: what Bubbles cannot see this week. */
  gap: string;
  /** One neutral suggestion for logging next week. Never medical advice. */
  tryNext: string;
  disclaimer: string;
}

export const RECAP_DISCLAIMER = "These are observations from your logged data, not diagnoses or proof that one thing caused another.";

/** Backend event types in the words a person would use. Unknown types fall back to the type with spaces. */
const EVENT_WORDS: Record<string, string> = {
  symptom: "symptoms", menstrual_symptom: "cycle symptoms", food: "meals", hydration: "water", sleep: "sleep",
  activity: "movement", exercise: "movement", weight: "weight", vital_sign: "vitals", medication: "medication notes",
  supplement: "supplements", mood: "mood", stress: "stress", lifestyle: "daily habits", lab_result: "lab results",
  doctor_visit: "doctor visits", pregnancy_test: "pregnancy tests", wellness_checkin: "check-ins",
  medical_condition: "conditions", allergy: "allergies", vaccination: "vaccinations", medical_procedure: "procedures",
};

/** Everyday signals worth noticing when nothing was recorded for them. Each is "label" plus the event types that count. */
const CORE: Array<{ label: string; types: string[] }> = [
  { label: "sleep", types: ["sleep"] },
  { label: "mood", types: ["mood"] },
  { label: "water", types: ["hydration"] },
  { label: "movement", types: ["activity", "exercise"] },
  { label: "meals", types: ["food"] },
];

/** Words the recap must not repeat from free text: causation, diagnosis, dosing. Such a line is dropped, not reworded. */
const OFF_LIMITS =
  /\b(caus\w*|because|due to|leads? to|led to|result(?:s|ed)? (?:in|from)|diagnos\w*|prescri\w*|dos(?:e|es|ed|age|ing)|overdos\w*)\b|\b\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|iu)\b/i;
const MAX_LINE = 160;

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const joinWords = (words: string[]) => (words.length > 1 ? `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}` : words[0] ?? "");
const wordsFor = (type: string) => EVENT_WORDS[type] ?? (type.replaceAll("_", " ").trim() || "entries");

function firstSentence(text: string): string {
  const match = /^.+?[.!?](?=\s|$)/.exec(text.trim());
  return (match ? match[0] : text).trim();
}

/** A pattern line from the backend, kept short and safe. null when the line cannot be shown. */
function patternLine(item: InsightItem): string | null {
  if (item.category !== "recurrence" && item.category !== "association") return null;
  const line = firstSentence(item.description ?? "");
  if (!line || line.length > MAX_LINE || OFF_LIMITS.test(line)) return null;
  return item.category === "association" ? `${line} Seen together, not a cause.` : line;
}

/** null when the response cannot say how much was recorded (the card then stays hidden). */
export function buildWeekRecap(weekly: WeeklyInsights | null | undefined): WeekRecap | null {
  const count = weekly?.data_quality?.event_count;
  if (!weekly || typeof count !== "number" || !Number.isFinite(count) || count < 0) return null;

  const patterns = (Array.isArray(weekly.insights) ? weekly.insights : []).flatMap((item) => patternLine(item) ?? []);
  // `trend` looks back from the newest record, so it is only about this week when something was recorded this week.
  const rawSignals = weekly.trend?.signals;
  const signals = count > 0 && Array.isArray(rawSignals)
    ? rawSignals.filter((s) => s && typeof s.event_type === "string" && Number.isFinite(s.count) && s.count > 0)
    : [];
  const recorded = new Set(signals.map((s) => s.event_type));
  const top = [...signals].sort((a, b) => b.count - a.count).slice(0, 2);

  const highlights = [
    ...(count > 0 ? [`Bubbles recorded ${plural(count, "entry", "entries")} this week.`] : []),
    ...(top.length ? [`Most recorded: ${joinWords(top.map((s) => `${wordsFor(s.event_type)} (${s.count})`))}.`] : []),
    ...patterns,
  ].slice(0, 3);

  const sufficient = weekly.data_quality?.sufficient_for_pattern_detection ?? count >= 3;
  // Only claim a missing signal when the breakdown is there to check against.
  const missing = signals.length && sufficient ? CORE.filter((c) => !c.types.some((t) => recorded.has(t))).map((c) => c.label) : [];

  let gap: string;
  let tryNext: string;
  if (count === 0) {
    gap = "Nothing was recorded in the last 7 days, so there is no weekly picture yet. That is a gap, not a sign that all is well.";
    tryNext = "Tell Bubbles about one day, even in a sentence.";
  } else if (!sufficient) {
    gap = `Only ${plural(count, "entry", "entries")} this week, which is too few to look for patterns.`;
    tryNext = "Add a quick note on a few different days so Bubbles has more to compare.";
  } else if (missing.length) {
    gap = `Nothing recorded for ${joinWords(missing.slice(0, 2))} this week. Those stay blank rather than counting as fine.`;
    tryNext = `Log ${missing[0]} on a few days so Bubbles can compare it with your usual.`;
  } else if (!patterns.length) {
    gap = "No repeating patterns showed up. That reflects what was recorded, not proof that nothing is going on.";
    tryNext = "Keep logging the way you already do. A few more days gives Bubbles a steadier picture.";
  } else {
    gap = "Days with nothing recorded stay blank. Bubbles does not count them as fine.";
    tryNext = "Keep logging the way you already do. A few more days gives Bubbles a steadier picture.";
  }

  return { highlights, gap, tryNext, disclaimer: weekly.disclaimer?.trim() || RECAP_DISCLAIMER };
}
