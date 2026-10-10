import { describe, expect, it } from "vitest";
import { cycleDayLine, nextPeriodUncertainty, phaseSteps, phaseSymptomHint, symptomsInPhase } from "./cycle-today";
import type { SymptomByPhase } from "./cycle-types";

const sym = (label: string, total_days: number, most_common_phase: SymptomByPhase["most_common_phase"]): SymptomByPhase => ({
  id: label, label, total_days, per_phase: [], most_common_phase,
});

describe("cycleDayLine", () => {
  it("states the day against the user's own length", () => {
    expect(cycleDayLine(14, 28.2)).toBe("Day 14 of about 28");
  });
  it("is honest when the length is not learned yet", () => {
    expect(cycleDayLine(5, null)).toContain("still learning your usual length");
  });
  it("does not pretend a long cycle is normal progress", () => {
    expect(cycleDayLine(33, 28)).toBe("Day 33, past your usual length of about 28 days");
  });
});

describe("nextPeriodUncertainty", () => {
  const w = { earliest: "2026-10-30", latest: "2026-11-05" };
  it("counts the window inclusively and hedges", () => {
    const text = nextPeriodUncertainty(w, "low");
    expect(text).toContain("A window of about 7 days");
    expect(text).toContain("cycles vary");
    expect(text).toContain("can fall outside");
  });
  it("handles a one-day window and the learning state", () => {
    const text = nextPeriodUncertainty({ earliest: "2026-10-30", latest: "2026-10-30" }, "learning");
    expect(text).toContain("A single-day window");
    expect(text).toContain("rough guess");
  });
});

describe("phaseSteps", () => {
  it("marks only the current phase", () => {
    const steps = phaseSteps("luteal", false);
    expect(steps.map((s) => s.id)).toEqual(["menstrual", "follicular", "ovulatory", "luteal"]);
    expect(steps.filter((s) => s.here).map((s) => s.id)).toEqual(["luteal"]);
  });
  it("drops the ovulatory step when fertility is hidden", () => {
    expect(phaseSteps("follicular", true).map((s) => s.id)).not.toContain("ovulatory");
  });
});

describe("symptoms by phase", () => {
  const all = [sym("Cramps", 9, "menstrual"), sym("Headache", 4, "luteal"), sym("Bloating", 7, "luteal"), sym("Fatigue", 2, null)];
  it("lists what clusters in the current phase, busiest first", () => {
    expect(symptomsInPhase(all, "luteal")).toEqual(["Bloating", "Headache"]);
  });
  it("phrases a hint from the user's own logs", () => {
    expect(phaseSymptomHint(all, "luteal")).toBe("You are in the luteal phase. In your logs, bloating and headache show up most often in this phase.");
  });
  it("says so when nothing clusters, without calling it fine", () => {
    const hint = phaseSymptomHint(all, "ovulatory") ?? "";
    expect(hint).toContain("Nothing in your logs points to this phase yet");
    expect(hint).toContain("may only mean it has not been logged");
  });
  it("gives no hint without a known phase", () => {
    expect(phaseSymptomHint(all, null)).toBeNull();
  });
});
