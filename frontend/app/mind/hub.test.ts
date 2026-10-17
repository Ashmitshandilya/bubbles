import { describe, expect, it } from "vitest";
import { ASK, QUICK, softBrain } from "./hub";

describe("quick scores", () => {
  it("matches the server scales", () => {
    expect(QUICK.loneliness.options.map((o) => o.value)).toEqual([1, 2, 3, 4, 5]);
    expect(QUICK.anxiety.options.map((o) => o.value)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(QUICK.loneliness.question).toBe("How often do you feel lonely?");
  });
});

describe("softBrain", () => {
  it("has gentle words for every state and never says all clear", () => {
    for (const s of ["no_data", "steady", "worth_watching", "talk_to_doctor"] as const) {
      const w = softBrain(s);
      expect(w.length).toBeGreaterThan(10);
      expect(w).not.toMatch(/—|healthy|fine|normal|diagnos|disorder/i);
    }
    expect(softBrain(undefined)).toBe(softBrain("no_data"));
  });
});

describe("chat hand-off", () => {
  it("is short, first person and label free", () => {
    for (const q of Object.values(ASK)) {
      expect(q.length).toBeLessThan(120);
      expect(q).not.toMatch(/disorder|diagnos|—/i);
    }
  });
});
