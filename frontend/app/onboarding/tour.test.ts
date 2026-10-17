import { describe, expect, it } from "vitest";
import { TOUR_STEPS, outcomeBody, placeCard, reduceTour, shouldStart, tourView, usableSteps } from "./tour";

describe("the tour stops", () => {
  it("has four or five stops, each with plain copy and no em-dashes", () => {
    expect(TOUR_STEPS.length).toBeGreaterThanOrEqual(4);
    expect(TOUR_STEPS.length).toBeLessThanOrEqual(5);
    for (const step of TOUR_STEPS) {
      expect(`${step.title} ${step.body}`).not.toMatch(/[—–]/);
      expect(step.body.length).toBeLessThan(110);
    }
    expect(TOUR_STEPS.map((s) => s.id)).toEqual(["ask", "log", "week", "body", "me"]);
  });

  it("drops a stop whose target is not on the page (no body map card for a profile without one)", () => {
    const steps = usableSteps((s) => s.id !== "body");
    expect(steps.map((s) => s.id)).toEqual(["ask", "log", "week", "me"]);
  });
});

describe("moving through the tour", () => {
  const open = { open: true, index: 0 };

  it("goes forward and back, and cannot go back past the first stop", () => {
    expect(reduceTour(open, { type: "next" }, 5)).toEqual({ open: true, index: 1 });
    expect(reduceTour({ open: true, index: 2 }, { type: "back" }, 5)).toEqual({ open: true, index: 1 });
    expect(reduceTour(open, { type: "back" }, 5)).toEqual({ open: true, index: 0 });
  });

  it("closes after the last stop and on skip, and stays closed", () => {
    expect(reduceTour({ open: true, index: 4 }, { type: "next" }, 5).open).toBe(false);
    expect(reduceTour(open, { type: "close" }, 5).open).toBe(false);
    const closed = { open: false, index: 3 };
    expect(reduceTour(closed, { type: "next" }, 5)).toBe(closed);
  });

  it("says where you are and when it is the last stop", () => {
    expect(tourView(0, 5)).toEqual({ position: "1 of 5", isFirst: true, isLast: false });
    expect(tourView(4, 5)).toEqual({ position: "5 of 5", isFirst: false, isLast: true });
  });
});

describe("when the tour starts", () => {
  it("starts for someone who has not seen it, or on a replay, and never when seen or when unknown", () => {
    expect(shouldStart(false, false)).toBe(true);
    expect(shouldStart(true, false)).toBe(false);
    expect(shouldStart(true, true)).toBe(true);
    expect(shouldStart(null, false)).toBe(false);
  });

  it("records finish and skip", () => {
    expect(JSON.parse(outcomeBody(false))).toEqual({ skipped: false });
    expect(JSON.parse(outcomeBody(true))).toEqual({ skipped: true });
  });
});

describe("placing the card", () => {
  const phone = { width: 430, height: 900 };
  const card = { width: 340, height: 190 };

  it("sits under the target when it fits, inside the margins", () => {
    const at = placeCard({ top: 100, left: 20, width: 390, height: 60 }, phone, card);
    expect(at.top).toBe(174);
    expect(at.left).toBeGreaterThanOrEqual(16);
    expect(at.left + 340).toBeLessThanOrEqual(430 - 16);
  });

  it("goes above a target near the bottom, and pins to the bottom when neither fits", () => {
    expect(placeCard({ top: 800, left: 20, width: 100, height: 60 }, phone, card).top).toBe(800 - 14 - 190);
    expect(placeCard({ top: 60, left: 20, width: 100, height: 760 }, phone, card)).toEqual({ top: 900 - 190 - 16, left: 16 });
  });

  it("shrinks to a narrow screen", () => {
    const at = placeCard({ top: 10, left: 0, width: 320, height: 40 }, { width: 320, height: 640 }, card);
    expect(at.left).toBe(16);
  });
});
