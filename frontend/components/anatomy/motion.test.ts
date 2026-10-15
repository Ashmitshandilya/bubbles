import { describe, expect, it } from "vitest";
import { SELECTED_SCALE, easeFactor, isSettled, organOpacity, pulse, stepSpring } from "./motion";

function run(seconds: number, target: number, from = 1, fps = 60) {
  let s = { x: from, v: 0 };
  let peak = from;
  for (let i = 0; i < seconds * fps; i += 1) {
    s = stepSpring(s, target, 1 / fps);
    peak = Math.max(peak, s.x);
  }
  return { s, peak };
}

describe("selection spring", () => {
  it("reaches the selected size in about a second and stays there", () => {
    const { s } = run(1, SELECTED_SCALE);
    expect(s.x).toBeCloseTo(SELECTED_SCALE, 2);
    expect(isSettled(s, SELECTED_SCALE)).toBe(true);
  });

  it("bumps: overshoots a little, but only a little", () => {
    const { peak } = run(1, SELECTED_SCALE);
    expect(peak).toBeGreaterThan(SELECTED_SCALE + 0.01);
    expect(peak).toBeLessThan(SELECTED_SCALE + 0.08);
  });

  it("goes back down to normal size when it is no longer selected", () => {
    const { s } = run(1, 1, SELECTED_SCALE);
    expect(s.x).toBeCloseTo(1, 2);
  });

  it("is the same at 30 and 144 frames per second", () => {
    expect(run(0.5, SELECTED_SCALE, 1, 30).s.x).toBeCloseTo(run(0.5, SELECTED_SCALE, 1, 144).s.x, 1);
  });

  it("stays stable after a very long frame (a tab coming back)", () => {
    const s = stepSpring({ x: 1, v: 0 }, SELECTED_SCALE, 30);
    expect(Number.isFinite(s.x)).toBe(true);
    expect(s.x).toBeGreaterThan(1);
    expect(s.x).toBeLessThan(1.6);
  });

  it("ignores a negative or missing frame time", () => {
    expect(stepSpring({ x: 1, v: 0 }, 2, -1)).toEqual({ x: 1, v: 0 });
  });
});

describe("pulse", () => {
  const samples = (id: string, seconds: number, hz = 200) => Array.from({ length: seconds * hz }, (_, i) => pulse(id, i / hz));
  const peaks = (values: number[], min: number) => values.filter((v, i) => i > 0 && i < values.length - 1 && v > values[i - 1] && v >= values[i + 1] && v > min).length;

  it("stays gentle for every organ", () => {
    for (const id of ["heart", "lungs", "brain", "eyes", "unknown_organ"]) {
      for (const v of samples(id, 8)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(0.1);
      }
    }
  });

  it("makes the heart beat twice (lub-dub) every beat", () => {
    const beat = samples("heart", 1).slice(0, 170);          // one 0.85 s beat at 200 samples/s
    expect(peaks(beat, 0.02)).toBe(2);
    expect(Math.max(...beat.slice(0, 40))).toBeGreaterThan(Math.max(...beat.slice(40)));   // the first beat is the stronger one
  });

  it("breathes the lungs slowly: one swell every four seconds", () => {
    expect(peaks(samples("lungs", 8), 0.04)).toBe(2);
  });

  it("is zero for a clock that is not a number", () => {
    expect(pulse("heart", NaN)).toBe(0);
    expect(pulse("lungs", Infinity)).toBe(0);
  });
});

describe("dimming and easing", () => {
  it("dims everything except the selected organ", () => {
    expect(organOpacity(true, true)).toBe(1);
    expect(organOpacity(false, true)).toBe(0.5);
  });

  it("shows every organ at full strength when nothing is selected", () => {
    expect(organOpacity(false, false)).toBe(1);
  });

  it("eases by a fraction between 0 and 1", () => {
    expect(easeFactor(0, 6)).toBe(0);
    expect(easeFactor(1 / 60, 6)).toBeGreaterThan(0);
    expect(easeFactor(10, 6)).toBeLessThanOrEqual(1);
    expect(easeFactor(-1, 6)).toBe(0);
  });
});
