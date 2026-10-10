import { describe, expect, it } from "vitest";
import { CHAPTERS, MOBILE_LEN_FACTOR, story } from "../story/store";
import {
  COLOR_SCRIPT,
  ENTER_VARIANTS,
  PHASE_COLORS,
  composite,
  contrastRatio,
  cycleAt,
  mixOklab,
  phaseColorAt,
  sampleSky,
  skyAt,
  type ChapterPalette,
} from "./palette";
import { SKY_FRAG, SKY_UNIFORMS, SKY_VERT } from "./sky.glsl";
import {
  OVERLAY_CAP,
  calmBackground,
  calmStops,
  hexToUnit,
  mixSky,
  newSkyParams,
  phaseMixAtDay,
  scrimCss,
  skyCanvasSize,
  skyGradient,
  skyParams,
  skyVars,
} from "./sky";

const BODY = 4.5;
const LARGE = 3;
const HEIGHTS = Array.from({ length: 9 }, (_, i) => 0.12 + (0.66 * i) / 8);

describe("chapters and the colour script agree", () => {
  it("every chapter's tone matches its palette, so the text colour and the sky are one decision", () => {
    CHAPTERS.forEach((c, i) => {
      expect(COLOR_SCRIPT[i].key, c.key).toBe(c.key);
      expect(c.tone, c.key).toBe(COLOR_SCRIPT[i].tone);
    });
  });

  it("Numbers is clinical noon: a light sky with dark ink", () => {
    const noise = CHAPTERS.find((c) => c.key === "noise");
    expect(noise?.tone).toBe("light");
    expect(COLOR_SCRIPT.find((c) => c.key === "noise")?.tone).toBe("light");
  });

  it("the store starts on the opening (dawn) sky", () => {
    expect(story.sky.top).toBe(COLOR_SCRIPT[0].sky.top);
    expect(story.sky.mid).toBe(COLOR_SCRIPT[0].sky.mid);
    expect(story.sky.horizon).toBe(COLOR_SCRIPT[0].sky.horizon);
    expect(story.sky.sun).toBe(COLOR_SCRIPT[0].lights.sun);
    expect(story.sky.tone).toBe("light");
  });

  it("phones use the planned 0.8 chapter-length factor", () => {
    expect(MOBILE_LEN_FACTOR).toBe(0.8);
  });
});

describe("phaseMixAtDay", () => {
  it("peaks each phase colour at the middle of its days and mixes between", () => {
    expect(phaseColorAt(phaseMixAtDay(2.5))).toBe(PHASE_COLORS.period);
    expect(phaseColorAt(phaseMixAtDay(9))).toBe(PHASE_COLORS.follicular);
    expect(phaseColorAt(phaseMixAtDay(14.5))).toBe(PHASE_COLORS.ovulation);
    expect(phaseColorAt(phaseMixAtDay(22))).toBe(PHASE_COLORS.luteal);
    expect(phaseMixAtDay(5.75)).toBeCloseTo(0.5, 5);
  });

  it("only moves forward through the day and stays inside 0..3", () => {
    let last = -1;
    for (let d = -2; d <= 30; d += 0.05) {
      const m = phaseMixAtDay(d);
      expect(m).toBeGreaterThanOrEqual(last);
      expect(m).toBeGreaterThanOrEqual(0);
      expect(m).toBeLessThanOrEqual(3);
      last = m;
    }
    expect(phaseMixAtDay(Number.NaN)).toBe(0);
    expect(phaseMixAtDay(27.999)).toBe(3);
  });
});

describe("mixSky", () => {
  const a = skyAt(1, 0);
  const b = skyAt(2, 0);

  it("returns each end exactly and follows the nearer sky for tone", () => {
    expect(mixSky(a, b, 0).top).toBe(a.top);
    expect(mixSky(a, b, 1).horizon).toBe(b.horizon);
    expect(mixSky(a, b, 0.25).tone).toBe(a.tone);
    expect(mixSky(a, b, 0.75).tone).toBe(b.tone);
    expect(mixSky(a, b, 0.4).mid).toBe(mixOklab(a.mid, b.mid, 0.4));
  });

  it("clamps t", () => {
    expect(mixSky(a, b, -5).top).toBe(a.top);
    expect(mixSky(a, b, 5).top).toBe(b.top);
  });
});

