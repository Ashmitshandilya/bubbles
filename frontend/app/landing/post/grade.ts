/**
 * The post stack's numbers (plan step 9), as pure functions. The stack itself lives in PostStack.ts.
 *
 * Full tier only: a gentle bloom and a colour grade, both read from the colour script (`story.sky.bloom` and
 * `story.sky.grade`, which the scroll director blends through every hand-over). The DOM is never touched, so
 * copy never blooms. In lite and static none of this runs.
 */
import type { Grade } from "../atmosphere/palette";
import type { Tier } from "../perf/tier";

/** Tuning knobs, in one place. */
export const POST = {
  /** the plan's "about 0.35" is the opening chapter's bloom value; this scales every chapter's value (0.9 at the companion is the one big bloom) */
  bloomGain: 0.8,
  bloomRadius: 0.7,
  bloomThreshold: 0.85,
  /** most the internal targets are rendered at, in device pixels per CSS pixel (half-float targets are heavy) */
  dprCap: 1.5,
  /** pixel counts above which the multisampling drops from 4 to 2 samples, and from 2 to 0 */
  samples4Max: 2_500_000,
  samples2Max: 5_500_000,
  /** how fast the stack fades in after the tier is promoted and out after a demotion, per second */
  fadeRate: 4,
  /** an amount under this counts as off */
  off: 0.015,
} as const;

/** Post runs only in the full tier. */
export const postWanted = (tier: Tier) => tier === "full";

/**
 * A page can switch the stack off for comparison: `?post=0` in the address. (Reads the string it is given,
 * so it is testable without a window.)
 */
export const postAllowed = (search: string) => new URLSearchParams(search).get("post") !== "0";

export type GradeUniforms = {
  /** per-channel multiplier (warmth), linear light */
  warm: [number, number, number];
  /** 1 = unchanged */
  sat: number;
  /** contrast exponent around mid grey: 1 = unchanged */
  con: number;
  /** added to every channel, linear light */
  lift: number;
  /** the page vignette's strength (the same number as `--vig`) */
  vig: number;
};

export const newGradeUniforms = (): GradeUniforms => ({ warm: [1, 1, 1], sat: 1, con: 1, lift: 0, vig: 0 });

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/**
 * Colour script grade to shader values. Warmth is -1..1 (cool to warm), saturation and contrast are percent
 * points, lift and vignette 0..1. Every effect is scaled by `amount` (0 off, 1 full), so the stack fades in
 * and out instead of jumping when the tier changes. Writes into `out` (no allocation per frame).
 */
export function gradeUniforms(g: Grade, amount: number, out: GradeUniforms): GradeUniforms {
  const a = clamp01(amount);
  out.warm[0] = 1 + 0.07 * g.warmth * a;
  out.warm[1] = 1 + 0.008 * g.warmth * a;
  out.warm[2] = 1 - 0.08 * g.warmth * a;
  out.sat = 1 + (g.saturation / 100) * a;
  out.con = 1 + (g.contrast / 100) * a;
  out.lift = g.lift * 0.05 * a;
  out.vig = g.vignette * a;
  return out;
}

/** Bloom strength for a colour script value (0..1) at a fade `amount`. */
export const bloomStrength = (bloom: number, amount: number) => POST.bloomGain * clamp01(bloom) * clamp01(amount);

export type PostTarget = { width: number; height: number; samples: number };

/**
 * Size and multisampling of the post stack's targets for a canvas of `cssW x cssH` CSS pixels at device pixel
 * ratio `dpr`. Targets never exceed `POST.dprCap` device pixels per CSS pixel (the final pass scales up), and
 * the sample count steps down as the pixel count grows, so memory stays reasonable on big screens.
 */
export function postTargetSize(cssW: number, cssH: number, dpr: number): PostTarget {
  const k = Math.min(Math.max(dpr || 1, 1), POST.dprCap);
  const width = Math.max(1, Math.round(cssW * k));
  const height = Math.max(1, Math.round(cssH * k));
  const px = width * height;
  return { width, height, samples: px <= POST.samples4Max ? 4 : px <= POST.samples2Max ? 2 : 0 };
}

/** One step of the fade: `amount` moves toward 1 (stack wanted) or 0 (not wanted) at `POST.fadeRate` per second. */
export function fadeAmount(amount: number, wanted: boolean, dt: number): number {
  const next = amount + ((wanted ? 1 : 0) - amount) * (1 - Math.exp(-POST.fadeRate * Math.max(0, dt)));
  return wanted ? next : next < POST.off ? 0 : next;
}
