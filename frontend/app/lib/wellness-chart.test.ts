import { describe, expect, it } from "vitest";
import { barBoxes, gardenAlt, gardenStage, pixelSummary, pixelTable, ringDash, weekdayAverages } from "./wellness-chart";

describe("weekdayAverages", () => {
  const series = [
    { date: "2026-10-05", hours: 8 }, // Monday
    { date: "2026-10-12", hours: 6 }, // Monday
    { date: "2026-10-10", hours: 9 }, // Saturday (one night only)
    { date: "2026-10-11", hours: 7 }, // Sunday
    { date: "2026-10-04", hours: 8 }, // Sunday
  ];
  it("is Monday-first and averages per weekday", () => {
    const bars = weekdayAverages(series);
    expect(bars.map((b) => b.short)).toEqual(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]);
    expect(bars[0]).toMatchObject({ hours: 7, nights: 2 });
    expect(bars[6]).toMatchObject({ hours: 7.5, nights: 2 });
  });
  it("leaves a gap, not zero, when a weekday has too little data", () => {
    const bars = weekdayAverages(series);
    expect(bars[5].hours).toBeNull(); // Saturday has only one night
    expect(bars[1].hours).toBeNull();
    expect(bars[5].nights).toBe(1);
  });
  it("copes with no series", () => {
    expect(weekdayAverages(undefined).every((b) => b.hours === null)).toBe(true);
  });
});

describe("barBoxes", () => {
  it("scales to the largest value and skips nulls", () => {
    const boxes = barBoxes([4, null, 8], 300, 100);
    expect(boxes[1]).toBeNull();
    expect(boxes[2]?.height).toBe(100);
    expect(boxes[0]?.height).toBe(50);
    expect(boxes[0]?.y).toBe(50);
  });
  it("honours a fixed ceiling and a minimum visible height", () => {
    expect(barBoxes([0.01], 100, 100, 10)[0]?.height).toBe(2);
    expect(barBoxes([5], 100, 100, 10)[0]?.height).toBe(50);
  });
});

describe("ringDash", () => {
  it("clamps and splits the circumference", () => {
    const half = ringDash(50, 10);
    expect(half.dash).toBeCloseTo(Math.PI * 10, 5);
    expect(half.dash + half.gap).toBeCloseTo(half.circumference, 5);
    expect(ringDash(150, 10).dash).toBeCloseTo(ringDash(100, 10).circumference, 5);
    expect(ringDash(-5, 10).dash).toBe(0);
    expect(ringDash(Number.NaN, 10).dash).toBe(0);
  });
});

describe("pixelTable", () => {
  const days = [
    { date: "2026-01-05", mood: 8, level: 4, entries: 1 },
    { date: "2026-02-28", mood: 2, level: 1, entries: 2 },
  ];
  const table = pixelTable(days, 2026);
  it("is 31 days by 12 months", () => {
    expect(table.rows).toHaveLength(31);
    expect(table.rows.every((r) => r.length === 12)).toBe(true);
    expect(table.months).toHaveLength(12);
  });
  it("leaves days that do not exist empty", () => {
    expect(table.rows[29][1]).toBeNull(); // 30 February
    expect(table.rows[30][3]).toBeNull(); // 31 April
    expect(table.rows[30][0]).not.toBeNull(); // 31 January
  });
  it("gives every real cell a text label, never colour alone", () => {
    expect(table.rows[4][0]).toMatchObject({ date: "2026-01-05", level: 4, label: "5 January: Good" });
    expect(table.rows[27][1]).toMatchObject({ level: 1, label: "28 February: Rough" });
    expect(table.rows[0][5]).toMatchObject({ level: null, label: "1 June: no check-in" });
    const labels = table.rows.flat().filter(Boolean).map((c) => c!.label);
    expect(labels).toHaveLength(365);
    expect(labels.every((l) => l.length > 0)).toBe(true);
  });
  it("handles leap years", () => {
    expect(pixelTable([], 2028).rows[28][1]).not.toBeNull(); // 29 February 2028
    expect(pixelTable([], 2028).rows.flat().filter(Boolean)).toHaveLength(366);
  });
  it("summarises in words", () => {
    expect(pixelSummary(0, {}, 2026)).toBe("No check-ins in 2026 yet.");
    expect(pixelSummary(3, { "4": 2, "1": 1 }, 2026)).toBe("3 days checked in during 2026: 2 good, 1 rough.");
  });
});

describe("garden", () => {
  it("maps API level numbers to stages and clamps", () => {
    expect(gardenStage(0)).toBe("seed");
    expect(gardenStage(3)).toBe("blossom");
    expect(gardenStage(5)).toBe("oasis");
    expect(gardenStage(9)).toBe("oasis");
    expect(gardenStage(-2)).toBe("seed");
    expect(gardenStage(null)).toBe("seed");
  });
  it("only mentions the gauge when there is a goal", () => {
    expect(gardenAlt("pond", null)).not.toMatch(/percent/);
    expect(gardenAlt("pond", 40)).toMatch(/40 percent/);
  });
});
