import { describe, expect, it } from "vitest";
import { CHAPTERS } from "../story/store";
import {
  BLUSH,
  COLOR_SCRIPT,
  COPY_ZONE,
  ENTER_VARIANTS,
  INK,
  PHASE_COLORS,
  backdropAt,
  contrastRatio,
  cycleAt,
  mixOklab,
  phaseColorAt,
  sampleSky,
  skyAt,
  skyCss,
  timeOfDay,
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
    for (const c of [...COLOR_SCRIPT, ...Object.values(ENTER_VARIANTS)]) {
      hexes.push(c.sky.top, c.sky.mid, c.sky.horizon, c.lights.key, c.lights.rim, c.lights.sun, c.accent, c.accent2, c.text);
      if (c.scrim) hexes.push(c.scrim.color);
      expect(c.bloom).toBeGreaterThanOrEqual(0);
      expect(c.bloom).toBeLessThanOrEqual(1);
      expect(Math.abs(c.grade.warmth)).toBeLessThanOrEqual(1);
    }
    for (const h of hexes) expect(h).toMatch(/^#[0-9A-F]{6}$/i);
  });

  it("matches the plan for anchor values", () => {
    const by = Object.fromEntries(COLOR_SCRIPT.map((c) => [c.key, c]));
    expect(by.enter.sky).toEqual({ top: "#E6D3FF", mid: "#FFC9E3", horizon: "#FFD9B5" });
    expect(by.companion.bloom).toBe(0.9);
    expect(by.noise.bloom).toBe(0.15);
    expect(by.noise.grade.saturation).toBe(-15);
    expect(by.remember.grade.vignette).toBe(0.14);
    expect(by.cycle.sky).toEqual({ top: "#2B1038", mid: "#5A2058", horizon: "#B8467A" });
  });
});

describe("text contrast through the copy zone (12 to 78 percent of the height)", () => {
  for (const c of COLOR_SCRIPT) {
    it(`${c.key}: ${c.tone === "light" ? "ink" : "blush"} text holds 4.5 for body and 3 for large`, () => {
      expect(c.text).toBe(c.tone === "light" ? INK : BLUSH);
      expectReadable(c.key, c);
    });
  }

  for (const [tod, v] of Object.entries(ENTER_VARIANTS)) {
    it(`enter at ${tod} holds contrast`, () => {
      expectReadable(`enter/${tod}`, v);
    });
  }

  it("cycle holds contrast (with its scrim) at every phase and between phases", () => {
    for (let x = 0; x <= 3.001; x += 0.25) {
      expectReadable(`cycle/phase ${x.toFixed(2)}`, cycleAt(x));
    }
  });

  it("cycle needs its scrim: without it the planned sky fails with blush text", () => {
    let failed = 0;
    for (let x = 0; x <= 3.001; x += 0.25) {
      const p = cycleAt(x);
      if (worst({ sky: p.sky, scrim: null, text: p.text }).min < BODY) failed += 1;
    }
    expect(failed).toBeGreaterThan(0);
    expect(cycleAt(0).scrim).not.toBeNull();
  });
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
    expect(contrastRatio(INK, BLUSH)).toBeCloseTo(contrastRatio(BLUSH, INK), 10);
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
    expect(skyAt(7, 0.5).bloom).toBeCloseTo((0.9 + 0.2) / 2, 5); // companion to care
  });

  it("walks the cycle sky through the four phase colours", () => {
    const horizons = [0, 1, 2, 3].map((p) => skyAt(4, 0, p).horizon);
    expect(new Set(horizons).size).toBe(4);
    (["period", "follicular", "ovulation", "luteal"] as const).forEach((name, i) => {
      expect(phaseColorAt(i)).toBe(PHASE_COLORS[name]);
      expect(skyAt(4, 0, i).horizon).toBe(cycleAt(i).sky.horizon);
    });
    // without a phase the planned base sky is untouched
    expect(skyAt(4, 0).horizon).toBe(COLOR_SCRIPT[4].sky.horizon);
  });

  it("fades the cycle scrim in and out across the hand-overs", () => {
    const alpha = COLOR_SCRIPT[4].scrim.alpha;
    expect(skyAt(3, 0).scrim).toBeNull();
    expect(skyAt(3, 1).scrim?.alpha).toBeCloseTo(alpha, 5);
    expect(skyAt(3, 0.5).scrim?.alpha).toBeCloseTo(alpha / 2, 5);
    expect(skyAt(4, 1).scrim).toBeNull();
  });

  it("applies an opening-chapter time-of-day variant", () => {
    expect(skyAt(0, 0, undefined, "night").top).toBe(ENTER_VARIANTS.night.sky.top);
    expect(skyAt(0, 0).top).toBe(ENTER_VARIANTS.dawn.sky.top);
  });
});

describe("helpers", () => {
  it("maps the local hour to four variants", () => {
    expect(timeOfDay(6)).toBe("dawn");
    expect(timeOfDay(12)).toBe("day");
    expect(timeOfDay(18)).toBe("dusk");
    expect(timeOfDay(23)).toBe("night");
    expect(timeOfDay(3)).toBe("night");
    expect(timeOfDay(29)).toBe("dawn");
  });

  it("samples the sky at its stops and writes an OKLab CSS gradient", () => {
    const s = COLOR_SCRIPT[0].sky;
    expect(sampleSky(s, 0)).toBe(s.top);
    expect(sampleSky(s, 0.5)).toBe(s.mid);
    expect(sampleSky(s, 1)).toBe(s.horizon);
    expect(skyCss(s)).toContain("in oklab");
  });
});
