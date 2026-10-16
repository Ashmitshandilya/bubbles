/** Pure pieces of the Mind hub: the one-tap quick scores, the soft brain wording and the chat hand-off questions. */
import type { OrganStatus } from "../lib/organ-map";

export type QuickKind = "loneliness" | "anxiety";

export interface QuickSpec {
  kind: QuickKind;
  question: string;
  /** Every tappable value with the word shown under it (empty for most of the 0 to 10 row). */
  options: { value: number; label: string }[];
}

const LONELY_WORDS = ["Never", "Rarely", "Sometimes", "Often", "Almost always"];

export const QUICK: Record<QuickKind, QuickSpec> = {
  loneliness: {
    kind: "loneliness",
    question: "How often do you feel lonely?",
    options: LONELY_WORDS.map((label, i) => ({ value: i + 1, label })),
  },
  anxiety: {
    kind: "anxiety",
    question: "How anxious do you feel right now?",
    options: Array.from({ length: 11 }, (_, value) => ({ value, label: value === 0 ? "calm" : value === 10 ? "very" : "" })),
  },
};

/** What the brain area says on the Mind page. Same four states as the body map, in gentler words, and no state ever says "fine". */
const BRAIN_WORDS: Record<OrganStatus, string> = {
  no_data: "Nothing to read yet. A check-in or two will start it.",
  steady: "Nothing stands out in what you have logged.",
  worth_watching: "Worth a gentle look. Small habits can help.",
  talk_to_doctor: "Worth talking through with someone you trust or a doctor.",
};

export function softBrain(status: OrganStatus | undefined): string {
  return BRAIN_WORDS[status ?? "no_data"] ?? BRAIN_WORDS.no_data;
}

/** The question a topic hands to chat. Plain first person, no labels. */
export const ASK: Record<"loneliness" | "apart" | "panic", string> = {
  loneliness: "I have been feeling lonely lately and I would like to talk about it.",
  apart: "I am missing someone and being apart is hard right now.",
  panic: "I feel panicky and I would like some help calming down.",
};
