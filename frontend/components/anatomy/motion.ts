// The "bump and pump" of a selected organ, as pure maths (motion.test.ts). The renderer only calls these once per frame.

export interface SpringState {
  x: number;
  v: number;
}

/** How big a selected organ gets. */
export const SELECTED_SCALE = 1.3;
/** A slightly under-damped spring: it overshoots the target by about 13 % of the distance, which is the little "bump". */
const STIFFNESS = 190;
const DAMPING = 15;
/** Never integrate a long frame in one go (a background tab resuming must not throw the organ across the screen). */
const MAX_STEP = 1 / 30;

export function stepSpring(state: SpringState, target: number, dt: number): SpringState {
  let { x, v } = state;
  let left = Math.min(Math.max(dt, 0), 0.25);
  while (left > 0) {
    const h = Math.min(left, MAX_STEP);
    v += (STIFFNESS * (target - x) - DAMPING * v) * h;   // semi-implicit Euler: stable at these step sizes
    x += v * h;
    left -= h;
  }
  return { x, v };
}

export function isSettled(state: SpringState, target: number): boolean {
  return Math.abs(state.x - target) < 0.002 && Math.abs(state.v) < 0.01;
}

const bump = (phase: number, centre: number, width: number) => Math.exp(-(((phase - centre) / width) ** 2));

/**
 * How much a selected organ swells and relaxes, as a fraction of its size (0 to about 0.09). It is a gentle hint of life,
 * never a medical reading: the heart does a two-beat "lub-dub" about 70 times a minute, the lungs breathe slowly, the rest
 * breathe softly.
 */
export function pulse(organId: string, seconds: number): number {
  if (!Number.isFinite(seconds)) return 0;
  if (organId === "heart") {
    const phase = (((seconds / 0.85) % 1) + 1) % 1;
    return 0.09 * Math.min(1, bump(phase, 0.08, 0.07) + 0.65 * bump(phase, 0.3, 0.07));
  }
  if (organId === "lungs") return 0.08 * (0.5 - 0.5 * Math.cos(2 * Math.PI * 0.25 * seconds));
  return 0.045 * (0.5 - 0.5 * Math.cos(2 * Math.PI * 0.8 * seconds));
}

/** Opacity of an organ's fill: the picked one and everything (when nothing is picked) are full, the rest step back. */
export function organOpacity(isSelected: boolean, anySelected: boolean): number {
  return !anySelected || isSelected ? 1 : 0.5;
}

/** Exponential smoothing factor for easing a value towards a target (frame-rate independent). */
export function easeFactor(dt: number, rate: number): number {
  return 1 - Math.exp(-Math.max(0, dt) * rate);
}
