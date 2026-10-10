/**
 * Checks for the soap-pop geometry. Run: npx vitest run app/lib/soap-pop.test.ts
 * Deterministic (same pop every time, no hydration mismatch) and always inside the radius.
 */
import { describe, expect, it } from "vitest";
import { burstDroplets } from "./soap-pop";

describe("burstDroplets", () => {
  it("makes the requested number of droplets and none for zero or nonsense", () => {
    expect(burstDroplets(8)).toHaveLength(8);
    expect(burstDroplets(0)).toEqual([]);
    expect(burstDroplets(-3)).toEqual([]);
    expect(burstDroplets(Number.NaN)).toEqual([]);
  });

  it("is deterministic", () => {
    expect(burstDroplets(8, 30)).toEqual(burstDroplets(8, 30));
  });

  it("starts straight up and never goes past the radius", () => {
    const drops = burstDroplets(8, 28);
    expect(drops[0]).toMatchObject({ x: 0, y: -28 });
    for (const d of drops) {
      expect(Number.isFinite(d.x) && Number.isFinite(d.y)).toBe(true);
      expect(Math.hypot(d.x, d.y)).toBeLessThanOrEqual(28.05);
    }
  });

  it("alternates long-reach big droplets with short small ones, and spreads the start times", () => {
    const drops = burstDroplets(6, 20);
    expect(drops.map((d) => d.size)).toEqual([6, 4, 6, 4, 6, 4]);
    expect(Math.hypot(drops[1].x, drops[1].y)).toBeCloseTo(13, 0);
    expect(new Set(drops.map((d) => d.delay)).size).toBeGreaterThan(1);
    expect(Math.max(...drops.map((d) => d.delay))).toBeLessThanOrEqual(50);
  });
});
