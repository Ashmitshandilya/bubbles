import { describe, expect, it } from "vitest";
import { CHAPTERS } from "../story/store";
import {
  COLOR_SCRIPT,
  COPY_ZONE,
  INK,
  backdropAt,
  contrastRatio,
  mixOklab,
  sampleSky,
  skyAt,
  skyCss,
  type ChapterPalette,
} from "./palette";

const BODY = 4.5;
const LARGE = 3;
const HEIGHTS = Array.from({ length: 5 }, (_, i) => COPY_ZONE.from + ((COPY_ZONE.to - COPY_ZONE.from) * i) / 4);

type Readable = Pick<ChapterPalette, "sky" | "scrim" | "text">;

function worst(p: Readable) {
  let min = Infinity;
  let at = 0;
  for (const h of HEIGHTS) {
    const r = contrastRatio(backdropAt(p, h), p.text);
    if (r < min) {
      min = r;
      at = h;
    }
  }
  return { min, at };
}

function expectReadable(name: string, p: Readable) {
  const { min, at } = worst(p);
  const where = `${name}: ${min.toFixed(2)} at ${(at * 100).toFixed(0)}% of the height`;
  expect(min, `body text, ${where}`).toBeGreaterThanOrEqual(BODY);
  expect(min, `large text, ${where}`).toBeGreaterThanOrEqual(LARGE);
}

describe("colour script", () => {
  it("has the same keys, in the same order, as the story chapters", () => {
    expect(COLOR_SCRIPT.map((c) => c.key)).toEqual(CHAPTERS.map((c) => c.key));
  });

  it("uses only valid hex colours and sane grade values", () => {
    const hexes: string[] = [];
    for (const c of COLOR_SCRIPT as readonly ChapterPalette[]) {
      hexes.push(c.sky.top, c.sky.mid, c.sky.horizon, c.lights.key, c.lights.rim, c.lights.sun, c.accent, c.accent2, c.text);
      if (c.scrim) hexes.push(c.scrim.color);
      expect(c.bloom).toBeGreaterThanOrEqual(0);
      expect(c.bloom).toBeLessThanOrEqual(1);
      expect(Math.abs(c.grade.warmth)).toBeLessThanOrEqual(1);
    }
    for (const h of hexes) expect(h).toMatch(/^#[0-9A-F]{6}$/i);
  });

  it("is Pearl Lab: light only, plum ink, pearl skies, gentle bloom", () => {
    for (const c of COLOR_SCRIPT as readonly ChapterPalette[]) {
      expect(c.tone, c.key).toBe("light");
      expect(c.text, c.key).toBe("#1E1B2E");
      expect(c.scrim, c.key).toBeNull();
      expect(c.bloom, c.key).toBeLessThanOrEqual(0.3);
      // every sky stop stays pale (pearl), so the page never turns dark or neon
      for (const h of [c.sky.top, c.sky.mid, c.sky.horizon]) expect(contrastRatio(h, "#000000"), `${c.key} ${h}`).toBeGreaterThan(18);
    }
  });
});

describe("text contrast through the copy zone (12 to 78 percent of the height)", () => {
  for (const c of COLOR_SCRIPT) {
    it(`${c.key}: ink text holds 4.5 for body and 3 for large`, () => {
      expect(c.text).toBe(INK);
      expectReadable(c.key, c);
    });
  }
});

describe("OKLab mixing", () => {
  it("returns the endpoints exactly and clamps t", () => {
    expect(mixOklab("#E6D3FF", "#13294B", 0)).toBe("#E6D3FF");
    expect(mixOklab("#E6D3FF", "#13294B", 1)).toBe("#13294B");
    expect(mixOklab("#E6D3FF", "#13294B", -3)).toBe("#E6D3FF");
    expect(mixOklab("#E6D3FF", "#13294B", 7)).toBe("#13294B");
  });

  it("black to white mid-point is perceptual mid grey, not the sRGB 50 percent", () => {
    // OKLab L = 0.5 is about #636363; an sRGB mix would give #808080.
    const mid = mixOklab("#000000", "#FFFFFF", 0.5);
    const v = parseInt(mid.slice(1, 3), 16);
    expect(v).toBeGreaterThan(0x5e);
    expect(v).toBeLessThan(0x68);
    expect(mid.slice(1, 3)).toBe(mid.slice(3, 5));
    expect(mid.slice(3, 5)).toBe(mid.slice(5, 7));
  });

  it("gets lighter monotonically from a dark colour towards white", () => {
    let last = -1;
    for (let t = 0; t <= 1.0001; t += 0.1) {
      const l = contrastRatio(mixOklab("#13294B", "#FFFFFF", t), "#000000");
      expect(l).toBeGreaterThanOrEqual(last);
      last = l;
    }
  });
});

describe("contrastRatio", () => {
  it("matches the WCAG reference values", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio("#FFFFFF", "#FFFFFF")).toBeCloseTo(1, 5);
    expect(contrastRatio("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2);
    expect(contrastRatio("#FFF", "#000")).toBeCloseTo(21, 5);
  });

  it("is symmetric", () => {
    expect(contrastRatio(INK, "#FBF8F6")).toBeCloseTo(contrastRatio("#FBF8F6", INK), 10);
  });
});

describe("skyAt", () => {
  it("returns the chapter's own sky at blend 0 and the next chapter's at blend 1", () => {
    const a = skyAt(1, 0);
    expect(a.top).toBe(COLOR_SCRIPT[1].sky.top);
    expect(a.horizon).toBe(COLOR_SCRIPT[1].sky.horizon);
    const b = skyAt(1, 1);
    expect(b.top).toBe(COLOR_SCRIPT[2].sky.top);
    expect(b.tone).toBe(COLOR_SCRIPT[2].tone);
    expect(skyAt(1, 0.25).text).toBe(COLOR_SCRIPT[1].text);
    expect(skyAt(1, 0.75).text).toBe(COLOR_SCRIPT[2].text);
  });

  it("holds the last chapter and clamps bad input", () => {
    const last = COLOR_SCRIPT[COLOR_SCRIPT.length - 1];
    expect(skyAt(99, 0.5).top).toBe(last.sky.top);
    expect(skyAt(-4, -1).top).toBe(COLOR_SCRIPT[0].sky.top);
    expect(skyAt(Number.NaN, Number.NaN).top).toBe(COLOR_SCRIPT[0].sky.top);
  });

  it("moves bloom smoothly through a hand-over", () => {
    expect(skyAt(4, 0.5).bloom).toBeCloseTo((COLOR_SCRIPT[4].bloom + COLOR_SCRIPT[5].bloom) / 2, 5); // prepare to close
  });
});

describe("helpers", () => {
  it("samples the sky at its stops and writes an OKLab CSS gradient", () => {
    const s = COLOR_SCRIPT[0].sky;
    expect(sampleSky(s, 0)).toBe(s.top);
    expect(sampleSky(s, 0.5)).toBe(s.mid);
    expect(sampleSky(s, 1)).toBe(s.horizon);
    expect(skyCss(s)).toContain("in oklab");
  });
});
