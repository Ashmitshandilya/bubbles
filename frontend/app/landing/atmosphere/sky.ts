/**
 * Pure helpers for the landing sky (plan 2.6): everything the shader, the CSS fallback and the
 * calm (static) page need that is not WebGL. No DOM, so it is unit-tested in node.
 *
 * The same colours drive three skies that must agree: the OKLab shader (full and lite tiers), the
 * CSS gradient under it (also the whole sky in the static tier) and the per-chapter gradients of
 * the calm page (reduced motion).
 */
import type { Tier } from "../perf/tier";
import type { Tone } from "../story/store";
import {
  COPY_ZONE,
  SKY_MID_STOP,
  hexToRgb,
  sampleSky,
  skyCss,
  type ChapterPalette,
  type Hex,
  type Scrim,
  type SkyStops,
} from "./palette";

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/* ---------------------------------------------------------------------- CSS */

/** `rgb(r g b / a)` for a scrim, `transparent` for none. */
export function scrimCss(s: Scrim | null): string {
  if (!s || s.alpha <= 0) return "transparent";
  const [r, g, b] = hexToRgb(s.color);
  return `rgb(${r} ${g} ${b} / ${Math.round(clamp01(s.alpha) * 1000) / 1000})`;
}

/** A sky as a CSS gradient: OKLab (modern browsers) or plain sRGB (the fallback behind an `@supports`). */
export const skyGradient = (s: SkyStops, oklab: boolean) =>
  oklab ? skyCss(s) : `linear-gradient(${s.top} 0%, ${s.mid} ${SKY_MID_STOP * 100}%, ${s.horizon} 100%)`;

/** The sky restricted to the copy zone: three samples, so a page that stretches it over a whole chapter keeps every pixel tested. */
export function calmStops(sky: SkyStops): SkyStops {
  const mid = (COPY_ZONE.from + COPY_ZONE.to) / 2;
  return { top: sampleSky(sky, COPY_ZONE.from), mid: sampleSky(sky, mid), horizon: sampleSky(sky, COPY_ZONE.to) };
}

/** Background of one chapter on the calm page: its scrim (if any) over its sky. */
export function calmBackground(p: Pick<ChapterPalette, "sky" | "scrim">, oklab: boolean): string {
  const gradient = skyGradient(calmStops(p.sky), oklab);
  if (!p.scrim) return gradient;
  const wash = scrimCss(p.scrim);
  return `linear-gradient(${wash}, ${wash}), ${gradient}`;
}

/** CSS custom properties for a sky at rest: what the server renders before any script runs. */
export function skyVars(p: Pick<ChapterPalette, "sky" | "scrim" | "grade">): Record<string, string> {
  return {
    "--sky-top": p.sky.top,
    "--sky-mid": p.sky.mid,
    "--sky-hor": p.sky.horizon,
    "--bg": p.sky.mid,
    "--vig": String(p.grade.vignette),
    "--scrim": scrimCss(p.scrim),
  };
}

/* ---------------------------------------------------------------------- shader parameters */

export type SkyParams = {
  sunX: number;
  sunY: number;
  sunSize: number;
  discAlpha: number;
  rays: number;
  haze: number;
  /** most the glow, rays and haze may lighten the sky toward the sun colour (see OVERLAY_CAP) */
  cap: number;
};

/**
 * The most the shader's glow, rays and haze may blend the sky toward the sun colour, per tone.
 * sky.test.ts proves copy keeps WCAG contrast even at this worst case, everywhere in the copy zone
 * (the small sun / moon disc is outside the budget: it sits away from the copy).
 */
export const OVERLAY_CAP: Record<Tone, number> = { light: 0.3, dark: 0.1 };

/**
 * Warm daylight from the top left on light skies (Pearl Lab's key light): no visible disc, only a soft wash and faint
 * rays. A small moon top-right on dark ones (the landing has none now; kept so the shader stays general).
 */
const LIGHT_SUN = { x: 0.16, y: 0.86, size: 0.055, disc: 0, rays: 0.3, haze: 0.55 } as const;
const DARK_SUN = { x: 0.82, y: 0.82, size: 0.026, disc: 0.55, rays: 0.3, haze: 0.45 } as const;

/** Shader parameters for a sky that is `dark` (0 light .. 1 dark) and a tier. Writes into `out` (no allocation per frame). */
export function skyParams(dark: number, tier: Tier, out: SkyParams): SkyParams {
  const k = clamp01(dark);
  out.sunX = lerp(LIGHT_SUN.x, DARK_SUN.x, k);
  out.sunY = lerp(LIGHT_SUN.y, DARK_SUN.y, k);
  out.sunSize = lerp(LIGHT_SUN.size, DARK_SUN.size, k);
  out.discAlpha = lerp(LIGHT_SUN.disc, DARK_SUN.disc, k);
  out.rays = lerp(LIGHT_SUN.rays, DARK_SUN.rays, k);
  out.haze = lerp(LIGHT_SUN.haze, DARK_SUN.haze, k) * (tier === "full" ? 1 : 0.7);
  out.cap = lerp(OVERLAY_CAP.light, OVERLAY_CAP.dark, k);
  return out;
}

export const newSkyParams = (): SkyParams => ({ sunX: 0, sunY: 0, sunSize: 0, discAlpha: 0, rays: 0, haze: 0, cap: 0 });

/** Render scale (pixels per CSS pixel, before the device ratio) per tier: the sky is smooth, so it is cheap to under-sample. */
export const SKY_SCALE: Record<Exclude<Tier, "static">, number> = { lite: 0.5, full: 0.75 };
export const SKY_DPR_CAP: Record<Exclude<Tier, "static">, number> = { lite: 1, full: 1.5 };

/** Canvas size in device pixels for a CSS size, tier and device pixel ratio. At least 1 x 1. */
export function skyCanvasSize(cssW: number, cssH: number, tier: Exclude<Tier, "static">, dpr: number) {
  const k = Math.min(Math.max(1, dpr || 1), SKY_DPR_CAP[tier]) * SKY_SCALE[tier];
  return { w: Math.max(1, Math.round(cssW * k)), h: Math.max(1, Math.round(cssH * k)) };
}

/** `#RRGGBB` to sRGB 0..1 (shader uniforms). */
export function hexToUnit(hex: Hex | string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex);
  return [r / 255, g / 255, b / 255];
}
