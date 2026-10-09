import { describe, expect, it } from "vitest";
import {
  badgeText, beverageLabel, detailOf, exportFilename, loggedMessage, reminderHint, formatHours, formatMl, humanizeKey, isClock, plural, scoreWords, shortDay, timeAgo, tzLabel,
  tzOffsetMinutes, withQuery,
} from "./wellness-format";

describe("time zone offset", () => {
  const fake = (west: number) => ({ getTimezoneOffset: () => west }) as Date;
  it("is minutes EAST of UTC (the opposite sign of getTimezoneOffset)", () => {
    expect(tzOffsetMinutes(fake(-330))).toBe(330); // India
    expect(tzOffsetMinutes(fake(300))).toBe(-300); // New York in winter
  });
  it("never returns -0 and stays inside the server's accepted range", () => {
    expect(Object.is(tzOffsetMinutes(fake(0)), 0)).toBe(true);
    expect(tzOffsetMinutes(fake(-5000))).toBe(840);
    expect(tzOffsetMinutes(fake(5000))).toBe(-840);
  });
  it("labels the zone", () => {
    expect(tzLabel(0)).toBe("UTC");
    expect(tzLabel(330)).toBe("UTC+05:30");
    expect(tzLabel(-240)).toBe("UTC-04:00");
  });
});

describe("withQuery", () => {
  it("adds and skips empty values", () => {
    expect(withQuery("/a", { x: 1, y: null, z: undefined, w: "" })).toBe("/a?x=1");
    expect(withQuery("/a?b=1", { tz_offset_minutes: -300 })).toBe("/a?b=1&tz_offset_minutes=-300");
    expect(withQuery("/a", {})).toBe("/a");
  });
});

describe("export filename", () => {
  it("uses the local date", () => {
    expect(exportFilename(new Date(2026, 9, 8))).toBe("bubbles-my-data-2026-10-08.json");
    expect(exportFilename(new Date(2026, 0, 3))).toBe("bubbles-my-data-2026-01-03.json");
  });
});

describe("number words", () => {
  it("formats hours", () => {
    expect(formatHours(7.5)).toBe("7 h 30 min");
    expect(formatHours(8)).toBe("8 h");
    expect(formatHours(0.75)).toBe("45 min");
    expect(formatHours(null)).toBe("—");
    expect(formatHours(Number.NaN)).toBe("—");
  });
  it("formats millilitres", () => {
    expect(formatMl(250)).toBe("250 ml");
    expect(formatMl(1500)).toBe("1.5 L");
    expect(formatMl(2000)).toBe("2 L");
    expect(formatMl(null)).toBe("—");
  });
  it("pluralises and humanises", () => {
    expect(plural(1, "night")).toBe("1 night");
    expect(plural(3, "night")).toBe("3 nights");
    expect(humanizeKey("late_meal")).toBe("Late meal");
  });
});

describe("clock and score words", () => {
  it("accepts HH:MM only", () => {
    expect(isClock("07:30")).toBe(true);
    expect(isClock("7:30")).toBe(false);
    expect(isClock("24:00")).toBe(false);
    expect(isClock(null)).toBe(false);
  });
  it("describes a sleep score in kind words", () => {
    expect(scoreWords(90)).toBe("Restful");
    expect(scoreWords(70)).toBe("Good");
    expect(scoreWords(50)).toBe("Okay");
    expect(scoreWords(10)).toBe("A lighter stretch");
  });
});

describe("notifications", () => {
  it("caps the badge", () => {
    expect(badgeText(0)).toBe("");
    expect(badgeText(3)).toBe("3");
    expect(badgeText(25)).toBe("9+");
    expect(badgeText(Number.NaN)).toBe("");
  });
  it("says how long ago", () => {
    const now = new Date("2026-10-08T12:00:00Z");
    expect(timeAgo("2026-10-08T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-10-08T11:55:00Z", now)).toBe("5 min ago");
    expect(timeAgo("2026-10-08T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-10-07T09:00:00Z", now)).toBe("yesterday");
    expect(timeAgo("not a date", now)).toBe("");
  });
});

describe("server messages", () => {
  it("shows the server's own sentence for client errors", () => {
    expect(detailOf(422, { detail: "duration must be a number" }, "fallback")).toBe("duration must be a number");
    expect(detailOf(404, { detail: "Schedule not found" }, "fallback")).toBe("Schedule not found");
  });
  it("joins validation lists and hides server internals", () => {
    expect(detailOf(422, { detail: [{ msg: "a" }, { msg: "b" }] }, "x")).toBe("a; b");
    expect(detailOf(500, { detail: "Traceback ..." }, "Try again")).toBe("Try again");
    expect(detailOf(401, { detail: "bad token" }, "Sign in")).toBe("Sign in");
    expect(detailOf(422, null, "fallback")).toBe("fallback");
  });
});

describe("shortDay", () => {
  it("does not shift across time zones", () => {
    expect(shortDay("2026-10-05")).toMatch(/5/);
    expect(shortDay("bad")).toBe("bad");
  });
});

describe("hydration wording", () => {
  const base = { enabled: true, next: null, due_now: null, reason: null };
  it("hints at the next reminder, or stays quiet when there is no target", () => {
    expect(reminderHint({ ...base, next: "14:00" })).toBe("Next gentle reminder around 14:00.");
    expect(reminderHint({ ...base, due_now: "12:00" })).toMatch(/sip would be nice/);
    expect(reminderHint(base)).toMatch(/keeping pace/);
    expect(reminderHint({ ...base, enabled: false, reason: "no_target" })).toBe("");
    expect(reminderHint({ ...base, enabled: false, reason: "goal_reached" })).toMatch(/at your target/);
    expect(reminderHint(null)).toBe("");
  });
  it("explains what a drink counts for without judging", () => {
    expect(loggedMessage(250, "water", 250)).toBe("Added 250 ml of water.");
    expect(loggedMessage(500, "coffee", 400)).toBe("Added 500 ml of coffee, which counts as about 400 ml toward your target.");
    expect(loggedMessage(330, "alcohol", 0)).toBe("Logged 330 ml of alcohol. It doesn't count toward your drinks target.");
  });
  it("labels beverages", () => {
    expect(beverageLabel("coconut_water")).toBe("Coconut water");
    expect(beverageLabel("tea")).toBe("Tea");
  });
});
