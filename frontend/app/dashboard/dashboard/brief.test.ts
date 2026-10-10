// Run: npx vitest run app/dashboard/dashboard/brief.test.ts
import { describe, expect, it } from "vitest";
import { TREND_WORDS, confidenceDots, sparkPath, sparkPoints } from "./brief";
import { buildTodayItems, summarizeSignal } from "./today";
import type { TrackerEntry } from "./types";

const now = new Date(2026, 9, 6, 9, 0);
const day = (ago: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - ago);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const sleep = (ago: number, duration: number): TrackerEntry => ({ id: `s${ago}`, date: day(ago), duration });
const usual = [8, 9, 10, 11, 12, 13].map((ago) => sleep(ago, 7.5));

describe("trend", () => {
  it("is down/up only for a 15% or larger move against the user's own weeks", () => {
    const short = [0, 1, 2].map((ago) => sleep(ago, 5.5));
    const s = summarizeSignal("sleep", [...short, ...usual], now);
    expect(s.trend).toBe("down");
    const item = buildTodayItems([s], null, [])[0];
    expect(item.trend).toBe("down");
    expect(TREND_WORDS[item.trend!]).toBe("Below your usual");
  });

  it("is steady inside 15%", () => {
    const same = [0, 1, 2].map((ago) => sleep(ago, 7.4));
    expect(summarizeSignal("sleep", [...same, ...usual], now).trend).toBe("steady");
  });

  it("is undefined, not steady, when there are too few logged days to compare", () => {
    const thin = summarizeSignal("sleep", [0, 1, 2].map((ago) => sleep(ago, 5.5)), now);
    expect(thin.trend).toBeUndefined();
    expect(summarizeSignal("sleep", [], now).trend).toBeUndefined();
  });
});

describe("gap items deep-link to the log sheet", () => {
  it("uses ?log=1 for trackers that support it", () => {
    const items = buildTodayItems([summarizeSignal("hydration", [], now), summarizeSignal("sleep", [], now)], null, []);
    const sleepItem = items.find((i) => i.id === "gap-sleep")!;
    expect(sleepItem.primary).toEqual({ label: "Log sleep", href: "/sleep?log=1" });
    expect(items.find((i) => i.id === "gap-hydration")!.secondary?.href).toBe("/hydration?log=1");
  });
});

describe("evidence chip", () => {
  it("fills dots by confidence and none for a data gap", () => {
    expect(["high", "medium", "low", "gap"].map((k) => confidenceDots(k as never))).toEqual([3, 2, 1, 0]);
  });
});

describe("sparkline", () => {
  it("breaks the line at unlogged days instead of dropping to zero", () => {
    const points = sparkPoints([0.5, 1, 0, 0, 0.25, 0.5, 1]);
    expect(points[2]).toBeNull();
    expect(points[3]).toBeNull();
    expect(points[1]!.y).toBeLessThan(points[0]!.y); // taller bar is higher up
    const path = sparkPath(points);
    expect(path.match(/M/g)).toHaveLength(2);
    expect(path.match(/L/g)).toHaveLength(3);
  });

  it("returns nothing to draw when nothing is logged", () => {
    expect(sparkPath(sparkPoints([0, 0, 0, 0, 0, 0, 0]))).toBe("");
  });

  it("keeps every point inside the box", () => {
    for (const p of sparkPoints([1, 0.01, 0.5], 64, 24, 3)) {
      expect(p!.x).toBeGreaterThanOrEqual(3);
      expect(p!.x).toBeLessThanOrEqual(61);
      expect(p!.y).toBeGreaterThanOrEqual(3);
      expect(p!.y).toBeLessThanOrEqual(21);
    }
  });
});
