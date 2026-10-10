import { describe, expect, it } from "vitest";
import { buildPulse, lastLoggedText, rollupToday, weekText } from "./track-pulse";

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
