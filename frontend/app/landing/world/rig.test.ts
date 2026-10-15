import { describe, expect, it } from "vitest";
import { CHAPTERS } from "../story/store";
import { ARRIVE_END, RIGS, SETTLE_START, doPhase, type Env } from "./rig";
import { FIREFLY_SHARE, fireflyFade, fireflyGlow, fireflyThreshold } from "./fireflies";

const envOf = (mobile: boolean): Env => ({ mobile, aspect: mobile ? 0.46 : 1.6, time: 3.2, intro: 5 });
const PS = [0, 0.1, 0.15, 0.3, 0.5, 0.7, 0.85, 0.95, 1];

const flat = (o: unknown): number[] => {
  if (typeof o === "number") return [o];
  if (Array.isArray(o)) return o.flatMap(flat);
  if (o && typeof o === "object") return Object.values(o).flatMap(flat);
  return [];
};

describe("chapter rigs", () => {
  it("has one rig per chapter", () => {
    expect(RIGS).toHaveLength(CHAPTERS.length);
  });

  it("returns only finite numbers at every progress, on desktop and on phones", () => {
    for (const mobile of [false, true]) {
      RIGS.forEach((rig, i) => {
        for (const p of PS) {
          const r = rig(p, envOf(mobile));
          const nums = flat(r);
          expect(nums.length, `${CHAPTERS[i].key} @ ${p}`).toBeGreaterThan(20);
          expect(nums.every(Number.isFinite), `${CHAPTERS[i].key} @ ${p}`).toBe(true);
        }
      });
    }
  });

  it("keeps the fireflies for the night chapters: remember most, then the companion, then connect's twilight", () => {
    const fireflies = Object.fromEntries(CHAPTERS.map((c, i) => [c.key, RIGS[i](0.5, envOf(false)).fireflies]));
    expect(fireflies.remember).toBe(1);
    expect(fireflies.companion).toBeGreaterThan(fireflies.connect);
    expect(fireflies.connect).toBeGreaterThan(0);
    for (const day of ["enter", "body", "noise", "track", "cycle", "care", "bubbles"]) expect(fireflies[day]).toBe(0);
    for (const v of Object.values(fireflies)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });
});

describe("arrive, do, settle (plan 2.7)", () => {
  it("holds still while the chapter arrives and settles, and moves in between", () => {
    expect(ARRIVE_END).toBe(0.15);
    expect(SETTLE_START).toBe(0.85);
    expect(doPhase(0)).toBe(0);
    expect(doPhase(ARRIVE_END)).toBe(0);
    expect(doPhase(SETTLE_START)).toBe(1);
    expect(doPhase(1)).toBe(1);
    expect(doPhase(0.5)).toBeCloseTo(0.5, 6);
  });

  it("never goes backwards", () => {
    let last = -1;
    for (let k = 0; k <= 100; k += 1) {
      const v = doPhase(k / 100);
      expect(v).toBeGreaterThanOrEqual(last);
      last = v;
    }
  });

  it("gives the Numbers chapter a camera that rests at both ends", () => {
    const noise = RIGS[CHAPTERS.findIndex((c) => c.key === "noise")];
    const at = (p: number) => noise(p, envOf(false)).cam[2];
    expect(at(0)).toBeCloseTo(at(0.14), 9);
    expect(at(0.86)).toBeCloseTo(at(1), 9);
    expect(at(0.5)).toBeLessThan(at(0.14));
    expect(at(1)).toBeCloseTo(7.6, 9);
  });
});

describe("fireflies", () => {
  it("keeps every cell by day and about one in seven at full night", () => {
    expect(fireflyThreshold(0)).toBe(1);
    expect(fireflyThreshold(1)).toBeCloseTo(FIREFLY_SHARE, 9);
    expect(fireflyThreshold(2)).toBeCloseTo(FIREFLY_SHARE, 9);
  });

  it("fades the rest out rather than blinking them off, and never touches the day", () => {
    for (const keep of [0, 0.3, 0.9, 0.999]) expect(fireflyFade(keep, fireflyThreshold(0), 0)).toBe(1);
    expect(fireflyFade(0.01, fireflyThreshold(1), 1)).toBe(1);
    expect(fireflyFade(0.5, fireflyThreshold(1), 1)).toBe(0);
    const edge = fireflyFade(FIREFLY_SHARE - 0.06, fireflyThreshold(1), 1);
    expect(edge).toBeGreaterThan(0);
    expect(edge).toBeLessThan(1);
  });

  it("twinkles between 0.3 and 1 at night, on a clock that pauses with the page", () => {
    expect(fireflyGlow(0, 12.3, 1, 0.4)).toBe(1);
    const values = Array.from({ length: 200 }, (_, k) => fireflyGlow(1, k * 0.05, 1.1, 0.7));
    expect(Math.min(...values)).toBeGreaterThanOrEqual(0.3 - 1e-9);
    expect(Math.max(...values)).toBeLessThanOrEqual(1 + 1e-9);
    expect(Math.max(...values) - Math.min(...values)).toBeGreaterThan(0.5);
    // the same idle time gives the same glow: freezing the clock freezes the twinkle
    expect(fireflyGlow(1, 4.2, 0.9, 1.3)).toBe(fireflyGlow(1, 4.2, 0.9, 1.3));
  });
});
