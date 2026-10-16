import { describe, expect, it } from "vitest";
import { applyOutcomes, optimistic, outcomesFromBatch } from "./event-decisions";

describe("event decisions", () => {
  it("shows the choice at once", () => {
    expect(optimistic(["a", "b"], true)).toEqual({ a: "saved", b: "saved" });
    expect(optimistic(["a"], false)).toEqual({ a: "dismissed" });
  });

  it("reads a batch answer per id, and treats a missing or malformed answer as failed", () => {
    const out = outcomesFromBatch(["a", "b", "c", "d"], [
      { id: "a", status: "confirmed" },
      { id: "b", status: "error", code: 409 },
      { id: "c", status: "error", code: 500 },
    ]);
    expect(out).toEqual(["done", "withdrawn", "failed", "failed"]);
    expect(outcomesFromBatch(["a"], null)).toEqual(["failed"]);
  });

  it("rolls back only the failed ids", () => {
    const state = { a: "saved", b: "saved", c: "saved" };
    expect(applyOutcomes(state, ["a", "b", "c"], true, ["done", "failed", "withdrawn"])).toEqual({ a: "saved", c: "retracted" });
  });
});
