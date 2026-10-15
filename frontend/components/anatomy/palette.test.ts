import { describe, expect, it } from "vitest";
import { BODY_FILL, BODY_OUTLINE, CANVAS, SELECT_GLOW, STATUS_COLOR, contrast, statusColor } from "./palette";

describe("body palette contrast (WCAG 1.4.11 asks for 3:1 for the parts of a graphic you need to see)", () => {
  it("measures contrast correctly", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 0);
    expect(contrast("#777777", "#777777")).toBeCloseTo(1, 5);
  });

  it("the silhouette outline stands out from the canvas", () => {
    expect(contrast(BODY_OUTLINE, CANVAS)).toBeGreaterThanOrEqual(3);
  });

  it("the selection halo stands out from the canvas", () => {
    expect(contrast(SELECT_GLOW, CANVAS)).toBeGreaterThanOrEqual(3);
  });

  it("every organ status colour stands out from the body it sits on", () => {
    for (const [status, color] of Object.entries(STATUS_COLOR)) {
      expect(contrast(color, BODY_FILL), status).toBeGreaterThanOrEqual(3);
    }
  });

  it("falls back to the not-enough-data colour for an unknown status", () => {
    expect(statusColor(undefined)).toBe(STATUS_COLOR.unknown);
    expect(statusColor("something_new")).toBe(STATUS_COLOR.unknown);
  });
});
