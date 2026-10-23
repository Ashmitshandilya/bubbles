import { describe, expect, it } from "vitest";
import { EMPTY_R, MAX_R, MIN_R, describeBubble, layoutBubbles, type BubbleSignal } from "./bubbles-layout";

const sig = (over: Partial<BubbleSignal> = {}): BubbleSignal => ({ id: "sleep", label: "Sleep", domain: "sleep", amount: 0.5, trend: 0, ...over });

describe("layoutBubbles", () => {
  it("sizes by amount within bounds and clamps wild values", () => {
    const [low, high, wild] = layoutBubbles([sig({ amount: 0 }), sig({ amount: 1 }), sig({ amount: 9 })], 300);
    expect(low.r).toBe(MIN_R);
    expect(high.r).toBe(MAX_R);
    expect(wild.r).toBe(MAX_R);
  });

  it("shows no entries as an empty outlined bubble, never a small filled one", () => {
    const [gap] = layoutBubbles([sig({ amount: null, trend: 1 })], 100);
    expect(gap.empty).toBe(true);
    expect(gap.r).toBe(EMPTY_R);
    expect(gap.drift).toBe(0);
  });

  it("drifts up for a rising trend, down for a falling one", () => {
    const [up, down, steady] = layoutBubbles([sig({ trend: 1 }), sig({ trend: -1 }), sig({ trend: null })], 300);
    expect(up.drift).toBeLessThan(0);
    expect(down.drift).toBeGreaterThan(0);
    expect(steady.drift).toBe(0);
  });

  it("spreads centres evenly and handles empty input", () => {
    const placed = layoutBubbles([sig(), sig({ id: "b" }), sig({ id: "c" })], 300);
    expect(placed.map((p) => p.cx)).toEqual([50, 150, 250]);
    expect(layoutBubbles([], 300)).toEqual([]);
    expect(layoutBubbles([sig()], 0)).toEqual([]);
  });
});

describe("describeBubble", () => {
  it("speaks in words, with a gap said plainly", () => {
    expect(describeBubble(sig({ amount: null }))).toBe("Sleep: no entries yet.");
    expect(describeBubble(sig({ trend: -0.6 }), "6.4 hours this week")).toBe("Sleep: 6.4 hours this week lower than your usual.");
  });
});
