import { describe, expect, it } from "vitest";
import { decisionLine, readChoices, readHistory } from "./choices";

describe("privacy choices", () => {
  it("reads the list and drops anything malformed", () => {
    const list = readChoices({ consents: [{ purpose: "a", title: "A", what: "x", available: true, granted: false }, null, { nope: 1 }] });
    expect(list).toEqual([{ purpose: "a", title: "A", what: "x", available: true, granted: false, decidedAt: null }]);
    expect(readChoices(null)).toEqual([]);
  });

  it("says plainly when a choice was changed, and treats a missing answer as off", () => {
    const base = { purpose: "a", title: "A", what: "", available: true };
    expect(decisionLine({ ...base, granted: false, decidedAt: null })).toBe("Off");
    expect(decisionLine({ ...base, granted: true, decidedAt: "2026-10-12T10:00:00Z" }, new Date("2026-10-16"))).toBe("Turned on 12 Oct");
    expect(decisionLine({ ...base, available: false, granted: false, decidedAt: null })).toBe("Coming soon");
  });

  it("reads the history", () => {
    expect(readHistory({ history: [{ purpose: "a", title: "A", granted: true, source: "settings", at: "2026-10-12T10:00:00Z" }] })[0].granted).toBe(true);
    expect(readHistory(undefined)).toEqual([]);
  });
});
