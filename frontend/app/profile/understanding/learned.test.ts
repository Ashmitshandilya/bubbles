import { describe, expect, it } from "vitest";
import { readLearned } from "./learned";

describe("readLearned", () => {
  it("turns links into plain rows with the record", () => {
    const rows = readLearned({ links: [{ link: ["sleep_hours", "mood"], status: "earned", right: 8, of: 10 }, { link: ["hydration_ml", "mood"], status: "learning", right: 0, of: 0 }] });
    expect(rows[0]).toMatchObject({ title: "A short night and your mood", status: "earned", record: "Held up for you: right 8 of 10 guesses." });
    expect(rows[1].record).toBe("Still learning: no guesses checked yet.");
  });
  it("ignores bad input", () => {
    expect(readLearned(null)).toEqual([]);
    expect(readLearned({ links: [{ link: "x" }, 5] })).toEqual([]);
  });
});
