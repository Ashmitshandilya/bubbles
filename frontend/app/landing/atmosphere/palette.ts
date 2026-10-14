/**
 * Colour script for the landing: "Pearl Lab", a sunlit pearl laboratory (bubbles-stitch-kit DESIGN.md).
 * Light only: every chapter is pearl with a slightly different light (lilac morning, porcelain noon, warm
 * gold at the close), so the hand-overs feel like the light moving, not like the page changing colour.
 * Pure data and pure helpers, no DOM and no dependencies. Gradients are mixed in OKLab, never in sRGB.
 *
 * Contrast is enforced by palette.test.ts and contrast.test.ts: every chapter's sky, sampled through the
 * copy zone, must hold WCAG 4.5 for body text and 3 for large text against the text colours.
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

/** Ink-plum: all body text and headlines. Never pure black. */
export const INK: Hex = "#1E1B2E";

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

/** In chapter order (same order and keys as CHAPTERS in story/store.ts). */
export const COLOR_SCRIPT = [
  {
    key: "enter",
    tone: "light",
    sky: { top: "#F4EEFA", mid: "#FBF8F6", horizon: "#FCF2EA" },
    lights: { key: "#FFF6EA", rim: "#E9DDF7", sun: "#FFF4E4" },
    accent: "#C9B6F2",
    accent2: "#E9C98B",
    text: INK,
    scrim: null,
    grade: g(0.25, 0, 0, 0.02, 0),
    bloom: 0.2,
  },
  {
    key: "listen",
    tone: "light",
    sky: { top: "#F1ECFA", mid: "#FAF6F8", horizon: "#F6EFF8" },
    lights: { key: "#FFF8F0", rim: "#D5C4F5", sun: "#FFF6EC" },
    accent: "#C9B6F2",
    accent2: "#F7C8D6",
    text: INK,
    scrim: null,
    grade: g(0.1, 0, 0, 0.02, 0),
    bloom: 0.2,
  },
  {
    key: "confirm",
    tone: "light",
    sky: { top: "#F8F4F1", mid: "#FBF8F6", horizon: "#F6F0F6" },
    lights: { key: "#FFFFFF", rim: "#E7E0EC", sun: "#FFF8F0" },
    accent: "#D5C4F5",
    accent2: "#E9C98B",
    text: INK,
    scrim: null,
    grade: g(0.05, 0, 0, 0.02, 0),
    bloom: 0.12,
  },
  {
    key: "patterns",
    tone: "light",
    sky: { top: "#F3EDF9", mid: "#FAF6F8", horizon: "#FCF1EC" },
    lights: { key: "#FFF4E8", rim: "#D5C4F5", sun: "#FFF2E2" },
    accent: "#B49BFF",
    accent2: "#FFC37A",
    text: INK,
    scrim: null,
    grade: g(0.15, 0, 0, 0.02, 0),
    bloom: 0.15,
  },
  {
    key: "prepare",
    tone: "light",
    sky: { top: "#FAF8F6", mid: "#FBF8F6", horizon: "#F7F2F3" },
    lights: { key: "#FFFFFF", rim: "#E7E0EC", sun: "#FFFAF4" },
    accent: "#D5C4F5",
    accent2: "#E9C98B",
    text: INK,
    scrim: null,
    grade: g(0, 0, 0, 0.02, 0),
    bloom: 0.1,
  },
  {
    key: "close",
    tone: "light",
    sky: { top: "#F5ECF6", mid: "#FBF6F4", horizon: "#FDEFE2" },
    lights: { key: "#FFF2DE", rim: "#F7C8D6", sun: "#FFEFD6" },
    accent: "#F7C8D6",
    accent2: "#E9C98B",
    text: INK,
    scrim: null,
    grade: g(0.35, 0, 0, 0.02, 0),
    bloom: 0.22,
  },
] as const satisfies ReadonlyArray<ChapterPalette>;

export type ScriptKey = (typeof COLOR_SCRIPT)[number]["key"];

export const PHASE_COLORS = {
  period: "#E8336F",
  follicular: "#FF8A7A",
  ovulation: "#FFC37A",
  luteal: "#B49BFF",
} as const satisfies Record<string, Hex>;
export const PHASE_ORDER = ["period", "follicular", "ovulation", "luteal"] as const;

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

/** A hex colour as OKLab [L, a, b]: what the sky shader mixes in. */
export const hexToOklab = (hex: string): Lab => toOklab(hexToRgb(hex));

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

const mixGrade = (a: Grade, b: Grade, t: number): Grade => ({
  warmth: lerp(a.warmth, b.warmth, t),
  saturation: lerp(a.saturation, b.saturation, t),
  contrast: lerp(a.contrast, b.contrast, t),
  lift: lerp(a.lift, b.lift, t),
  vignette: lerp(a.vignette, b.vignette, t),
});

/**
 * The palette on screen when chapter `chapterIndex` is leading and `blend` (0..1) of the hand-over
 * to the next chapter has happened. Indices and blend clamp, so the last chapter holds.
 */
export function skyAt(chapterIndex: number, blend: number): BlendedSky {
  const last = COLOR_SCRIPT.length - 1;
  const i = Math.min(last, Math.max(0, Math.floor(Number.isFinite(chapterIndex) ? chapterIndex : 0)));
  const j = Math.min(last, i + 1);
  const t = clamp01(Number.isFinite(blend) ? blend : 0);
  const a: ChapterPalette = COLOR_SCRIPT[i];
  const b: ChapterPalette = COLOR_SCRIPT[j];
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
