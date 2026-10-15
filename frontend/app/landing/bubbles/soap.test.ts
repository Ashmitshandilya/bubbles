import { describe, expect, it } from "vitest";
import { CHAPTERS } from "../story/store";
import { DROP_LIFE_S, Droplets, MAX_DROPS } from "./pop";
import { SOAP_FRAG, SOAP_UNIFORMS, SOAP_VERT } from "./soap.glsl";
import { BUBBLE_LEVEL, MAX_BUBBLES, POP_S, SoapField, bubbleCount, levelAt, mulberry32, type StepInput } from "./soap";

const view = { vw: 1440, vh: 900, mobile: false };
const input = (over: Partial<StepInput> = {}): StepInput => ({
  ...view,
  time: 0,
  level: 1,
  active: MAX_BUBBLES,
  excite: 0,
  pointer: null,
  rects: [],
  ...over,
});

/** Run a field for `seconds` in 1/60 s steps. */
function run(field: SoapField, seconds: number, over: Partial<StepInput> = {}) {
  let t = 0;
  for (let k = 0; k < Math.round(seconds * 60); k += 1) {
    t += 1 / 60;
    field.step(1 / 60, input({ time: t, ...over }));
  }
}

describe("tiers and chapter levels", () => {
  it("draws 12 bubbles in full, 6 in lite and none in static", () => {
    expect(bubbleCount("full")).toBe(12);
    expect(bubbleCount("lite")).toBe(6);
    expect(bubbleCount("static")).toBe(0);
  });

  it("has a level for every chapter: busiest in the hero and the finale, none in care", () => {
    expect(Object.keys(BUBBLE_LEVEL).sort()).toEqual(CHAPTERS.map((c) => c.key).sort());
    expect(BUBBLE_LEVEL.enter).toBe(1);
    expect(BUBBLE_LEVEL.bubbles).toBe(1);
    expect(BUBBLE_LEVEL.care).toBe(0);
    for (const v of Object.values(BUBBLE_LEVEL)) expect(v).toBeGreaterThanOrEqual(0);
  });

  it("glides between chapter levels through a hand-over and clamps bad input", () => {
    expect(levelAt(0, 0)).toBe(1);
    expect(levelAt(0, 1)).toBeCloseTo(BUBBLE_LEVEL.body, 6);
    const mid = levelAt(0, 0.5);
    expect(mid).toBeGreaterThan(BUBBLE_LEVEL.body);
    expect(mid).toBeLessThan(1);
    expect(levelAt(8, 1)).toBeCloseTo(BUBBLE_LEVEL.bubbles, 6); // care into the finale
    expect(levelAt(99, 5)).toBe(BUBBLE_LEVEL.bubbles);
    expect(levelAt(-3, -1)).toBe(1);
  });
});

describe("SoapField", () => {
  it("is deterministic for a seed", () => {
    const a = new SoapField(3);
    const b = new SoapField(3);
    run(a, 3);
    run(b, 3);
    expect(Array.from(a.x)).toEqual(Array.from(b.x));
    expect(Array.from(a.y)).toEqual(Array.from(b.y));
    expect(mulberry32(5)()).toBe(mulberry32(5)());
  });

  it("wakes the bubbles one after another, then holds them in view", () => {
    const f = new SoapField();
    run(f, 0.3);
    expect(f.vis.every((v) => v === 0)).toBe(true);
    run(f, 6);
    expect(f.vis.every((v) => v > 0.9)).toBe(true);
    expect(f.alpha.every((a) => a > 0.3)).toBe(true);
  });

  it("only wakes as many bubbles as the tier draws", () => {
    const f = new SoapField();
    run(f, 6, { active: 6 });
    for (let i = 0; i < 6; i += 1) expect(f.vis[i]).toBeGreaterThan(0.9);
    for (let i = 6; i < MAX_BUBBLES; i += 1) expect(f.vis[i]).toBe(0);
  });

  it("rises, and a bubble that leaves the top comes back from below", () => {
    const f = new SoapField();
    run(f, 1);
    const before = Array.from(f.y);
    run(f, 1);
    expect(f.y.some((y, i) => y < before[i])).toBe(true);
    let wrapped = 0;
    let last = Array.from(f.y);
    for (let k = 0; k < 60 * 60; k += 1) {
      f.step(1 / 60, input({ time: k / 60 }));
      f.y.forEach((y, i) => {
        if (y > last[i] + 50) wrapped += 1;
      });
      last = Array.from(f.y);
      for (let i = 0; i < MAX_BUBBLES; i += 1) expect(f.y[i]).toBeLessThan(900 + f.r[i] * 3 + 900 * 0.3);
    }
    expect(wrapped).toBeGreaterThan(0);
  });

  it("swells with excitement", () => {
    const calm = new SoapField();
    const keen = new SoapField();
    run(calm, 1);
    run(keen, 1, { excite: 1 });
    expect(keen.r[2]).toBeGreaterThan(calm.r[2]);
  });

  it("slides bubbles round a copy block and never leaves one inside it for long", () => {
    const rects = [{ l: 80, t: 300, r: 740, b: 860 }];
    const f = new SoapField();
    run(f, 8, { rects });
    let inside = 0;
    let samples = 0;
    for (let k = 0; k < 60 * 20; k += 1) {
      f.step(1 / 60, input({ time: 8 + k / 60, rects }));
      for (let i = 0; i < MAX_BUBBLES; i += 1) {
        if (f.vis[i] < 0.5) continue;
        samples += 1;
        const overlapsX = f.x[i] + f.r[i] * 0.7 > rects[0].l && f.x[i] - f.r[i] * 0.7 < rects[0].r;
        const overlapsY = f.y[i] + f.r[i] * 0.7 > rects[0].t && f.y[i] - f.r[i] * 0.7 < rects[0].b;
        if (overlapsX && overlapsY) inside += 1;
      }
    }
    expect(samples).toBeGreaterThan(0);
    // the push is eased, so a bubble may brush the block as it arrives, but it does not live there
    expect(inside / samples).toBeLessThan(0.05);
  });

  it("fades bubbles that have no free side (a phone with full-width copy)", () => {
    const f = new SoapField();
    const rects = [{ l: 10, t: -100, r: 380, b: 1000 }];
    run(f, 8, { vw: 390, vh: 844, mobile: true, rects });
    expect(f.alpha.every((a) => a < 0.02)).toBe(true);
  });

  it("dims the whole field in a calm chapter", () => {
    const busy = new SoapField();
    const calm = new SoapField();
    run(busy, 6, { level: 1 });
    run(calm, 6, { level: 0.1 });
    expect(calm.alpha[2]).toBeLessThan(busy.alpha[2]);
  });
});

