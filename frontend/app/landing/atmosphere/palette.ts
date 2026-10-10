/**
 * Colour script for the landing: "A day in Bubbles' sky" (docs/autonomy/LANDING_PREMIUM_PLAN.md, 2.3).
 * Pure data and pure helpers, no DOM and no dependencies. Gradients are mixed in OKLab, never in
 * sRGB, which is what made the old chapter hand-overs muddy.
 *
 * Contrast is enforced by palette.test.ts: every chapter's sky, sampled through the copy zone,
 * must hold WCAG 4.5 for body text and 3 for large text against the chapter's text colour
 * (after its scrim, where it has one).
 */
import type { Tone } from "../story/store";

export type Hex = `#${string}`;

export type SkyStops = { top: Hex; mid: Hex; horizon: Hex };
/** Grade values: warmth -1..1; saturation and contrast in percent points; lift and vignette 0..1. */
export type Grade = { warmth: number; saturation: number; contrast: number; lift: number; vignette: number };
/** A soft radial wash behind copy: composited over the sky before text contrast is measured. */
export type Scrim = { color: Hex; alpha: number };
export type Lights = { key: Hex; rim: Hex; sun: Hex };

export type ChapterPalette = {
  key: string;
  tone: Tone;
  sky: SkyStops;
  lights: Lights;
  /** primary accent: the colour the chapter's signature object glows with */
  accent: Hex;
  /** secondary accent (nerves, threads, horn): used by the world, not by the sky */
  accent2: Hex;
  text: Hex;
  scrim: Scrim | null;
  grade: Grade;
  /** 0..1 */
  bloom: number;
};

export const INK: Hex = "#2B1A3F";
export const BLUSH: Hex = "#FFF6FA";

/** Where the middle stop sits in the sky gradient (0 = top, 1 = horizon). */
export const SKY_MID_STOP = 0.5;
/** The band of the viewport where copy lives, as a fraction of the height. */
export const COPY_ZONE = { from: 0.12, to: 0.78 } as const;

const g = (warmth: number, saturation: number, contrast: number, lift: number, vignette: number): Grade => ({
  warmth,
  saturation,
  contrast,
  lift,
  vignette,
});

/**
 * Section 2.3, in chapter order (same order and keys as CHAPTERS in story/store.ts).
 *
 * Adjustments made to the plan's starting values, all found by palette.test.ts (see the test for the numbers):
 *  - cycle: the sky colours are exactly as planned, but with the phase tint (45 percent of the phase
 *    colour into mid and horizon) blush text falls to about 3.3:1 at ovulation (apricot) and below
 *    4.5 at most phases except the first. A dark plum scrim (alpha 0.35, inside the plan's 25 to 40
 *    percent range) behind the copy lifts the worst case to about 6:1 at every phase. This is the
 *    plan's own remedy; no sky colour was changed. Every other chapter passes as planned.
 */
