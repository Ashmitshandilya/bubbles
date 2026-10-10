import { describe, expect, it } from "vitest";
import { partnerSummary } from "./summary";

const available = [
  { key: "cycle", label: "Cycle", description: "" },
  { key: "sleep", label: "Sleep", description: "" },
  { key: "support_note", label: "A note", description: "" },
] as const;
const base = { available: [...available], categories: [], sharing: false, connection: null };

describe("partnerSummary", () => {
  it("says nothing when the status could not be read", () => {
    expect(partnerSummary(null)).toBeNull();
  });
  it("is Off when nothing is shared and nobody is connected", () => {
    expect(partnerSummary(base)).toBe("Off");
  });
  it("names what is shared", () => {
    expect(partnerSummary({ ...base, sharing: true, categories: ["cycle"] })).toBe("Sharing cycle");
    expect(partnerSummary({ ...base, sharing: true, categories: ["cycle", "sleep", "support_note"] })).toBe("Sharing cycle, sleep and a note");
  });
  it("names the connected person when sharing is paused", () => {
    expect(partnerSummary({ ...base, connection: { name: "Sam", since: "2026-09-01" } })).toBe("Connected to Sam");
  });
});
