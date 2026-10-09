import { describe, expect, it } from "vitest";
import { markersFor, monthSummary, primaryMarker } from "./cycle-markers";
import type { CalendarDay } from "./cycle-types";

const day = (over: Partial<CalendarDay> = {}): CalendarDay => ({
  date: "2026-10-12", cycle_day: null, phase: null, period: null, fertile: null, ovulation: null, period_start: false,
  flow: null, has_log: false, symptom_count: 0, pain_level: null, is_today: false, is_future: false, ...over,
});

describe("calendar markers", () => {
  it("gives a plain day no markers", () => {
    expect(markersFor(day())).toEqual([]);
    expect(markersFor(undefined)).toEqual([]);
    expect(primaryMarker(day())).toBeNull();
  });

  it("maps every state to its own shape kind", () => {
    expect(markersFor(day({ period: "logged", has_log: true }))).toEqual(["period-logged", "log"]);
    expect(markersFor(day({ period: "predicted" }))).toEqual(["period-predicted"]);
    expect(markersFor(day({ period: "possible" }))).toEqual(["period-possible"]);
    expect(markersFor(day({ fertile: "possible", ovulation: "confirmed" }))).toEqual(["ovulation-confirmed", "fertile-possible"]);
  });

  it("picks one marker for the compact year view", () => {
    expect(primaryMarker(day({ period: "predicted", fertile: "predicted" }))).toBe("period-predicted");
    expect(primaryMarker(day({ period: "logged", has_log: true }))).toBe("period-logged");
    expect(primaryMarker(day({ has_log: true }))).toBe("log");
  });

  it("summarises a month in words", () => {
    expect(monthSummary([])).toBe("nothing marked");
    const text = monthSummary([day({ period: "logged" }), day({ period: "logged" }), day({ period: "predicted" }), day({ fertile: "possible" })]);
    expect(text).toBe("2 period days logged, 1 predicted, 1 fertile-window day");
  });
});
