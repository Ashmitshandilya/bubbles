// Pure view-model for the Patterns screen (POST /patterns/analyze, POST /intelligence/longitudinal).
// Kept free of React and of HubKit so the real response shapes can be fixtured in api-contract.test.ts.
import { formatWhen, parseWhen } from "../lib/dates";

/* ── Backend shapes: POST /patterns/analyze, POST /intelligence/longitudinal ── */

export interface Recurrence {
  event_type: string;
  subject: string;
  occurrence_count: number;
  average_confidence: number;
  first_seen: string;
  last_seen: string;
  span_days: number;
  source_event_ids?: string[];
}

export interface CoOccurrence {
  a: { event_type: string; subject: string };
  b: { event_type: string; subject: string };
  pair_count: number;
  window_days: number;
  interpretation: string;
  source_event_ids?: string[];
}

export interface PatternsResponse {
  analysis?: { event_count?: number; patterns?: Recurrence[]; correlations?: CoOccurrence[] };
}

export type Coverage = "missing" | "sparse" | "observed";

export interface LongitudinalResponse {
  analysis?: {
    domains?: Record<string, { observed_days?: number; coverage_status?: Coverage }>;
    timeline?: Array<{ date: string; domain: string }>;
  };
}

/* ── View model ───────────────────────────────────────── */

export type Confidence = "High" | "Medium" | "Low";

export interface PatternCard {
  key: string;
  headline: string;
  confidence: Confidence;
  /** `subject` is the raw backend word ("sleep"); `toneKey` is what the view hands to toneFor(). */
  signals: Array<{ subject: string; toneKey: string }>;
  window: string;
  evidence: string[];
  note: string;
}

export const RANK: Record<Confidence, number> = { High: 0, Medium: 1, Low: 2 };

/** Cards shown before "Show all": a regular logger gets a dozen-plus pairs ("X and Y show up together"). Strongest first. */
export const CARD_LIMIT = 8;

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// ponytail: confidence labels are a front-end heuristic on counts; move to the backend when it scores patterns.
export function recurrenceConfidence(p: Recurrence): Confidence {
  if (p.average_confidence < 0.5) return "Low";
  if (p.occurrence_count >= 8 && p.span_days >= 14) return "High";
  return p.occurrence_count >= 5 ? "Medium" : "Low";
}

export function toCards(analysis: NonNullable<PatternsResponse["analysis"]>, days: number): PatternCard[] {
  const recurrences = (analysis.patterns ?? []).map((p): PatternCard => {
    const linked = p.source_event_ids?.length ?? 0;
    return {
      key: `r-${p.event_type}-${p.subject}`,
      headline: `${cap(p.subject)} came up ${p.occurrence_count} times`,
      confidence: recurrenceConfidence(p),
      signals: [{ subject: p.subject, toneKey: `${p.event_type} ${p.subject}` }],
      window: `${formatWhen(p.first_seen)} – ${formatWhen(p.last_seen)}`,
      evidence: [
        `Logged ${p.occurrence_count} times over about ${Math.max(1, Math.round(p.span_days))} days.`,
        ...(linked ? [`Linked to ${linked} of your entries.`] : []),
        `Bubbles read those entries with ${Math.round(p.average_confidence * 100)}% confidence on average.`,
      ],
      note: "Something repeating isn't a sign that anything is wrong. It's just worth noticing, and worth mentioning to a clinician if it bothers you.",
    };
  });

  const together = (analysis.correlations ?? []).map((c): PatternCard => ({
    key: `c-${c.a.subject}-${c.b.subject}`,
    headline: `${cap(c.a.subject)} and ${c.b.subject} often show up together`,
    confidence: c.pair_count >= 6 ? "High" : c.pair_count >= 4 ? "Medium" : "Low",
    signals: [
      { subject: c.a.subject, toneKey: `${c.a.event_type} ${c.a.subject}` },
      { subject: c.b.subject, toneKey: `${c.b.event_type} ${c.b.subject}` },
    ],
    window: `Within ${c.window_days} days of each other`,
    evidence: [
      `Seen close together ${c.pair_count} times in the last ${days} days.`,
      ...(c.source_event_ids?.length ? [`Based on ${c.source_event_ids.length} linked entries.`] : []),
    ],
    note: c.interpretation,
  }));

  return [...recurrences, ...together].sort((x, y) => RANK[x.confidence] - RANK[y.confidence]);
}

/**
 * Logs per week, oldest first, last entry = the week ending today. Timeline dates are calendar days
 * ("2026-10-07"); a full timestamp is read in local time rather than being silently skipped.
 */
export function weeklyCounts(timeline: ReadonlyArray<{ date?: unknown }> | undefined, days: number, now = new Date()): number[] {
  const weeks = Math.ceil(days / 7);
  const counts = new Array<number>(weeks).fill(0);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  for (const item of timeline ?? []) {
    if (typeof item?.date !== "string") continue;
    const when = parseWhen(item.date);
    if (Number.isNaN(when.getTime())) continue;
    const ago = Math.round((today - new Date(when.getFullYear(), when.getMonth(), when.getDate()).getTime()) / 86_400_000);
    const index = weeks - 1 - Math.floor(ago / 7);
    if (index >= 0 && index < weeks) counts[index] += 1;
  }
  return counts;
}
