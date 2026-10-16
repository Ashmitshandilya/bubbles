import { describe, expect, it } from "vitest";
import { DECLINE_KEY, clearDecline, declineActive, readDecline, writeDecline } from "./decline";

const DAY = 86_400_000;
const memory = () => {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

describe("declineActive", () => {
  const now = Date.parse("2026-10-16T10:00:00Z");
  it("holds for 14 days and then the question may come back", () => {
    expect(declineActive(new Date(now - 13 * DAY).toISOString(), now)).toBe(true);
    expect(declineActive(new Date(now - 14 * DAY).toISOString(), now)).toBe(false);
  });

  it("treats nothing, junk and a future date as not declined", () => {
    expect(declineActive(null, now)).toBe(false);
    expect(declineActive("nope", now)).toBe(false);
    expect(declineActive(new Date(now + DAY).toISOString(), now)).toBe(false);
  });
});

describe("storage", () => {
  it("round-trips and clears", () => {
    const store = memory();
    const now = Date.parse("2026-10-16T10:00:00Z");
    expect(readDecline(store, now)).toBe(false);
    writeDecline(store, now);
    expect(store.getItem(DECLINE_KEY)).toBe("2026-10-16T10:00:00.000Z");
    expect(readDecline(store, now + DAY)).toBe(true);
    clearDecline(store);
    expect(readDecline(store, now)).toBe(false);
  });

  it("survives storage that throws", () => {
    const broken = {
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
    expect(readDecline(broken)).toBe(false);
    expect(() => writeDecline(broken)).not.toThrow();
    expect(() => clearDecline(broken)).not.toThrow();
  });
});
