import { describe, expect, it } from "vitest";
import { agoText, describeWrite, pickLastUpdate, shouldRefreshOnResume } from "./data-sync";

describe("describeWrite", () => {
  it("ignores reads and plumbing", () => {
    expect(describeWrite("/health/weight?days=30", "GET")).toBeNull();
    expect(describeWrite("/health", "POST")).toBeNull();
    expect(describeWrite("/me/consent", "PUT")).toBeNull();
    expect(describeWrite("/consents/ai_chat_processing", "POST")).toBeNull();
    expect(describeWrite("/chat/feedback", "POST")).toBeNull();
  });
  it("names tracker saves", () => {
    expect(describeWrite("/health/weight", "POST")).toBe("Weight");
    expect(describeWrite("/health/hydration", "POST")).toBe("Water");
  });
  it("counts Companion", () => {
    expect(describeWrite("/chat", "POST")).toBe("Chat");
    expect(describeWrite("/health-events/abc/confirmation", "POST")).toBe("Companion notes");
  });
});

describe("requests that read through POST are not changes", () => {
  // Every one of these is sent while a screen loads. If any counted as a change, that screen would reload itself forever.
  it.each([
    ["/intelligence/brief", "Today"],
    ["/intelligence/deep", "Today"],
    ["/intelligence/longitudinal", "Patterns"],
    ["/patterns/analyze", "Patterns"],
    ["/insights/weekly", "Patterns"],
    ["/companion/daily", "Talk"],
    ["/doctor/prepare", "Care"],
    ["/medical/summary", "Care"],
    ["/rag/search", "Talk"],
    ["/fitness/meal/parse", "Fitness"],
    ["/fitness/workouts/screen", "Fitness"],
    ["/fitness/transform/preview", "Fitness"],
    ["/fitness/diet/swap-options", "Fitness"],
  ])("%s (%s) is not a change", (path) => {
    expect(describeWrite(path, "POST")).toBeNull();
    expect(describeWrite(`${path}?days=14`, "POST")).toBeNull();
  });
  it("an unknown POST is not a change either (fail safe, never loop)", () => {
    expect(describeWrite("/something/new", "POST")).toBeNull();
  });
  it("real saves still count", () => {
    expect(describeWrite("/fitness/food-log", "POST")).toBe("Fitness");
    expect(describeWrite("/fitness/workouts/log", "POST")).toBe("Fitness");
    expect(describeWrite("/cycle/period/start", "POST")).toBe("Cycle");
    expect(describeWrite("/health/sleep/abc", "DELETE")).toBe("Sleep");
    expect(describeWrite("/health/medications", "POST")).toBe("Medications");
    expect(describeWrite("/import/csv", "POST")).toBe("Imported records");
    expect(describeWrite("/me/whole-health/data?confirm=true", "DELETE")).toBe("Your record");
  });
});

describe("pickLastUpdate", () => {
  it("prefers the newer of local and server", () => {
    const local = { label: "Weight", at: 2_000 };
    expect(pickLastUpdate(local, new Date(1_000).toISOString())).toBe(local);
    expect(pickLastUpdate(local, new Date(5_000).toISOString())?.at).toBe(5_000);
    expect(pickLastUpdate(null, null)).toBeNull();
    expect(pickLastUpdate(null, "nope")).toBeNull();
  });
});

describe("agoText", () => {
  it("reads naturally", () => {
    const now = 10_000_000_000;
    expect(agoText(now - 5_000, now)).toBe("just now");
    expect(agoText(now - 5 * 60_000, now)).toBe("5 minutes ago");
    expect(agoText(now - 3 * 3_600_000, now)).toBe("3 hours ago");
    expect(agoText(now - 30 * 3_600_000, now)).toBe("yesterday");
  });
});

describe("profile changes", () => {
  it("setup and body figures count as record changes", () => {
    expect(describeWrite("/onboarding/complete", "POST")).toBe("Profile");
    expect(describeWrite("/profile/body", "PUT")).toBe("Profile");
    expect(describeWrite("/onboarding/answers", "PUT")).toBeNull();
  });
});

describe("shouldRefreshOnResume", () => {
  it("refreshes after a real absence, not a blink", () => {
    expect(shouldRefreshOnResume(null, 50_000)).toBe(false);
    expect(shouldRefreshOnResume(45_000, 50_000)).toBe(false);
    expect(shouldRefreshOnResume(10_000, 50_000)).toBe(true);
  });
});
