import { describe, expect, it } from "vitest";
import { KEEP_KEY, createAuthStorage } from "./auth-storage";

const fake = () => {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};
const blocked = () => ({
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
  removeItem: () => {
    throw new Error("blocked");
  },
});

describe("auth storage", () => {
  it("keeps the session in sessionStorage by default and never writes the token to localStorage", () => {
    const local = fake();
    const session = fake();
    const s = createAuthStorage(local, session);
    s.setItem("sb-token", "secret-session");
    expect(session.data.get("sb-token")).toBe("secret-session");
    expect(local.data.has("sb-token")).toBe(false);
    expect(s.getItem("sb-token")).toBe("secret-session");
  });

  it("uses localStorage only when the person chose to stay signed in, and moves the copy", () => {
    const local = fake();
    const session = fake();
    session.data.set("sb-token", "old");
    local.data.set(KEEP_KEY, "1");
    const s = createAuthStorage(local, session);
    s.setItem("sb-token", "kept");
    expect(local.data.get("sb-token")).toBe("kept");
    expect(session.data.has("sb-token")).toBe(false);
  });

  it("moves an old localStorage session to sessionStorage the next time it is refreshed", () => {
    const local = fake();
    const session = fake();
    local.data.set("sb-token", "legacy");
    const s = createAuthStorage(local, session);
    expect(s.getItem("sb-token")).toBe("legacy"); // still signed in
    s.setItem("sb-token", "refreshed");
    expect(local.data.has("sb-token")).toBe(false);
    expect(session.data.get("sb-token")).toBe("refreshed");
  });

  it("signs out of both places", () => {
    const local = fake();
    const session = fake();
    local.data.set("sb-token", "a");
    session.data.set("sb-token", "b");
    const s = createAuthStorage(local, session);
    s.removeItem("sb-token");
    expect(s.getItem("sb-token")).toBeNull();
    expect(local.data.size + session.data.size).toBe(0);
  });

  it("falls back to memory instead of throwing when the browser blocks storage", () => {
    const s = createAuthStorage(blocked(), blocked());
    expect(() => s.setItem("sb-token", "x")).not.toThrow();
    expect(s.getItem("sb-token")).toBe("x");
    expect(() => s.removeItem("sb-token")).not.toThrow();
    expect(s.getItem("sb-token")).toBeNull();
    const none = createAuthStorage(null, null);
    none.setItem("a", "b");
    expect(none.getItem("a")).toBe("b");
  });
});
