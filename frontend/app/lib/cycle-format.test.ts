import { describe, expect, it } from "vitest";
import {
  cToF, confidenceCopy, dayAriaLabel, formatRange, formatTemp, fToC, lengthsSentence, nextPeriodLines, parseTemp,
  pregnancyProgress, relativeDays, summarizeLog, validateBbt,
} from "./cycle-format";
import { EMPTY_DAY_LOG, type CalendarDay, type NextPeriod } from "./cycle-types";

const day = (over: Partial<CalendarDay> = {}): CalendarDay => ({
  date: "2026-10-12", cycle_day: null, phase: null, period: null, fertile: null, ovulation: null, period_start: false,
  flow: null, has_log: false, symptom_count: 0, pain_level: null, is_today: false, is_future: false, ...over,
});
const np = (over: Partial<NextPeriod> = {}): NextPeriod => ({
  date: "2026-11-02", earliest: "2026-10-30", latest: "2026-11-05", in_days: 5, status: "upcoming", late_by_days: null, ...over,
});

describe("ranges and relative wording", () => {
  it("formats a range or a single day", () => {
    expect(formatRange("2026-10-12", "2026-10-15", "en-GB")).toBe("12 Oct to 15 Oct");
    expect(formatRange("2026-10-12", "2026-10-12", "en-GB")).toBe("12 Oct");
  });

  it("says when", () => {
    expect(relativeDays(0)).toBe("today");
    expect(relativeDays(1)).toBe("tomorrow");
    expect(relativeDays(4)).toBe("in 4 days");
    expect(relativeDays(-1)).toBe("yesterday");
    expect(relativeDays(-3)).toBe("3 days ago");
  });

  it("describes the next period kindly and hedged", () => {
    const upcoming = nextPeriodLines(np(), "en-GB");
    expect(upcoming.range).toBe("Between 30 Oct and 5 Nov");
    expect(upcoming.likely).toBe("most likely 2 Nov");
    expect(upcoming.relative).toBe("Expected in 5 days");
    expect(nextPeriodLines(np({ status: "due", in_days: 0 })).relative).toBe("Due around now");
    const late = nextPeriodLines(np({ status: "late", in_days: -3, late_by_days: 3 })).relative;
    expect(late).toContain("3 days later than the estimate");
    expect(nextPeriodLines(np({ status: "late", in_days: -1, late_by_days: 1 })).relative).toContain("1 day later");
  });

  it("gives confidence a plain-language note", () => {
    expect(confidenceCopy("learning").label).toBe("Still learning");
    expect(confidenceCopy("high").note).toContain("can still be wrong");
  });

  it("shows pregnancy as completed weeks plus days", () => {
    expect(pregnancyProgress({ week: 12, day: 3 })).toBe("12 weeks + 3 days");
    expect(pregnancyProgress({ week: 12, day: 1 })).toBe("12 weeks + 1 day");
    expect(pregnancyProgress({ week: 8, day: 0 })).toBe("8 weeks");
  });
});

describe("day aria labels", () => {
  it("spells out every marker so colour is never the only cue", () => {
    const label = dayAriaLabel("2026-10-12", day({ cycle_day: 9, period: "predicted", fertile: "possible" }), "en-GB");
    expect(label).toBe("12 October, day 9, period predicted, fertile window possible");
  });

  it("handles logged, today, ovulation and pain", () => {
    const label = dayAriaLabel("2026-10-12", day({ is_today: true, period: "logged", period_start: true, ovulation: "confirmed", has_log: true, pain_level: 4 }), "en-GB");
    expect(label).toContain("today");
    expect(label).toContain("first day of period logged");
    expect(label).toContain("ovulation confirmed");
    expect(label).toContain("pain 4 of 10");
  });

  it("labels a day with no data", () => {
    expect(dayAriaLabel("2026-10-12", undefined, "en-GB")).toBe("12 October");
  });
});

describe("temperature", () => {
  it("converts both ways", () => {
    expect(cToF(36.6)).toBe(97.9);
    expect(fToC(98.6)).toBe(37);
    expect(cToF(34)).toBe(93.2);
  });

  it("parses decimals with a comma", () => {
    expect(parseTemp("36,55")).toBe(36.55);
    expect(parseTemp(" 36.5 ")).toBe(36.5);
    expect(parseTemp("abc")).toBeNull();
    expect(parseTemp("")).toBeNull();
  });

  it("validates 34 to 40 C in either unit", () => {
    expect(validateBbt("", "c")).toBeNull();
    expect(validateBbt("36.5", "c")).toBeNull();
    expect(validateBbt("33.9", "c")).toContain("between 34 and 40");
    expect(validateBbt("40.1", "c")).not.toBeNull();
    expect(validateBbt("97.7", "f")).toBeNull();
    expect(validateBbt("93.0", "f")).toContain("93.2");
    expect(validateBbt("hot", "c")).toContain("number");
  });

  it("formats for display", () => {
    expect(formatTemp(36.5, "c")).toBe("36.5 °C");
    expect(formatTemp(36.5, "f")).toBe("97.7 °F");
    expect(formatTemp(null, "c")).toBe("—");
  });
});

describe("summaries", () => {
  it("summarises a log without inventing anything", () => {
    expect(summarizeLog(null)).toEqual([]);
    expect(summarizeLog(EMPTY_DAY_LOG)).toEqual([]);
    const lines = summarizeLog({ ...EMPTY_DAY_LOG, flow: "medium", pain_level: 3, factors: ["a", "b"], notes: "hi", period_start: true });
    expect(lines).toEqual(["Period started", "Flow: medium", "Pain 3 of 10", "2 symptoms or feelings noted", "Note added"]);
  });

  it("writes a text alternative for the length chart", () => {
    expect(lengthsSentence([])).toBe("No completed cycles yet.");
    expect(lengthsSentence([28, 30, 26])).toContain("Shortest 26, longest 30");
    expect(lengthsSentence([28])).toContain("1 cycle lasted");
  });
});
