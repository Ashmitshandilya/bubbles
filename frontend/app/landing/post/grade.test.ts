import { describe, expect, it } from "vitest";
import { COLOR_SCRIPT } from "../atmosphere/palette";
import { GRADE_FRAG, GRADE_UNIFORMS, GRADE_VERT } from "./grade.glsl";
import { POST, bloomStrength, fadeAmount, gradeUniforms, newGradeUniforms, postAllowed, postTargetSize, postWanted } from "./grade";

const chapter = (key: string) => COLOR_SCRIPT.find((c) => c.key === key)!;

describe("when the post stack runs", () => {
  it("only in the full tier (never lite or static)", () => {
    expect(postWanted("full")).toBe(true);
    expect(postWanted("lite")).toBe(false);
    expect(postWanted("static")).toBe(false);
  });

  it("can be switched off for comparison with ?post=0", () => {
    expect(postAllowed("")).toBe(true);
    expect(postAllowed("?x=1")).toBe(true);
    expect(postAllowed("?post=0")).toBe(false);
    expect(postAllowed("?a=1&post=0")).toBe(false);
    expect(postAllowed("?post=1")).toBe(true);
  });
});

describe("grade from the colour script", () => {
  it("is the identity at amount 0, for every chapter (the stack fades in from nothing)", () => {
    for (const c of COLOR_SCRIPT) {
      const u = gradeUniforms(c.grade, 0, newGradeUniforms());
      expect(u.warm).toEqual([1, 1, 1]);
      expect(u.sat).toBe(1);
      expect(u.con).toBe(1);
      expect(u.lift).toBe(0);
      expect(u.vig).toBe(0);
    }
  });

  it("warm chapters push red up and blue down, cool chapters the other way", () => {
    const warm = gradeUniforms(chapter("track").grade, 1, newGradeUniforms());
    expect(warm.warm[0]).toBeGreaterThan(1);
    expect(warm.warm[2]).toBeLessThan(1);
    const cool = gradeUniforms(chapter("body").grade, 1, newGradeUniforms());
    expect(cool.warm[0]).toBeLessThan(1);
    expect(cool.warm[2]).toBeGreaterThan(1);
  });

  it("follows saturation and contrast in percent points (Numbers is desaturated and crisper)", () => {
    const noon = gradeUniforms(chapter("noise").grade, 1, newGradeUniforms());
    expect(noon.sat).toBeCloseTo(0.85, 6);
    expect(noon.con).toBeCloseTo(1.08, 6);
    const care = gradeUniforms(chapter("care").grade, 1, newGradeUniforms());
    expect(care.con).toBeLessThan(1);
  });

  it("carries the page vignette through at the same strength as --vig", () => {
    expect(gradeUniforms(chapter("remember").grade, 1, newGradeUniforms()).vig).toBeCloseTo(0.14, 6);
  });

  it("stays subtle: no chapter moves a channel by more than 10 percent, or lifts by more than 0.01", () => {
    for (const c of COLOR_SCRIPT) {
      const u = gradeUniforms(c.grade, 1, newGradeUniforms());
      for (const w of u.warm) expect(Math.abs(w - 1)).toBeLessThan(0.1);
      expect(u.lift).toBeLessThan(0.01);
      expect(Math.abs(u.sat - 1)).toBeLessThan(0.2);
      expect(Math.abs(u.con - 1)).toBeLessThan(0.1);
    }
  });

  it("writes into the object it is given, with no allocation", () => {
    const out = newGradeUniforms();
    const warm = out.warm;
    expect(gradeUniforms(chapter("enter").grade, 1, out)).toBe(out);
    expect(out.warm).toBe(warm);
  });
});

describe("bloom from the colour script", () => {
  it("is zero when faded out and grows with the chapter's bloom value", () => {
    expect(bloomStrength(0.9, 0)).toBe(0);
    expect(bloomStrength(0, 1)).toBe(0);
    expect(bloomStrength(0.5, 1)).toBeGreaterThan(bloomStrength(0.15, 1));
  });

  it("makes the companion chapter the one big bloom, and keeps every chapter gentle", () => {
    const strengths = COLOR_SCRIPT.map((c) => bloomStrength(c.bloom, 1));
    const companion = bloomStrength(chapter("companion").bloom, 1);
    expect(companion).toBe(Math.max(...strengths));
    expect(companion).toBeLessThanOrEqual(0.75);
    // the opening chapter sits at the plan's "about 0.35" (scaled by the gain)
    expect(bloomStrength(chapter("enter").bloom, 1)).toBeCloseTo(0.35 * POST.bloomGain, 6);
  });

  it("clamps out-of-range input", () => {
    expect(bloomStrength(5, 5)).toBeCloseTo(POST.bloomGain, 6);
    expect(bloomStrength(-1, 1)).toBe(0);
  });
});

describe("target size and multisampling", () => {
  it("never renders the targets above the pixel ratio cap", () => {
    expect(postTargetSize(1000, 600, 1).width).toBe(1000);
    expect(postTargetSize(1000, 600, 1.75)).toMatchObject({ width: 1500, height: 900 });
    expect(postTargetSize(1000, 600, 3)).toMatchObject({ width: 1500, height: 900 });
    expect(postTargetSize(1000, 600, 0.5).width).toBe(1000);
    expect(postTargetSize(1000, 600, Number.NaN).width).toBe(1000);
  });

  it("steps the samples down as the screen grows, to keep memory sane", () => {
    expect(postTargetSize(1440, 900, 1).samples).toBe(4); // 1.3 MP
    expect(postTargetSize(1920, 1080, 1.5).samples).toBe(2); // 4.7 MP
    expect(postTargetSize(3840, 2160, 1).samples).toBe(0); // 8.3 MP
  });

  it("is never smaller than one pixel", () => {
    expect(postTargetSize(0, 0, 1)).toMatchObject({ width: 1, height: 1 });
  });
});

describe("fading in and out", () => {
  it("rises toward 1 while wanted and snaps to 0 once it has faded out", () => {
    let a = 0;
    for (let i = 0; i < 120; i += 1) a = fadeAmount(a, true, 1 / 60);
    expect(a).toBeGreaterThan(0.95);
    expect(a).toBeLessThanOrEqual(1);
    for (let i = 0; i < 240 && a > 0; i += 1) a = fadeAmount(a, false, 1 / 60);
    expect(a).toBe(0);
  });

  it("does not move on a zero or negative frame time", () => {
    expect(fadeAmount(0.5, true, 0)).toBe(0.5);
    expect(fadeAmount(0.5, true, -1)).toBe(0.5);
  });
});

describe("the grade shader", () => {
  it("lets three apply the renderer's tone mapping, then the output colour space, in that order", () => {
    const tone = GRADE_FRAG.indexOf("#include <tonemapping_fragment>");
    const space = GRADE_FRAG.indexOf("#include <colorspace_fragment>");
    expect(tone).toBeGreaterThan(0);
    expect(space).toBeGreaterThan(tone);
  });

  it("un-premultiplies before grading and premultiplies last, so the transparent canvas stays correct", () => {
    expect(GRADE_FRAG).toContain("c.rgb / a");
    const lastLine = GRADE_FRAG.trim().split("\n").filter((l) => l.includes("gl_FragColor")).pop() ?? "";
    expect(lastLine).toContain("outA");
  });

  it("declares every uniform the stack sets, and has a vertex shader that passes the uv through", () => {
    for (const name of GRADE_UNIFORMS) expect(GRADE_FRAG).toMatch(new RegExp(`uniform\\s+\\w+\\s+${name};`));
    expect(GRADE_VERT).toContain("vUv = uv");
  });
});