describe("popping", () => {
  it("hits the bubble the point is deepest inside, and misses empty sky", () => {
    const f = new SoapField();
    run(f, 6);
    const i = 2;
    expect(f.hit(f.x[i], f.y[i])).toBe(i);
    expect(f.hit(-500, -500)).toBe(-1);
  });

  it("cannot pop what is not yet visible, or pop twice", () => {
    const f = new SoapField();
    run(f, 0.1);
    expect(f.popAt(0)).toBe(false);
    run(f, 6);
    expect(f.popAt(0)).toBe(true);
    expect(f.popAt(0)).toBe(false);
    expect(f.popAt(-1)).toBe(false);
    expect(f.popAt(MAX_BUBBLES)).toBe(false);
  });

  it("bursts for POP_S seconds, then the bubble is reborn below the screen and fades back in", () => {
    const f = new SoapField();
    run(f, 6);
    f.popAt(1);
    run(f, POP_S / 2);
    expect(f.pop[1]).toBeGreaterThan(0.3);
    expect(f.pop[1]).toBeLessThan(0.8);
    expect(f.hit(f.x[1], f.y[1])).not.toBe(1);
    run(f, POP_S);
    expect(f.pop[1]).toBe(0);
    expect(f.y[1]).toBeGreaterThan(900 - 5);
    run(f, 6);
    expect(f.vis[1]).toBeGreaterThan(0.9);
  });

  it("lights up the hovered bubble and lets it go", () => {
    const f = new SoapField();
    run(f, 6);
    expect(f.hoverAt(f.x[2], f.y[2])).toBe(true);
    run(f, 0.5);
    expect(f.hover[2]).toBeGreaterThan(0.9);
    f.clearHover();
    run(f, 0.5);
    expect(f.hover[2]).toBeLessThan(0.05);
  });
});

describe("Droplets", () => {
  it("throws a burst, fades it out within its life, and recycles the pool without growing", () => {
    const d = new Droplets();
    let n = 0;
    const rand = () => ((n += 0.37) % 1);
    d.burst(100, 100, 60, rand);
    expect(d.alive).toBe(10);
    for (let k = 0; k < Math.ceil(DROP_LIFE_S * 60) + 2; k += 1) d.step(1 / 60);
    expect(d.alive).toBe(0);
    for (let k = 0; k < 10; k += 1) d.burst(0, 0, 40, rand);
    expect(d.alive).toBe(MAX_DROPS);
    expect(d.life.length).toBe(MAX_DROPS);
  });

  it("throws droplets outward from the bubble's rim", () => {
    const d = new Droplets();
    d.burst(500, 400, 80, mulberry32(1), 8);
    d.step(0.1);
    for (let i = 0; i < 8; i += 1) expect(Math.hypot(d.x[i] - 500, d.y[i] - 400)).toBeGreaterThan(80 * 0.7 - 1);
  });
});

describe("soap shader source", () => {
  it("declares the uniforms and per-instance attributes the component sets", () => {
    for (const u of SOAP_UNIFORMS) expect(SOAP_VERT + SOAP_FRAG).toContain(u);
    for (const a of ["aSeed", "aPop", "aAlpha", "aHover"]) expect(SOAP_VERT).toContain(`attribute float ${a}`);
  });

  it("builds the film from a cosine palette, fresnel, a window highlight, and dithers", () => {
    expect(SOAP_FRAG).toContain("cos(6.28318");
    expect(SOAP_FRAG).toContain("fres");
    expect(SOAP_FRAG).toContain("win");
    expect(SOAP_FRAG).toContain("gl_FragCoord");
    expect(SOAP_VERT).toContain("instanceMatrix");
  });
});
