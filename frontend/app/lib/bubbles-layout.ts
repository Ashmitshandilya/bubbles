// Pure layout for LivingBubbles (renovation plan 10.2): size is amount, drift is trend, colour is the domain.
// A signal with no entries is an empty outlined bubble of fixed size, never a small filled one: missing is a gap, not a low value.

export type Domain = "sleep" | "mood" | "body" | "food" | "move" | "cycle" | "us";

export interface BubbleSignal {
  id: string;
  label: string;
  domain: Domain;
  /** 0..1 share of the person's own usual, or null when nothing was logged. */
  amount: number | null;
  /** -1 (down) .. 1 (up) against the person's usual, or null when unknown. */
  trend: number | null;
  /** The value in words, shown inside the bubble ("6h 24m"); omitted when nothing is logged. */
  valueText?: string;
}

export interface PlacedBubble {
  id: string;
  label: string;
  color: string;
  cx: number;
  cy: number;
  r: number;
  empty: boolean;
  valueText?: string;
  /** Vertical rest offset in px: up for a rising trend, down for a falling one, 0 when steady or unknown. */
  drift: number;
}

export const MIN_R = 20;
export const MAX_R = 40;
export const EMPTY_R = 24;
export const MAX_DRIFT = 6;

const COLORS: Record<Domain, string> = {
  sleep: "var(--mark-sleep)", mood: "var(--mark-mood)", body: "var(--mark-body)", food: "var(--mark-food)",
  move: "var(--mark-move)", cycle: "var(--phase-luteal)", us: "var(--mark-us)",
};

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

export function layoutBubbles(signals: BubbleSignal[], width: number, height = MAX_R * 2 + MAX_DRIFT * 2 + 8): PlacedBubble[] {
  const count = signals.length;
  if (!count || !(width > 0)) return [];
  const slot = width / count;
  return signals.map((s, i) => {
    const empty = s.amount === null || !Number.isFinite(s.amount);
    const r = empty ? EMPTY_R : Math.round(MIN_R + clamp(s.amount as number, 0, 1) * (MAX_R - MIN_R));
    const trend = s.trend !== null && Number.isFinite(s.trend) && !empty ? clamp(s.trend, -1, 1) : 0;
    return {
      id: s.id, label: s.label, color: COLORS[s.domain], cx: Math.round(slot * (i + 0.5)), cy: Math.round(height / 2),
      r, empty, valueText: empty ? undefined : s.valueText, drift: Math.round(-trend * MAX_DRIFT) || 0,   // `|| 0` turns -0 into 0
    };
  });
}

/** Screen-reader sentence for one bubble, e.g. "Sleep: lower than your usual." Never a bare number. */
export function describeBubble(s: BubbleSignal, detail?: string): string {
  if (s.amount === null) return `${s.label}: no entries yet.`;
  const against = s.trend === null ? "" : s.trend > 0.15 ? "higher than your usual" : s.trend < -0.15 ? "lower than your usual" : "close to your usual";
  return [`${s.label}:`, detail, against].filter(Boolean).join(" ").replace(/:\s*$/, "") + ".";
}