describe("CSS sky", () => {
  const s = COLOR_SCRIPT[0].sky;

  it("writes an OKLab gradient and a plain sRGB fallback with the same stops", () => {
    expect(skyGradient(s, true)).toContain("in oklab");
    const plain = skyGradient(s, false);
    expect(plain).not.toContain("oklab");
    for (const c of [s.top, s.mid, s.horizon]) expect(plain).toContain(c);
  });

  it("renders the scrim as rgb() or transparent", () => {
    expect(scrimCss(null)).toBe("transparent");
    expect(scrimCss({ color: "#1C0A26", alpha: 0 })).toBe("transparent");
    expect(scrimCss({ color: "#1C0A26", alpha: 0.35 })).toBe("rgb(28 10 38 / 0.35)");
  });

  it("starts the server render on the opening colours", () => {
    const v = skyVars(COLOR_SCRIPT[0]);
    expect(v["--sky-top"]).toBe(s.top);
    expect(v["--sky-hor"]).toBe(s.horizon);
    expect(v["--bg"]).toBe(s.mid);
    expect(v["--scrim"]).toBe("transparent");
  });
});

describe("the calm (static) page keeps every pixel readable", () => {
  /** Colour at height h of the calm background (flat scrim over the three-stop gradient, mixed in OKLab). */
  const colorAt = (p: Pick<ChapterPalette, "sky" | "scrim">, h: number) => {
    const c = calmStops(p.sky);
    const base = h <= 0.5 ? mixOklab(c.top, c.mid, h / 0.5) : mixOklab(c.mid, c.horizon, (h - 0.5) / 0.5);
    return p.scrim ? composite(base, p.scrim.color, p.scrim.alpha) : base;
  };

  const all: Array<[string, ChapterPalette]> = [
    ...COLOR_SCRIPT.map((c) => [c.key, c] as [string, ChapterPalette]),
    ...[0, 0.5, 1, 1.5, 2, 2.5, 3].map((x) => [`cycle/${x}`, cycleAt(x)] as [string, ChapterPalette]),
  ];

  for (const [name, p] of all) {
    it(`${name}: the whole background, top to bottom, holds 4.5 for ${p.tone === "light" ? "ink" : "blush"} text`, () => {
      for (let i = 0; i <= 20; i += 1) {
        const h = i / 20;
        expect(contrastRatio(colorAt(p, h), p.text), `${name} at ${h}`).toBeGreaterThanOrEqual(BODY);
      }
    });
  }

  it("stays on the tested part of the sky", () => {
    const sky = COLOR_SCRIPT[3].sky;
    const c = calmStops(sky);
    expect(c.top).toBe(sampleSky(sky, 0.12));
    expect(c.horizon).toBe(sampleSky(sky, 0.78));
  });

  it("adds the scrim only where a chapter has one, in both gradient flavours", () => {
    const cycle = COLOR_SCRIPT.find((c) => c.key === "cycle")!;
    expect(calmBackground(cycle, true)).toContain("rgb(28 10 38 / 0.35)");
    expect(calmBackground(cycle, false)).not.toContain("oklab");
    expect(calmBackground(COLOR_SCRIPT[0], true)).not.toContain("rgb(");
  });
});

describe("the shader's overlay budget", () => {
  // glow + rays + haze can lighten the sky toward the sun colour by at most OVERLAY_CAP[tone];
  // copy must still pass at that worst case, everywhere in the copy zone.
  const cases: Array<[string, ChapterPalette | (typeof ENTER_VARIANTS)[keyof typeof ENTER_VARIANTS] & { sky: ChapterPalette["sky"] }]> = [
    ...COLOR_SCRIPT.map((c) => [c.key, c] as [string, ChapterPalette]),
    ...Object.entries(ENTER_VARIANTS).map(([k, v]) => [`enter/${k}`, v] as [string, never]),
    ...[0, 0.5, 1, 1.5, 2, 2.5, 3].map((x) => [`cycle/${x}`, cycleAt(x)] as [string, ChapterPalette]),
  ];

  for (const [name, p] of cases) {
    it(`${name}: copy holds contrast with the glow, rays and haze at their cap`, () => {
      const cap = OVERLAY_CAP[p.tone];
      for (const h of HEIGHTS) {
        let bg = sampleSky(p.sky, h);
        if (p.scrim) bg = composite(bg, p.scrim.color, p.scrim.alpha);
        const lit = composite(bg, p.lights.sun, cap);
        const r = contrastRatio(lit, p.text);
        expect(r, `${name} at ${h.toFixed(2)}`).toBeGreaterThanOrEqual(BODY);
        expect(r).toBeGreaterThanOrEqual(LARGE);
      }
    });
  }

  it("lets light skies glow more than dark ones", () => {
    expect(OVERLAY_CAP.light).toBeGreaterThan(OVERLAY_CAP.dark);
  });
});

