import { describe, expect, it } from "vitest";
import { eyebrow } from "./eyebrow";
import { CHAPTERS } from "./story/store";

describe("chapter eyebrow", () => {
  it("numbers every chapter and falls back to its label", () => {
    expect(eyebrow("enter")).toBe(`01 / ${String(CHAPTERS.length).padStart(2, "0")} · CYCLE-AWARE. ALWAYS HUMAN.`);
    expect(eyebrow("body")).toMatch(/^02 \/ \d\d · BODY$/);
    expect(eyebrow("nope")).toBe("");
  });
});
