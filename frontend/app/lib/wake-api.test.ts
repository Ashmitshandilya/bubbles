import { describe, expect, it } from "vitest";
import { wakeUrl } from "./wake-api";

describe("wakeUrl", () => {
  it("uses the website's own route on https", () => {
    expect(wakeUrl("https:", "https://heybubbles.in", false)).toBe("https://heybubbles.in/bubbles-api/health");
  });
  it("does nothing for local development or the Android app", () => {
    expect(wakeUrl("http:", "http://localhost:3000", false)).toBeNull();
    expect(wakeUrl("https:", "https://localhost", true)).toBeNull();
  });
});
