import { describe, expect, it } from "vitest";
import { buildPulse, lastLoggedText, rollupToday, weekText, checkIns, streakText } from "./track-pulse";

const NOW = new Date(2026, 9, 10, 15, 0); // 10 Oct 2026, local

describe("buildPulse", () => {
  it("counts entries per day with today on the right", () => {
    const p = buildPulse([{ date: "2026-10-10" }, { date: "2026-10-10" }, { date: "2026-10-08" }, { date: "2026-10-04" }], NOW);
    expect(p.week).toEqual([1, 0, 0, 0, 1, 0, 2]);
    expect(p.daysLogged).toBe(3);
    expect(p.lastAgo).toBe(0);
  });

  it("ignores future and unreadable dates", () => {
    const p = buildPulse([{ date: "2026-10-12" }, { date: "nope" }, { date: "" }], NOW);
    expect(p.lastAgo).toBeNull();
    expect(p.daysLogged).toBe(0);
  });

  it("keeps older entries for the last-logged hint but not the week", () => {
    const p = buildPulse([{ date: "2026-09-25" }], NOW);
    expect(p.week.every((n) => n === 0)).toBe(true);
    expect(p.lastAgo).toBe(15);
  });
});

describe("hint wording", () => {
  it("says when it was last logged", () => {
    expect(lastLoggedText(buildPulse([{ date: "2026-10-10" }], NOW))).toBe("Logged today");
    expect(lastLoggedText(buildPulse([{ date: "2026-10-09" }], NOW))).toBe("Last logged yesterday");
    expect(lastLoggedText(buildPulse([{ date: "2026-10-05" }], NOW))).toBe("Last logged 5 days ago");
  });

  it("shows an empty tracker as a gap, not as fine", () => {
    const empty = buildPulse([], NOW);
    expect(lastLoggedText(empty)).toBe("Nothing logged in the last 30 days");
    expect(weekText(empty)).toBe("No entries in the last 7 days");
  });

  it("summarises the week", () => {
    expect(weekText(buildPulse([{ date: "2026-10-10" }, { date: "2026-10-09" }], NOW))).toBe("Logged on 2 of the last 7 days");
  });
});

describe("rollupToday", () => {
  it("splits done, open and unknown", () => {
    const r = rollupToday([
      { label: "Sleep", pulse: buildPulse([{ date: "2026-10-10" }], NOW) },
      { label: "Mood", pulse: buildPulse([], NOW) },
      { label: "Water", pulse: null },
    ]);
    expect(r).toEqual({ checked: 2, done: ["Sleep"], open: ["Mood"], unknown: ["Water"] });
  });
});

describe("check-in days across trackers", () => {
  const now = new Date(2026, 9, 10, 12, 0, 0);
  const day = (ago: number) => ({ date: new Date(2026, 9, 10 - ago, 9, 0, 0).toISOString() });

  it("counts a day when any readable tracker has an entry", () => {
    const sleep = buildPulse([day(0), day(1)], now);
    const water = buildPulse([day(1), day(2), day(3)], now);
    const c = checkIns([sleep, water, null]);
    expect(c.streak).toBe(4);
    expect(c.readable).toBe(2);
    expect(c.recent).toHaveLength(14);
    expect(c.recentDays).toBe(4);
  });

  it("does not break the streak when today is still empty", () => {
    const c = checkIns([buildPulse([day(1), day(2), day(3)], now)]);
    expect(c.streak).toBe(3);
  });

  it("stops at the first missed day and never counts a gap as a day", () => {
    const c = checkIns([buildPulse([day(0), day(1), day(3), day(4)], now)]);
    expect(c.streak).toBe(2);
    expect(c.recent.slice(-5)).toEqual([true, true, false, true, true]);
  });

  it("says nothing when no tracker could be read and stays gentle otherwise", () => {
    expect(streakText(checkIns([null, null]))).toBe("");
    expect(streakText(checkIns([buildPulse([], now)]))).toBe("Every day is a fresh start. One entry is enough.");
    expect(streakText(checkIns([buildPulse([day(0)], now)]))).toMatch(/One more day/);
    expect(streakText(checkIns([buildPulse([day(0), day(1), day(2)], now)]))).toBe("3 days in a row with something logged.");
    expect(streakText(checkIns([buildPulse([day(0)], now)]))).not.toMatch(/—|missed|lost|broke/i);
  });

  it("ignores future dates and entries older than the window", () => {
    const c = checkIns([buildPulse([{ date: new Date(2026, 9, 12).toISOString() }, day(45)], now)]);
    expect(c.streak).toBe(0);
    expect(c.recentDays).toBe(0);
  });
});
