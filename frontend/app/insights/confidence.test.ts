// Run: npx vitest run app/insights/confidence.test.ts
import { describe, expect, it } from "vitest";
import { associationLevel, levelFromLabel, levelFromScore, recurrenceReason } from "./confidence";

describe("one confidence scale", () => {
  it("reads the server's word and ignores anything else", () => {
    expect(levelFromLabel("High")).toBe("High");
    expect(levelFromLabel(" medium ")).toBe("Medium");
    expect(levelFromLabel("certain")).toBeNull();
    expect(levelFromLabel(undefined)).toBeNull();
  });

  it("falls back to the same cut-offs as the backend", () => {
    expect(levelFromScore(0.75)).toBe("High");
    expect(levelFromScore(0.5)).toBe("Medium");
    expect(levelFromScore(0.49)).toBe("Low");
  });

  it("never lets a weak or unrepeated link read as High", () => {
    expect(associationLevel("weak", "repeated_pattern")).toBe("Medium");
    expect(associationLevel("strong", "single_period")).toBe("Medium");
    expect(associationLevel("moderate", "single_period")).toBe("Low");
  });

  it("does not over-claim in its reasons", () => {
    expect(recurrenceReason("High", 6, 20, 0.4)).toMatch(/not sure/);
    expect(recurrenceReason("Low", 3, 10, 0.9)).toMatch(/chance/);
  });
});
