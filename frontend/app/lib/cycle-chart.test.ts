import { describe, expect, it } from "vitest";
import { lengthChart } from "./cycle-chart";

describe("lengthChart", () => {
  it("draws no bars for no data but still shades the normal band", () => {
    const g = lengthChart([]);
    expect(g.bars).toEqual([]);
    expect(g.band.height).toBeGreaterThan(0);
  });

  it("keeps the newest twelve bars, in order, inside the plot", () => {
    const g = lengthChart(Array.from({ length: 15 }, (_, i) => 24 + i));
    expect(g.bars).toHaveLength(12);
    expect(g.bars[0].value).toBe(27);
    expect(g.bars[11].value).toBe(38);
    for (const bar of g.bars) {
      expect(bar.x).toBeGreaterThanOrEqual(g.left);
      expect(bar.x + bar.width).toBeLessThanOrEqual(g.right);
      expect(bar.y + bar.height).toBeCloseTo(g.baseline, 5);
    }
  });

  it("makes longer cycles taller and flags those outside 21 to 35", () => {
    const g = lengthChart([20, 28, 40]);
    expect(g.bars[1].height).toBeGreaterThan(g.bars[0].height);
    expect(g.bars[2].height).toBeGreaterThan(g.bars[1].height);
    expect(g.bars.map((b) => b.outside)).toEqual([true, false, true]);
  });

  it("places the band between 35 (top) and 21 (bottom)", () => {
    const g = lengthChart([28, 29]);
    const t35 = g.ticks.find((t) => t.value === 35);
    const t20 = g.ticks.find((t) => t.value === 20);
    expect(g.band.y).toBeLessThan(g.band.y + g.band.height);
    if (t35 && t20) {
      expect(t35.y).toBeCloseTo(g.band.y, 5);
      expect(t20.y).toBeGreaterThan(g.band.y + g.band.height - 0.001);
    }
    expect(g.yMax).toBeGreaterThanOrEqual(40);
  });

  it("widens the axis for extreme lengths", () => {
    const g = lengthChart([60, 18]);
    expect(g.yMax).toBeGreaterThanOrEqual(63);
    expect(g.yMin).toBeLessThanOrEqual(15);
  });
});
