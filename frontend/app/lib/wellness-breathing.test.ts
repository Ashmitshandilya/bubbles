import { describe, expect, it } from "vitest";
import { cycleSeconds, patternSentence, phaseAt, phasesOf } from "./wellness-breathing";

const box = phasesOf({ inhale: 4, hold: 4, exhale: 4, hold_empty: 4 });

describe("phasesOf", () => {
  it("keeps the breathing order and skips missing parts", () => {
    expect(box.map((p) => p.name)).toEqual(["inhale", "hold", "exhale", "hold_empty"]);
    expect(phasesOf({ inhale: 4, exhale: 6 }).map((p) => p.name)).toEqual(["inhale", "exhale"]);
    expect(phasesOf({ inhale: 0, exhale: -1 })).toEqual([]);
    expect(phasesOf(null)).toEqual([]);
  });
  it("totals a cycle", () => {
    expect(cycleSeconds(box)).toBe(16);
    expect(cycleSeconds(phasesOf({ inhale: 4, hold: 7, exhale: 8 }))).toBe(19);
  });
  it("reads as a sentence for text-only mode", () => {
    expect(patternSentence(phasesOf({ inhale: 4, exhale: 6 }))).toBe("breathe in for 4, then breathe out for 6");
  });
});

describe("phaseAt", () => {
  it("starts breathing in with a full countdown", () => {
    const s = phaseAt(box, 0)!;
    expect(s.phase.name).toBe("inhale");
    expect(s.secondsLeft).toBe(4);
    expect(s.fill).toBe(0);
  });
  it("fills during inhale, stays full on hold, empties on exhale", () => {
    expect(phaseAt(box, 2)!.fill).toBeCloseTo(0.5);
    expect(phaseAt(box, 5)).toMatchObject({ phase: { name: "hold" }, fill: 1 });
    expect(phaseAt(box, 10)!.fill).toBeCloseTo(0.5);
    expect(phaseAt(box, 13)).toMatchObject({ phase: { name: "hold_empty" }, fill: 0 });
  });
  it("counts whole seconds down to 1, never 0", () => {
    expect(phaseAt(box, 3.9)!.secondsLeft).toBe(1);
    expect(phaseAt(box, 4)!.secondsLeft).toBe(4);
  });
  it("wraps into later cycles", () => {
    const s = phaseAt(box, 16 + 1)!;
    expect(s.cycle).toBe(1);
    expect(s.phase.name).toBe("inhale");
  });
  it("is null with no phases and tolerates bad time", () => {
    expect(phaseAt([], 3)).toBeNull();
    expect(phaseAt(box, Number.NaN)!.index).toBe(0);
    expect(phaseAt(box, -5)!.index).toBe(0);
  });
});
