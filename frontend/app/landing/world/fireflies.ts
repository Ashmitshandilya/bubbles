/**
 * The fireflies of the night chapters (world/Motes.tsx), as pure functions so the numbers can be tested.
 * `night` is 0 (the usual drifting cells) to 1 (full night: a few big, warm, twinkling fireflies).
 */

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/** The fraction of the cells kept at full night: about one in seven. */
export const FIREFLY_SHARE = 0.14;

/** A cell with a `keep` value (0..1, fixed per cell) above this threshold is faded out. 1 by day, FIREFLY_SHARE at full night. */
export const fireflyThreshold = (night: number) => 1 - (1 - FIREFLY_SHARE) * clamp01(night);

/**
 * How visible a cell is: 1 by day, and at night 1 for the cells that stay and 0 for the rest, with a soft edge
 * so cells fade rather than blink out as the night comes in.
 */
export function fireflyFade(keep: number, threshold: number, night: number): number {
  const n = clamp01(night);
  const soft = clamp01((threshold - keep) / 0.12);
  return 1 + (soft - 1) * n;
}

/**
 * A firefly's twinkle: 1 by day; at night a slow beat between 0.3 and 1 (each cell has its own `beat` in
 * radians per second and `phase`), blended in with `night`. `time` is the idle clock, so pausing motion freezes it.
 */
export function fireflyGlow(night: number, time: number, beat: number, phase: number): number {
  const n = clamp01(night);
  const twinkle = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(time * beat * 2.2 + phase));
  return 1 + (twinkle - 1) * n;
}
