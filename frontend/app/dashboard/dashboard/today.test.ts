// Run: npx vitest run app/dashboard/dashboard/today.test.ts
import { describe, expect, it } from "vitest";
import { buildTodayItems, daysAgo, summarizeCycle, summarizeSignal, upcomingVisits } from "./today";
import type { TrackerEntry } from "./types";

const now = new Date(2026, 9, 6, 9, 0); // 6 Oct 2026, local time
const day = (ago: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - ago);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const sleep = (ago: number, duration: number): TrackerEntry => ({ id: `s${ago}`, date: day(ago), duration });

describe("today derivations", () => {
  it("counts calendar days for date-only and future values", () => {
    expect(daysAgo(day(0), now)).toBe(0);
    expect(daysAgo(day(3), now)).toBe(3);
    expect(daysAgo(day(-2), now)).toBe(-2);
    expect(Number.isNaN(daysAgo("not a date", now))).toBe(true);
  });

  it("flags a change only with enough days on both sides", () => {
    const usual = [8, 9, 10, 11, 12, 13].map((ago) => sleep(ago, 7.5));
    const short = [0, 1, 2].map((ago) => sleep(ago, 5.5));
    const s = summarizeSignal("sleep", [...short, ...usual], now);
    expect(s.value).toBe("5.5 h");
    expect(s.change?.direction).toBe("down");
    expect(s.change?.confidence).toBe("low");
    expect(s.detail).toBe("Below your usual 7.5 h");

    const thin = summarizeSignal("sleep", [...short, sleep(9, 7.5)], now);
    expect(thin.change).toBeUndefined();
    expect(thin.detail).toBe("Average of 3 logged nights");
  });

  it("shows gaps honestly and never invents values", () => {
    const empty = summarizeSignal("hydration", [], now);
    expect(empty.value).toBeUndefined();
    expect(empty.logged).toBe(false);
    expect(empty.bars).toEqual([0, 0, 0, 0, 0, 0, 0]);

    const items = buildTodayItems([empty, summarizeSignal("sleep", [], now)], null, []);
    expect(items.map((i) => i.id)).toEqual(["gap-hydration", "gap-sleep"]);
    expect(items[0].primary).toBe("add-water");
  });

  it("predicts the next period only from the backend summary", () => {
    const cycle = summarizeCycle(
      { entries: [{ id: "c1", date: day(26), phase: "period" }], summary: { period_start_count: 3, last_period: day(26), average_cycle_length: 28, next_predicted: day(-2) } },
      now,
    );
    expect(cycle.day).toBe(27);
    expect(cycle.daysUntil).toBe(2);
    expect(buildTodayItems([], cycle, [])[0].id).toBe("cycle-next");

    const none = summarizeCycle({ entries: [], summary: { period_start_count: 0 } }, now);
    expect(none.logged).toBe(false);
    expect(none.value).toBeUndefined();
  });

  it("lists upcoming visits soonest first", () => {
    const visits = upcomingVisits([{ id: "a", date: day(-10) }, { id: "b", date: day(5) }, { id: "c", date: day(-1) }], now);
    expect(visits.map((v) => v.id)).toEqual(["c", "a"]);
  });
});
