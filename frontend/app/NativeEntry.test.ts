import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: () => undefined }) }));

const { entryTarget } = await import("./NativeEntry");
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
