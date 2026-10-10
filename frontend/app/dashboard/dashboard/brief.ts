// Pure helpers for the Today brief glyphs. No React: unit-tested in brief.test.ts.
import type { PillKind, Trend } from "./today";

/** Words for the trend glyph. Neutral on purpose: higher or lower is not "better" or "worse" here. */
export const TREND_WORDS: Record<Trend, string> = {
  up: "Above your usual",
  down: "Below your usual",
  steady: "Close to your usual",
};

/** Filled dots on the evidence chip: how much of the user's own data backs an insight. A gap has none. */
export function confidenceDots(kind: PillKind): 0 | 1 | 2 | 3 {
  return kind === "high" ? 3 : kind === "medium" ? 2 : kind === "low" ? 1 : 0;
}

export interface SparkPoint {
  x: number;
  y: number;
}

/**
 * Last-7-days shape as points, oldest first. `bars` is 0..1 with 0 meaning nothing logged: those days are `null`
 * so the line breaks there instead of dipping to zero (a missing day is a gap, not a low value).
 */
export function sparkPoints(bars: number[], width = 64, height = 24, pad = 3): Array<SparkPoint | null> {
  const step = bars.length > 1 ? (width - pad * 2) / (bars.length - 1) : 0;
  const round = (n: number) => Math.round(n * 10) / 10;
  return bars.map((v, i) =>
    v > 0 && Number.isFinite(v)
      ? { x: round(pad + i * step), y: round(height - pad - Math.min(v, 1) * (height - pad * 2)) }
      : null,
  );
}

/** SVG path for the points, one stroke per run of consecutive logged days. A lone day yields no stroke (draw a dot). */
export function sparkPath(points: Array<SparkPoint | null>): string {
  let d = "";
  let previous: SparkPoint | null = null;
  for (const p of points) {
    if (p) d += `${previous ? "L" : "M"}${p.x} ${p.y}`;
    previous = p;
  }
  return d;
}