export const COLOR_SCRIPT = [
  {
    key: "enter",
    tone: "light",
    sky: { top: "#E6D3FF", mid: "#FFC9E3", horizon: "#FFD9B5" },
    lights: { key: "#FFF2DC", rim: "#FFB6D5", sun: "#FFF0D2" },
    accent: "#FFB6D5",
    accent2: "#FFF0D2",
    text: INK,
    scrim: null,
    grade: g(0.5, 0, 0, 0.04, 0),
    bloom: 0.35,
  },
  {
    key: "body",
    tone: "dark",
    sky: { top: "#13294B", mid: "#2A3E86", horizon: "#6E5BC9" },
    lights: { key: "#B8D8FF", rim: "#6E5BC9", sun: "#66E0E6" },
    accent: "#66E0E6", // aqua core glow
    accent2: "#FF8CC2", // nerves
    text: BLUSH,
    scrim: null,
    grade: g(-0.5, 8, 0, 0, 0.06),
    bloom: 0.5,
  },
  {
    key: "noise",
    tone: "light",
    sky: { top: "#D6E8FF", mid: "#EEF5FF", horizon: "#FFFFFF" },
    lights: { key: "#FFFFFF", rim: "#D6E8FF", sun: "#FFFFFF" },
    accent: "#9CC4FF",
    accent2: "#FFFFFF",
    text: INK,
    scrim: null,
    grade: g(-0.1, -15, 8, 0, 0),
    bloom: 0.15,
  },
  {
    key: "track",
    tone: "light",
    sky: { top: "#FFD9A8", mid: "#FFB7A0", horizon: "#FF9DB8" },
    lights: { key: "#FFE0B0", rim: "#FF9DB8", sun: "#FFE0B0" },
    accent: "#FFE0B0",
    accent2: "#FF9DB8",
    text: INK,
    scrim: null,
    grade: g(0.6, 10, 0, 0.02, 0),
    bloom: 0.45,
  },
  {
    key: "cycle",
    tone: "dark",
    sky: { top: "#2B1038", mid: "#5A2058", horizon: "#B8467A" },
    lights: { key: "#FFC9E3", rim: "#B8467A", sun: "#FFC9E3" },
    accent: "#E8336F",
    accent2: "#FFC37A",
    text: BLUSH,
    scrim: { color: "#1C0A26", alpha: 0.35 },
    grade: g(0.3, 0, 0, 0, 0.08),
    bloom: 0.5,
  },
  {
    key: "connect",
    tone: "dark",
    sky: { top: "#12123A", mid: "#2B2A78", horizon: "#9A5BB5" },
    lights: { key: "#CFC8FF", rim: "#9A5BB5", sun: "#FFE9F6" },
    accent: "#FFE9F6", // stars
    accent2: "#D9B8FF", // thread glow (not specified in the plan)
    text: BLUSH,
    scrim: null,
    grade: g(-0.4, 0, 0, 0, 0.08),
    bloom: 0.6,
  },
  {
    key: "remember",
    tone: "dark",
    sky: { top: "#0A0A22", mid: "#1D1A4D", horizon: "#5B3A78" },
    lights: { key: "#FFF1DE", rim: "#5B3A78", sun: "#FFF1DE" },
    accent: "#FFF1DE", // moon
    accent2: "#FFD98A", // fireflies
    text: BLUSH,
    scrim: null,
    grade: g(0, 0, 0, 0, 0.14),
    bloom: 0.4, // not in the plan; moderate, between connect and cycle
  },
  {
    key: "companion",
    tone: "dark",
    sky: { top: "#170C2B", mid: "#3A1A4A", horizon: "#A04574" },
    lights: { key: "#FFD98A", rim: "#A04574", sun: "#FFD98A" },
    accent: "#FFD98A", // horn gold
    accent2: "#FFF1DE",
    text: BLUSH,
    scrim: null,
    grade: g(0.5, 0, 0, 0, 0.1),
    bloom: 0.9,
  },
  {
    key: "care",
    tone: "light",
    sky: { top: "#F1E6F8", mid: "#FAEFF4", horizon: "#FFF4EA" },
    lights: { key: "#FFF4EA", rim: "#F1E6F8", sun: "#FFF4EA" },
    accent: "#E7C6F2",
    accent2: "#FFF4EA",
    text: INK,
    scrim: null,
    grade: g(0.1, 0, -6, 0.05, 0),
    bloom: 0.2,
  },
  {
    key: "bubbles",
    tone: "light",
    sky: { top: "#F4C9E2", mid: "#FFD0C0", horizon: "#FFE6B5" },
    lights: { key: "#FFF3D6", rim: "#FFB6D5", sun: "#FFF3D6" },
    accent: "#FFB6D5",
    accent2: "#FFF3D6",
    text: INK,
    scrim: null,
    grade: g(0.5, 0, 0, 0.03, 0),
    bloom: 0.4,
  },
] as const satisfies ReadonlyArray<ChapterPalette>;

export type ScriptKey = (typeof COLOR_SCRIPT)[number]["key"];

/** The cycle chapter's sky takes 45 percent of the phase colour into mid and horizon. */
export const PHASE_TINT = 0.45;
export const PHASE_COLORS = {
  period: "#E8336F",
  follicular: "#FF8A7A",
  ovulation: "#FFC37A",
  luteal: "#B49BFF",
} as const satisfies Record<string, Hex>;
export const PHASE_ORDER = ["period", "follicular", "ovulation", "luteal"] as const;

export type TimeOfDay = "dawn" | "day" | "dusk" | "night";
export type TimeVariant = Pick<ChapterPalette, "tone" | "sky" | "lights" | "accent" | "accent2" | "text" | "scrim" | "grade" | "bloom">;

/**
 * Four variants of the opening chapter, picked from the visitor's own clock after load ("her sky
 * follows your clock"). "dawn" is the plan's enter palette. The poster stays dawn.
 */
export const ENTER_VARIANTS: Record<TimeOfDay, TimeVariant> = {
  dawn: COLOR_SCRIPT[0],
  day: {
    tone: "light",
    sky: { top: "#CFE3FF", mid: "#F2E3FF", horizon: "#FFEBD0" },
    lights: { key: "#FFFFFF", rim: "#FFC9E3", sun: "#FFF7E0" },
    accent: "#FFC9E3",
    accent2: "#FFF7E0",
    text: INK,
    scrim: null,
    grade: g(0.1, 0, 0, 0.03, 0),
    bloom: 0.25,
  },
  dusk: {
    tone: "light",
    sky: { top: "#F0C4E8", mid: "#FFB8A8", horizon: "#FFC98F" },
    lights: { key: "#FFD9A8", rim: "#F08AB8", sun: "#FFD08A" },
    accent: "#F08AB8",
    accent2: "#FFD08A",
    text: INK,
    scrim: null,
    grade: g(0.7, 8, 0, 0.02, 0.04),
    bloom: 0.45,
  },
  night: {
    tone: "dark",
    sky: { top: "#1A1442", mid: "#43296E", horizon: "#9B5C8F" },
    lights: { key: "#FFE9F6", rim: "#9B5C8F", sun: "#FFF1DE" },
    accent: "#FFE9F6",
    accent2: "#FFD98A",
    text: BLUSH,
    scrim: null,
    grade: g(-0.2, 0, 0, 0, 0.12),
    bloom: 0.5,
  },
};

