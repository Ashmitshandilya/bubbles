import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { CHAPTERS } from "../story/store";
import { COLOR_SCRIPT, composite, contrastRatio, sampleSky, type ChapterPalette, type Hex } from "./palette";
import { OVERLAY_CAP } from "./sky";

/**
 * The text colours the stylesheet really uses (--fg, --fg-soft, --accent, read from landing.css so the two
 * cannot drift apart) against the sky behind each piece of copy, at the sky's worst case: the base gradient and
 * the shader's glow, rays and haze at their cap, with the chapter scrim where there is one.
 *
 * palette.test.ts proves the planned ink text; this proves the headings, accents and secondary text
 * that the page actually paints. Large text (headings, 24px or 19px bold and up) needs 3, the rest 4.5.
 * Each role lists the band of the viewport height its copy occupies, so a headline at the top is not judged
 * against the horizon glow it never touches.
 */

const css = readFileSync(new URL("../landing.css", import.meta.url), "utf8");

type Tone = "light" | "dark";
type Token = { hex: Hex; alpha: number };

function tokens(tone: Tone): Record<"fg" | "fgSoft" | "accent", Token> {
  const block = new RegExp(`\\.cw\\s+\\[data-tone="${tone}"\\]\\s*\\{([^}]*)\\}`).exec(css)?.[1];
  if (!block) throw new Error(`no ${tone} tone block in landing.css`);
  const read = (name: string): Token => {
    const raw = new RegExp(`--${name}:\\s*([^;]+);`).exec(block)?.[1]?.replace(/\/\*.*?\*\//g, "").trim();
    if (!raw) throw new Error(`--${name} missing in the ${tone} block`);
    const hex = /^#([0-9a-f]{6})$/i.exec(raw);
    if (hex) return { hex: `#${hex[1]}` as Hex, alpha: 1 };
    const rgb = /^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)(?:\s*\/\s*([\d.]+))?\s*\)$/.exec(raw);
    if (!rgb) throw new Error(`cannot read --${name}: ${raw}`);
    const to = (v: string) => Number(v).toString(16).padStart(2, "0");
    return { hex: `#${to(rgb[1])}${to(rgb[2])}${to(rgb[3])}` as Hex, alpha: rgb[4] === undefined ? 1 : Number(rgb[4]) };
  };
  return { fg: read("fg"), fgSoft: read("fg-soft"), accent: read("accent") };
}

const TOKENS = { light: tokens("light") } as Record<Tone, Record<"fg" | "fgSoft" | "accent", Token>>;

type Painted = Pick<ChapterPalette, "sky" | "scrim" | "lights" | "tone">;
const heights = (from: number, to: number) => Array.from({ length: 5 }, (_, i) => from + ((to - from) * i) / 4);

/** Lowest contrast of `text` over the sky between `band`, with and without the shader overlay at its cap. */
function worst(p: Painted, text: Token | Hex, band: readonly [number, number]) {
  let min = Infinity;
  for (const h of heights(band[0], band[1])) {
    let bg = sampleSky(p.sky, h);
    if (p.scrim) bg = composite(bg, p.scrim.color, p.scrim.alpha);
    for (const sky of [bg, composite(bg, p.lights.sun, OVERLAY_CAP[p.tone])]) {
      const fg = typeof text === "string" ? text : composite(sky, text.hex, text.alpha);
      min = Math.min(min, contrastRatio(sky, fg));
    }
  }
  return min;
}

/** `strict`: a headline accent held to 4.5 on light skies, although large text only needs 3 (the hero line must pop, not just pass). */
type Role = { what: string; use: "fg" | "fgSoft" | "accent"; large: boolean; band: readonly [number, number]; strict?: boolean };

/** What each chapter paints, and where. Bands are fractions of the viewport height (desktop and phone). */
const ROLES: Record<string, Role[]> = {
  enter: [
    { what: "headline", use: "fg", large: true, band: [0.2, 0.75] },
    { what: "accent line", use: "accent", large: true, strict: true, band: [0.2, 0.75] },
    { what: "lede", use: "fgSoft", large: false, band: [0.45, 0.9] },
  ],
  listen: [
    { what: "headline", use: "fg", large: true, band: [0.1, 0.5] },
    { what: "lede and chip labels", use: "fgSoft", large: false, band: [0.2, 0.95] },
    { what: "chip kinds (accent, small)", use: "accent", large: false, band: [0.15, 0.9] },
  ],
  confirm: [
    { what: "headline", use: "fg", large: true, band: [0.1, 0.55] },
    { what: "lede and example caption", use: "fgSoft", large: false, band: [0.2, 0.75] },
  ],
  patterns: [
    { what: "headline", use: "fg", large: true, band: [0.1, 0.5] },
    { what: "lede, pattern note and legend", use: "fgSoft", large: false, band: [0.25, 0.95] },
  ],
  prepare: [
    { what: "headline", use: "fg", large: true, band: [0.1, 0.5] },
    { what: "lede", use: "fgSoft", large: false, band: [0.3, 0.75] },
  ],
  close: [
    { what: "headline", use: "fg", large: true, band: [0.1, 0.5] },
    { what: "promise numbers (accent, small)", use: "accent", large: false, band: [0.2, 0.9] },
    { what: "promise copy", use: "fgSoft", large: false, band: [0.2, 0.9] },
  ],
};

const need = (r: Role, tone: Tone) => (r.strict && tone === "light" ? 4.5 : r.large ? 3 : 4.5);

function failures(label: string, p: Painted, roles: Role[]) {
  const out: string[] = [];
  for (const r of roles) {
    const got = worst(p, TOKENS[p.tone][r.use], r.band);
    if (got < need(r, p.tone)) out.push(`${label} ${r.what}: ${got.toFixed(2)} (needs ${need(r, p.tone)})`);
  }
  return out;
}

describe("the stylesheet's text tokens", () => {
  it("are read from landing.css: plum ink, muted plum, iris violet", () => {
    expect(TOKENS.light.fg.hex.toLowerCase()).toBe("#1e1b2e");
    expect(TOKENS.light.fgSoft.hex.toLowerCase()).toBe("#5e5873");
    expect(TOKENS.light.accent.hex.toLowerCase()).toBe("#6b46d6");
  });
});

describe("heading, accent and secondary text hold their contrast at the sky's worst case", () => {
  for (const c of COLOR_SCRIPT) {
    it(`${c.key}`, () => {
      expect(failures(c.key, c, ROLES[c.key])).toEqual([]);
    });
  }

  it("every chapter has roles listed here", () => {
    expect(Object.keys(ROLES).sort()).toEqual(CHAPTERS.map((c) => c.key).sort());
  });
});

describe("text on the page's own surfaces", () => {
  it("muted text and the accent hold 4.5 on porcelain cards and on the lilac message bubble", () => {
    for (const bg of ["#FFFFFF", "#D5C4F5", "#FBF8F6"]) {
      expect(contrastRatio(bg, TOKENS.light.fg.hex), bg).toBeGreaterThanOrEqual(4.5);
      if (bg !== "#D5C4F5") {
        expect(contrastRatio(bg, TOKENS.light.fgSoft.hex), bg).toBeGreaterThanOrEqual(4.5);
        expect(contrastRatio(bg, TOKENS.light.accent.hex), bg).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("white button text holds 4.5 on the violet button, at rest and pressed", () => {
    expect(contrastRatio("#6B46D6", "#FFFFFF")).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio("#5835BF", "#FFFFFF")).toBeGreaterThanOrEqual(4.5);
  });
});
