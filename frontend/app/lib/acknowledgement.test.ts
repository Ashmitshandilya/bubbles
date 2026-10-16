import { describe, expect, it, vi } from "vitest";
import { flushAcknowledgement, pendingAcknowledgement, rememberAcknowledgement, type AckStore } from "./acknowledgement";

function memory(): NonNullable<AckStore> & { data: Record<string, string> } {
  const data: Record<string, string> = {};
  return {
    data,
    getItem: (k) => data[k] ?? null,
    setItem: (k, v) => {
      data[k] = v;
    },
    removeItem: (k) => {
      delete data[k];
    },
  };
}

describe("the sign-up acknowledgement", () => {
  it("is remembered with the notice version and found again", () => {
    const store = memory();
    expect(pendingAcknowledgement(store)).toBeNull();
    rememberAcknowledgement(store, "2026-10-16");
    expect(pendingAcknowledgement(store)).toBe("2026-10-16");
  });

  it("is sent once and then forgotten", async () => {
    const store = memory();
    rememberAcknowledgement(store, "v1");
    const send = vi.fn().mockResolvedValue(true);
    expect(await flushAcknowledgement(store, send)).toBe(true);
    expect(send).toHaveBeenCalledWith("v1");
    expect(await flushAcknowledgement(store, send)).toBe(false);
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("is kept for the next try when the server did not take it", async () => {
    const store = memory();
    rememberAcknowledgement(store, "v1");
    expect(await flushAcknowledgement(store, async () => false)).toBe(false);
    expect(await flushAcknowledgement(store, async () => Promise.reject(new Error("offline")))).toBe(false);
    expect(pendingAcknowledgement(store)).toBe("v1");
  });

  it("does nothing where storage is blocked", async () => {
    const broken: AckStore = {
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
    expect(() => rememberAcknowledgement(broken, "v1")).not.toThrow();
    expect(pendingAcknowledgement(broken)).toBeNull();
    expect(await flushAcknowledgement(null, async () => true)).toBe(false);
  });
});