/** Local hour (0..23) to a time-of-day variant. */
export function timeOfDay(hour: number): TimeOfDay {
  const h = ((Math.floor(hour) % 24) + 24) % 24;
  if (h >= 5 && h < 9) return "dawn";
  if (h >= 9 && h < 17) return "day";
  if (h >= 17 && h < 21) return "dusk";
  return "night";
}

/* ---------------------------------------------------------------------- OKLab and contrast */

type Rgb = readonly [number, number, number];
type Lab = readonly [number, number, number];

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** "#RGB" or "#RRGGBB" to 0..255 channels. Throws on anything else: palette data must be valid. */
export function hexToRgb(hex: string): Rgb {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) throw new Error(`Invalid hex colour: ${hex}`);
  const h = m[1].length === 3 ? m[1].replace(/./g, (c) => c + c) : m[1];
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rgbToHex(rgb: Rgb): Hex {
  const to = (v: number) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0");
  return `#${to(rgb[0])}${to(rgb[1])}${to(rgb[2])}`.toUpperCase() as Hex;
}

const toLinear = (c: number) => {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
};
const fromLinear = (v: number) => {
  const c = v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
  return clamp01(c) * 255;
};

/** sRGB (0..255) to OKLab (Bjorn Ottosson's matrices). */
function toOklab(rgb: Rgb): Lab {
  const r = toLinear(rgb[0]);
  const gr = toLinear(rgb[1]);
  const b = toLinear(rgb[2]);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * gr + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * gr + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * gr + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** OKLab to sRGB (0..255), clamped to gamut. */
function fromOklab(lab: Lab): Rgb {
  const l = Math.pow(lab[0] + 0.3963377774 * lab[1] + 0.2158037573 * lab[2], 3);
  const m = Math.pow(lab[0] - 0.1055613458 * lab[1] - 0.0638541728 * lab[2], 3);
  const s = Math.pow(lab[0] - 0.0894841775 * lab[1] - 1.291485548 * lab[2], 3);
  return [
    fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}

/** Mix two colours in OKLab. `t` is clamped to 0..1; the result is an uppercase hex. */
export function mixOklab(a: string, b: string, t: number): Hex {
  const k = clamp01(t);
  const la = toOklab(hexToRgb(a));
  const lb = toOklab(hexToRgb(b));
  return rgbToHex(fromOklab([lerp(la[0], lb[0], k), lerp(la[1], lb[1], k), lerp(la[2], lb[2], k)]));
}

/** Plain sRGB alpha blend of `over` onto `base`, like CSS compositing. Used for scrims. */
export function composite(base: string, over: string, alpha: number): Hex {
  const a = clamp01(alpha);
  const x = hexToRgb(base);
  const y = hexToRgb(over);
  return rgbToHex([lerp(x[0], y[0], a), lerp(x[1], y[1], a), lerp(x[2], y[2], a)]);
}

/** WCAG relative luminance, 0..1. */
export function luminance(hex: string): number {
  const [r, gr, b] = hexToRgb(hex);
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(gr) + 0.0722 * toLinear(b);
}

/** WCAG contrast ratio, 1..21, symmetric in its arguments. */
export function contrastRatio(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/* ---------------------------------------------------------------------- sky sampling and blending */

/** Sky colour at height `h` (0 = top, 1 = horizon), mid stop at SKY_MID_STOP, mixed in OKLab. */
export function sampleSky(sky: SkyStops, h: number): Hex {
  const y = clamp01(h);
  return y <= SKY_MID_STOP
    ? mixOklab(sky.top, sky.mid, y / SKY_MID_STOP)
    : mixOklab(sky.mid, sky.horizon, (y - SKY_MID_STOP) / (1 - SKY_MID_STOP));
}

/** Sky colour at `h` with the chapter scrim composited over it: what the text actually sits on. */
export function backdropAt(p: Pick<ChapterPalette, "sky" | "scrim">, h: number): Hex {
  const base = sampleSky(p.sky, h);
  return p.scrim ? composite(base, p.scrim.color, p.scrim.alpha) : base;
}

/** The same gradient as CSS, interpolated in OKLab. */
export const skyCss = (s: SkyStops) =>
  `linear-gradient(in oklab, ${s.top} 0%, ${s.mid} ${SKY_MID_STOP * 100}%, ${s.horizon} 100%)`;

/**
 * Where on the four-phase scale an example day is: 0 period, 1 follicular, 2 ovulation, 3 luteal,
 * fractions in between mix neighbours in OKLab. Out-of-range values clamp.
 */
export function phaseColorAt(phaseMix: number): Hex {
  const x = Math.min(PHASE_ORDER.length - 1, Math.max(0, Number.isFinite(phaseMix) ? phaseMix : 0));
  const i = Math.min(PHASE_ORDER.length - 2, Math.floor(x));
  return mixOklab(PHASE_COLORS[PHASE_ORDER[i]], PHASE_COLORS[PHASE_ORDER[i + 1]], x - i);
}

const CYCLE_INDEX = COLOR_SCRIPT.findIndex((c) => c.key === "cycle");

/** The cycle chapter's palette tinted for a point in the example day (mid and horizon only). */
export function cycleAt(phaseMix: number): ChapterPalette {
  const base: ChapterPalette = COLOR_SCRIPT[CYCLE_INDEX];
  const tint = phaseColorAt(phaseMix);
  return {
    ...base,
    sky: {
      top: base.sky.top,
      mid: mixOklab(base.sky.mid, tint, PHASE_TINT),
      horizon: mixOklab(base.sky.horizon, tint, PHASE_TINT),
    },
    lights: { ...base.lights, key: mixOklab(base.lights.key, tint, PHASE_TINT) },
    accent: tint,
  };
}

export type BlendedSky = {
  top: Hex;
  mid: Hex;
  horizon: Hex;
  key: Hex;
  rim: Hex;
  sun: Hex;
  accent: Hex;
  /** text colour of the lead chapter (the one more than half on stage) */
  text: Hex;
  tone: Tone;
  scrim: Scrim | null;
  grade: Grade;
  bloom: number;
};

function paletteFor(index: number, phaseMix: number | undefined, tod: TimeOfDay | undefined): ChapterPalette {
  const base: ChapterPalette = COLOR_SCRIPT[index];
  if (index === CYCLE_INDEX && phaseMix !== undefined) return cycleAt(phaseMix);
  if (index === 0 && tod) return { ...base, ...ENTER_VARIANTS[tod] };
  return base;
}

const mixGrade = (a: Grade, b: Grade, t: number): Grade => ({
  warmth: lerp(a.warmth, b.warmth, t),
  saturation: lerp(a.saturation, b.saturation, t),
  contrast: lerp(a.contrast, b.contrast, t),
  lift: lerp(a.lift, b.lift, t),
  vignette: lerp(a.vignette, b.vignette, t),
});

/**
 * The palette on screen when chapter `chapterIndex` is leading and `blend` (0..1) of the hand-over
 * to the next chapter has happened. `phaseMix` (0..3, see phaseColorAt) tints the cycle chapter;
 * `tod` swaps in an opening-chapter variant. Indices and blend clamp, so the last chapter holds.
 */
export function skyAt(chapterIndex: number, blend: number, phaseMix?: number, tod?: TimeOfDay): BlendedSky {
  const last = COLOR_SCRIPT.length - 1;
  const i = Math.min(last, Math.max(0, Math.floor(Number.isFinite(chapterIndex) ? chapterIndex : 0)));
  const j = Math.min(last, i + 1);
  const t = clamp01(Number.isFinite(blend) ? blend : 0);
  const a = paletteFor(i, phaseMix, tod);
  const b = paletteFor(j, phaseMix, tod);
  const lead = t < 0.5 ? a : b;
  const scrimAlpha = lerp(a.scrim?.alpha ?? 0, b.scrim?.alpha ?? 0, t);
  const scrimColor = (t < 0.5 ? a.scrim ?? b.scrim : b.scrim ?? a.scrim)?.color;
  return {
    top: mixOklab(a.sky.top, b.sky.top, t),
    mid: mixOklab(a.sky.mid, b.sky.mid, t),
    horizon: mixOklab(a.sky.horizon, b.sky.horizon, t),
    key: mixOklab(a.lights.key, b.lights.key, t),
    rim: mixOklab(a.lights.rim, b.lights.rim, t),
    sun: mixOklab(a.lights.sun, b.lights.sun, t),
    accent: mixOklab(a.accent, b.accent, t),
    text: lead.text,
    tone: lead.tone,
    scrim: scrimColor && scrimAlpha > 0 ? { color: scrimColor, alpha: scrimAlpha } : null,
    grade: mixGrade(a.grade, b.grade, t),
    bloom: lerp(a.bloom, b.bloom, t),
  };
}