describe("skyParams", () => {
  it("puts the sun top-left on light skies and a small moon top-right on dark ones", () => {
    const light = skyParams(0, "full", newSkyParams());
    const dark = skyParams(1, "full", newSkyParams());
    expect(light.sunX).toBeLessThan(0.5);
    expect(dark.sunX).toBeGreaterThan(0.5);
    expect(dark.sunSize).toBeLessThan(light.sunSize);
    expect(dark.cap).toBe(OVERLAY_CAP.dark);
    expect(light.cap).toBe(OVERLAY_CAP.light);
  });

  it("eases between the two, clamps, and writes into the object it is given", () => {
    const out = newSkyParams();
    expect(skyParams(0.5, "lite", out)).toBe(out);
    const mid = out.sunX;
    expect(mid).toBeGreaterThan(skyParams(0, "lite", newSkyParams()).sunX);
    expect(mid).toBeLessThan(skyParams(1, "lite", newSkyParams()).sunX);
    expect(skyParams(7, "lite", newSkyParams()).sunX).toBe(skyParams(1, "lite", newSkyParams()).sunX);
    expect(skyParams(-3, "lite", newSkyParams()).sunX).toBe(skyParams(0, "lite", newSkyParams()).sunX);
  });

  it("keeps haze lighter on the lite tier", () => {
    expect(skyParams(0, "lite", newSkyParams()).haze).toBeLessThan(skyParams(0, "full", newSkyParams()).haze);
  });
});

describe("skyCanvasSize", () => {
  it("renders the sky at a fraction of the screen, capped by tier", () => {
    expect(skyCanvasSize(1440, 900, "full", 1)).toEqual({ w: 1080, h: 675 });
    expect(skyCanvasSize(1440, 900, "full", 3)).toEqual({ w: 1620, h: 1013 }); // dpr capped at 1.5
    expect(skyCanvasSize(390, 844, "lite", 3)).toEqual({ w: 195, h: 422 }); // lite: dpr 1, half size
  });

  it("is never smaller than one pixel and survives a bad ratio", () => {
    expect(skyCanvasSize(0, 0, "lite", 0)).toEqual({ w: 1, h: 1 });
    expect(skyCanvasSize(100, 100, "lite", Number.NaN)).toEqual({ w: 50, h: 50 });
  });
});

describe("hexToUnit", () => {
  it("maps hex to 0..1 sRGB", () => {
    expect(hexToUnit("#000000")).toEqual([0, 0, 0]);
    expect(hexToUnit("#FFFFFF")).toEqual([1, 1, 1]);
    expect(hexToUnit("#FF0000")[0]).toBe(1);
  });
});

describe("sky shader source", () => {
  it("is GLSL ES 3.00 with a full-screen triangle that needs no attributes", () => {
    expect(SKY_VERT.startsWith("#version 300 es")).toBe(true);
    expect(SKY_FRAG.startsWith("#version 300 es")).toBe(true);
    expect(SKY_VERT).toContain("gl_VertexID");
  });

  it("declares exactly the uniforms the component sets", () => {
    const declared = [...SKY_FRAG.matchAll(/^uniform\s+\w+\s+(\w+);/gm)].map((m) => m[1]).sort();
    expect([...SKY_UNIFORMS].sort()).toEqual(declared);
  });

  it("mixes in OKLab and dithers", () => {
    expect(SKY_FRAG).toContain("labToSrgb");
    expect(SKY_FRAG).toContain("52.9829189"); // interleaved gradient noise
  });
});
