import { describe, expect, it } from "vitest";
import { CYCLE_TABS, tabForKey, tabFromHash } from "./cycle-nav";

describe("cycle tabs", () => {
  it("has the seven tabs in order", () => {
    expect(CYCLE_TABS.map((t) => t.id)).toEqual(["today", "calendar", "log", "insights", "fertility", "modes", "report"]);
  });

  it("reads the hash, falling back to today", () => {
    expect(tabFromHash("#calendar")).toBe("calendar");
    expect(tabFromHash("#REPORT")).toBe("report");
    expect(tabFromHash("")).toBe("today");
    expect(tabFromHash("#nonsense")).toBe("today");
  });

  it("moves with arrow keys and wraps", () => {
    expect(tabForKey("today", "ArrowRight")).toBe("calendar");
    expect(tabForKey("report", "ArrowRight")).toBe("today");
    expect(tabForKey("today", "ArrowLeft")).toBe("report");
    expect(tabForKey("log", "Home")).toBe("today");
    expect(tabForKey("log", "End")).toBe("report");
    expect(tabForKey("log", "Enter")).toBeNull();
  });
});
