import { describe, expect, it } from "vitest";
import {
  addDays, addMonths, buildMonthGrid, daysInMonth, defaultWeekStart, diffDays, fromDayNumber, dayNumber, isISODate,
  monthLabel, monthOf, parseISO, todayISO, toISO, weekdayIndex, weekdayLabels, yearMonths,
} from "./cycle-calendar";

describe("iso helpers", () => {
  it("validates real calendar days only", () => {
    expect(isISODate("2026-10-08")).toBe(true);
    expect(isISODate("2026-02-30")).toBe(false);
    expect(isISODate("2024-02-29")).toBe(true);
    expect(isISODate("2026-13-01")).toBe(false);
    expect(isISODate("2026-1-1")).toBe(false);
    expect(parseISO("2026-10-08")).toEqual({ y: 2026, m: 10, d: 8 });
  });

  it("does arithmetic across month, year and leap boundaries", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2024-02-28", 2)).toBe("2024-03-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(diffDays("2026-10-01", "2026-10-29")).toBe(28);
    expect(diffDays("2026-10-29", "2026-10-01")).toBe(-28);
    expect(fromDayNumber(dayNumber("2026-10-08"))).toBe("2026-10-08");
    expect(daysInMonth(2026, 2)).toBe(28);
    expect(daysInMonth(2028, 2)).toBe(29);
  });

  it("is not moved by the clock time of day", () => {
    expect(todayISO(new Date(2026, 9, 8, 23, 59))).toBe("2026-10-08");
    expect(todayISO(new Date(2026, 9, 8, 0, 1))).toBe("2026-10-08");
    expect(toISO(2026, 1, 5)).toBe("2026-01-05");
  });

  it("knows weekdays and months", () => {
    expect(weekdayIndex("2023-01-01")).toBe(0);
    expect(weekdayIndex("2026-10-08")).toBe(4); // Thursday
    expect(monthOf("2026-10-08")).toBe("2026-10");
    expect(addMonths("2026-12", 1)).toBe("2027-01");
    expect(addMonths("2026-01", -1)).toBe("2025-12");
    expect(addMonths("2026-05", 13)).toBe("2027-06");
    expect(yearMonths(2026)).toHaveLength(12);
    expect(yearMonths(2026)[0]).toBe("2026-01");
  });
});

describe("month grid", () => {
  it("pads to whole weeks starting Monday", () => {
    const grid = buildMonthGrid("2026-10", 1); // 1 Oct 2026 is a Thursday
    expect(grid.every((row) => row.length === 7)).toBe(true);
    expect(grid[0][0].iso).toBe("2026-09-28");
    expect(grid[0][0].inMonth).toBe(false);
    expect(grid[0][3].iso).toBe("2026-10-01");
    expect(grid[0][3].inMonth).toBe(true);
    expect(grid.flat().filter((c) => c.inMonth)).toHaveLength(31);
    expect(grid.length).toBe(5);
  });

  it("starts on Sunday when asked and can need six rows", () => {
    const grid = buildMonthGrid("2026-10", 0);
    expect(grid[0][0].iso).toBe("2026-09-27");
    expect(grid[0][4].iso).toBe("2026-10-01");
    expect(buildMonthGrid("2026-02", 0)).toHaveLength(4); // 1 Feb 2026 is a Sunday: exactly four weeks
    expect(buildMonthGrid("2026-11", 0)).toHaveLength(5);
    expect(buildMonthGrid("2027-05", 0).length).toBe(6);
  });

  it("returns nothing for a bad month", () => {
    expect(buildMonthGrid("nope", 1)).toEqual([]);
  });
});

describe("labels and locale", () => {
  it("lists weekdays in week order", () => {
    expect(weekdayLabels(1, "en-GB").map((w) => w.long)[0]).toBe("Monday");
    expect(weekdayLabels(0, "en-US").map((w) => w.long)[0]).toBe("Sunday");
    expect(weekdayLabels(1, "en-GB")).toHaveLength(7);
  });

  it("labels months", () => {
    expect(monthLabel("2026-10", "en-GB")).toBe("October 2026");
    expect(monthLabel("2026-10", "en-GB", false)).toBe("October");
  });

  it("picks the week start from the locale", () => {
    expect(defaultWeekStart("en-US")).toBe(0);
    expect(defaultWeekStart("en-GB")).toBe(1);
    expect(defaultWeekStart("de-DE")).toBe(1);
  });
});
