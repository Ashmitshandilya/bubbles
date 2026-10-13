import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: () => undefined }) }));

const { entryRoute, entryTarget } = await import("./NativeEntry");
const ORIGIN = "https://heybubbles.in";

describe("entryTarget", () => {
  it("follows a path on this origin, keeping its query and hash", () => {
    expect(entryTarget("/cycle?tab=log#today", ORIGIN)).toBe("/cycle?tab=log#today");
  });

  it("goes to the dashboard without a usable target", () => {
    for (const to of [null, "", "/", "/?to=/sleep", "dashboard", "https://evil.example/x", "javascript:alert(1)"]) {
      expect(entryTarget(to, ORIGIN)).toBe("/dashboard");
    }
  });

  it("never leaves the origin", () => {
    for (const to of ["//evil.example/x", "/\\evil.example/x", "/\t/evil.example/x", "/\n/evil.example"]) {
      expect(entryTarget(to, ORIGIN)).toBe("/dashboard");
    }
  });
});

describe("entryRoute", () => {
  it("shows the welcome only to signed-out people opening the app", () => {
    expect(entryRoute(null, ORIGIN, false)).toBeNull();
    expect(entryRoute(null, ORIGIN, true)).toBe("/dashboard");
  });

  it("follows a deep link either way; that page checks sign-in itself", () => {
    expect(entryRoute("/sleep", ORIGIN, false)).toBe("/sleep");
    expect(entryRoute("/sleep", ORIGIN, true)).toBe("/sleep");
    expect(entryRoute("//evil.example", ORIGIN, false)).toBe("/dashboard");
  });
});
