/**
 * Checks for the quick-ask hand-off. Run: npx vitest run app/lib/ask-handoff.test.ts
 * Long health text must never reach the URL, and a stored question is read exactly once.
 */
import { describe, expect, it } from "vitest";
import { ASK_INLINE_MAX, askHandle, askHref, readAsk } from "./ask-handoff";

function fakeStore(seed: Record<string, string> = {}) {
  const data = new Map(Object.entries(seed));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

const paramsOf = (href: string) => new URL(href, "http://localhost").searchParams;

describe("askHref", () => {
  it("keeps a short question in the URL", () => {
    const href = askHref("How's my sleep this week?", fakeStore());
    expect(href).toBe("/companion?ask=How's%20my%20sleep%20this%20week%3F");
    expect(readAsk(paramsOf(href), fakeStore())).toBe("How's my sleep this week?");
  });

  it("keeps a question of exactly the limit inline and moves anything longer out of the URL", () => {
    expect(askHref("a".repeat(ASK_INLINE_MAX), fakeStore())).toContain("?ask=");
    const store = fakeStore();
    const longLog = "Slept badly, headache all day. ".repeat(20);
    const href = askHref(longLog, store);
    expect(href).toContain("?askref=");
    expect(href).not.toContain("ask=Slept");
    expect(href).not.toContain("headache");
    expect(href.length).toBeLessThan(60);
    expect([...store.data.values()]).toEqual([longLog.trim()]);
  });

  it("reads a stored question once and clears it", () => {
    const store = fakeStore();
    const longLog = "x".repeat(ASK_INLINE_MAX + 50);
    const params = paramsOf(askHref(longLog, store));
    expect(readAsk(params, store)).toBe(longLog);
    expect(store.data.size).toBe(0);
    expect(readAsk(params, store)).toBeNull();
  });

  it("still delivers the question when storage throws", () => {
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    const longLog = "y".repeat(ASK_INLINE_MAX + 1);
    const params = paramsOf(askHref(longLog, blocked));
    expect(readAsk(params, blocked)).toBe(longLog);
  });

  it("works with no storage at all", () => {
    const longLog = "z".repeat(ASK_INLINE_MAX + 1);
    const params = paramsOf(askHref(longLog, null));
    expect(readAsk(params, null)).toBe(longLog);
  });
});

describe("readAsk / askHandle", () => {
  it("returns null when there is nothing to send", () => {
    expect(readAsk(new URLSearchParams(""), fakeStore())).toBeNull();
    expect(askHandle(new URLSearchParams(""))).toBeNull();
  });

  it("returns null for an unknown or expired key", () => {
    expect(readAsk(new URLSearchParams("askref=gone"), fakeStore())).toBeNull();
  });

  it("identifies either form so the page handles each hand-off once", () => {
    expect(askHandle(new URLSearchParams("ask=hello"))).toBe("hello");
    expect(askHandle(new URLSearchParams("askref=abc123"))).toBe("abc123");
  });
});
