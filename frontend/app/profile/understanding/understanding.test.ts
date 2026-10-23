import { describe, expect, it } from "vitest";
import { actionBody, joinWords, readUnderstanding } from "./understanding";

describe("readUnderstanding", () => {
  it("reads the sentences, the reason and how sure Bubbles is", () => {
    const u = readUnderstanding({
      status: "success",
      traits: [{ id: "tone", line: "You like a calm, direct tone.", why: "Why we think so: you chose it in setup.", confidence: "Fairly sure", state: "confirmed" }],
    })!;
    expect(u.traits).toEqual([{ id: "tone", line: "You like a calm, direct tone.", why: "Why we think so: you chose it in setup.", confidence: "Fairly sure", state: "confirmed" }]);
  });

  it("falls back safely on odd data and never invents a number", () => {
    const u = readUnderstanding({ traits: [{ id: "a", line: "x", confidence: "93%" }, { id: 4 }, null, "no"] })!;
    expect(u.traits).toHaveLength(1);
    expect(u.traits[0]).toMatchObject({ confidence: "Not sure yet", state: "inferred", why: "" });
    expect(readUnderstanding(null)).toBeNull();
    expect(readUnderstanding({ traits: "x" })).toBeNull();
  });

  it("carries the waiting message and what Bubbles would use", () => {
    const u = readUnderstanding({ traits: [], intro: "Bubbles is still getting to know you.", would_use: ["the tone you like", 4] })!;
    expect(u.traits).toEqual([]);
    expect(u.wouldUse).toEqual(["the tone you like"]);
  });
});

describe("helpers", () => {
  it("sends the two actions", () => {
    expect(JSON.parse(actionBody("confirm"))).toEqual({ action: "confirm" });
    expect(JSON.parse(actionBody("reject"))).toEqual({ action: "reject" });
  });
  it("joins words with and", () => {
    expect(joinWords([])).toBe("");
    expect(joinWords(["a"])).toBe("a");
    expect(joinWords(["a", "b"])).toBe("a and b");
    expect(joinWords(["a", "b", "c"])).toBe("a, b and c");
  });
});
