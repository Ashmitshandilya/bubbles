import { describe, expect, it } from "vitest";
import { RING, THREADS, smoothPath, threadPaths } from "./ring";

describe("the example cycle ring", () => {
  it("draws the four phases in cycle order, each with a label", () => {
    expect(RING.phases.map((p) => p.key)).toEqual(["period", "follicular", "ovulation", "luteal"]);
    for (const p of RING.phases) {
      expect(p.arc).toMatch(/^M[\d.]+ [\d.]+ A/);
      expect(p.name.length).toBeGreaterThan(0);
    }
    expect(RING.phases.find((p) => p.key === "ovulation")?.name).toContain("estimate");
  });

  it("has sleep, mood and energy threads; the mood thread breaks where two days were not logged", () => {
    expect(THREADS.map((t) => t.key)).toEqual(["sleep", "mood", "energy"]);
    expect(THREADS.find((t) => t.key === "sleep")?.paths).toHaveLength(1);
    expect(THREADS.find((t) => t.key === "sleep")?.paths[0].endsWith("Z")).toBe(true);
    const mood = THREADS.find((t) => t.key === "mood")!;
    expect(mood.paths).toHaveLength(1);
    expect(mood.paths[0].endsWith("Z")).toBe(false);
  });

  it("never draws across a gap: each logged stretch is its own open path", () => {
    const band = { base: 100, swing: 10, lo: 0, hi: 1 };
    expect(threadPaths([0.5, 0.5, null, 0.5, 0.5, null, 0.5, 0.5], band)).toHaveLength(2);
    expect(threadPaths([0.5, null, 0.5, null], band)).toHaveLength(0);
  });

  it("smooths points into one curve per segment", () => {
    const d = smoothPath([[0, 0], [10, 0], [10, 10]], false);
    expect(d.match(/C/g)).toHaveLength(2);
    expect(smoothPath([[0, 0]], false)).toBe("");
  });
});
