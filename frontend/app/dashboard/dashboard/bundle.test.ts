import { describe, expect, it } from "vitest";
import { bubbleSignals, readBundle } from "./bundle";
import type { SignalSummary } from "./today";

const summary = (over: Partial<SignalSummary>): SignalSummary => ({ slug: "sleep", logged: true, weekDays: 3, weekCount: 3, detail: "", bars: [0, 0.5, 0, 1, 0, 0, 0], value: "6h", ...over });

describe("readBundle", () => {
  it("turns a null part into a gap, not a guess", () => {
    const b = readBundle({ lede: { kind: "warm", text: "Hello." }, trackers: { sleep: { entries: [] }, mood: null }, visits: null, brief: null, nudges: null });
    expect(b.lede?.text).toBe("Hello.");
    expect(b.trackers.sleep).toBeDefined();
    expect(b.trackers.mood).toBeUndefined();
    expect(b.visits).toBeUndefined();
    expect(b.brief).toBeUndefined();
    expect(b.nudges).toEqual([]);
  });

  it("survives junk", () => {
    expect(readBundle(null).trackers).toEqual({});
    expect(readBundle("x").lede).toBeUndefined();
    expect(readBundle({ lede: { text: "" } }).lede).toBeUndefined();
  });

  it("reads the profile in either shape", () => {
    expect(readBundle({ profile: { profile: { display_name: "Riya" } } }).profile?.display_name).toBe("Riya");
  });
});

describe("bubbleSignals", () => {
  it("gives every daily signal a bubble and marks unlogged ones empty", () => {
    const out = bubbleSignals([summary({}), summary({ slug: "mood", value: undefined, bars: [0, 0, 0, 0, 0, 0, 0] })]);
    expect(out.map((o) => o.id)).toEqual(["sleep", "mood", "hydration", "activity"]);
    expect(out[0].amount).toBeCloseTo(0.75);
    expect(out[1].amount).toBeNull();
    expect(out[2].amount).toBeNull();
  });

  it("carries the trend only when there is data", () => {
    const [sleep, mood] = bubbleSignals([summary({ trend: "down" }), summary({ slug: "mood", value: undefined, bars: [0, 0, 0, 0, 0, 0, 0], trend: "up" })]);
    expect(sleep.trend).toBeLessThan(0);
    expect(mood.trend).toBeNull();
  });
});
