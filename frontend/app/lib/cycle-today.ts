// Wording for the cycle "Today" header. Pure: no React, no network.
// Everything here is an estimate drawn from the user's own logs; missing data is said out loud, never filled in.

import { diffDays } from "./cycle-calendar";
import { PHASE_LABEL } from "./cycle-format";
import type { Confidence, NextPeriod, PhaseId, SymptomByPhase } from "./cycle-types";

/** The ring draws progress against a typical 28 days until Bubbles has learned the user's own length. */
export const TYPICAL_LENGTH = 28;

/** "Day 14 of about 28", or an honest line when the length is not known yet or the day is past it. */
export function cycleDayLine(day: number, averageLength: number | null): string {
  if (averageLength === null) {
    return `Day ${day}. Bubbles is still learning your usual length, so the ring uses a typical ${TYPICAL_LENGTH} days.`;
  }
  const length = Math.round(averageLength);
  return day > length ? `Day ${day}, past your usual length of about ${length} days` : `Day ${day} of about ${length}`;
}

/** How wide the next-period window is, and why. The range itself comes from nextPeriodLines. */
export function nextPeriodUncertainty(np: Pick<NextPeriod, "earliest" | "latest">, confidence: Confidence): string {
  const span = Math.max(1, diffDays(np.earliest, np.latest) + 1);
  const width = span === 1 ? "A single-day window" : `A window of about ${span} days`;
  const why: Record<Confidence, string> = {
    learning: "Still a rough guess while Bubbles learns your rhythm.",
    low: "Wide because your cycles vary.",
    medium: "Based on your recent cycles.",
    high: "Based on your recent, steady cycles.",
  };
  return `${width}. ${why[confidence]} The real day can fall outside it.`;
}

export interface PhaseStep { id: PhaseId; label: string; here: boolean }

const ORDER: PhaseId[] = ["menstrual", "follicular", "ovulatory", "luteal"];

/** The four phases in order, with the current one marked. The ovulatory step is dropped when fertility is hidden. */
export function phaseSteps(current: PhaseId | null, hideOvulatory: boolean): PhaseStep[] {
  return ORDER.filter((id) => !(hideOvulatory && id === "ovulatory")).map((id) => ({ id, label: PHASE_LABEL[id], here: id === current }));
}

/** Symptoms the user's own logs show most often in `phase`, busiest first. Empty when nothing clusters there. */
export function symptomsInPhase(symptoms: SymptomByPhase[], phase: PhaseId, limit = 3): string[] {
  return symptoms
    .filter((s) => s.most_common_phase === phase)
    .sort((a, b) => b.total_days - a.total_days)
    .slice(0, limit)
    .map((s) => s.label);
}

/** One sentence for the Insights tab, or null while the user's current phase is unknown. */
export function phaseSymptomHint(symptoms: SymptomByPhase[], phase: PhaseId | null): string | null {
  if (!phase) return null;
  const name = PHASE_LABEL[phase].toLowerCase();
  const labels = symptomsInPhase(symptoms, phase);
  if (!labels.length) {
    return `You are in the ${name} phase. Nothing in your logs points to this phase yet, which may only mean it has not been logged.`;
  }
  const list = labels.length === 1 ? labels[0] : `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
  return `You are in the ${name} phase. In your logs, ${list.toLowerCase()} ${labels.length === 1 ? "shows" : "show"} up most often in this phase.`;
}
