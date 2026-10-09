import { describe, expect, it } from "vitest";
import { calendarPath, dayPath, periodBody, reportPath, withToday } from "./cycle-api";

describe("cycle api paths", () => {
  it("adds the local day to every request", () => {
    expect(withToday("/cycle/overview", "2026-10-08")).toBe("/cycle/overview?today=2026-10-08");
    expect(withToday("/cycle/calendar?month=2026-10", "2026-10-08")).toBe("/cycle/calendar?month=2026-10&today=2026-10-08");
  });

  it("builds calendar, day and report paths", () => {
    expect(calendarPath({ month: "2026-10" }, "2026-10-08")).toBe("/cycle/calendar?month=2026-10&today=2026-10-08");
    expect(calendarPath({ year: 2026 }, "2026-10-08")).toBe("/cycle/calendar?year=2026&today=2026-10-08");
    expect(dayPath("2026-10-05", "2026-10-08")).toBe("/cycle/day/2026-10-05?today=2026-10-08");
    expect(reportPath(6, false, "2026-10-08")).toBe("/cycle/report?months=6&include_notes=false&today=2026-10-08");
    expect(reportPath(12, true, "2026-10-08")).toContain("include_notes=true");
  });

  it("sends a date only when it is not today", () => {
    expect(periodBody(null, "2026-10-08")).toEqual({ today: "2026-10-08" });
    expect(periodBody("2026-10-08", "2026-10-08")).toEqual({ today: "2026-10-08" });
    expect(periodBody("2026-10-01", "2026-10-08")).toEqual({ date: "2026-10-01", today: "2026-10-08" });
  });
});
