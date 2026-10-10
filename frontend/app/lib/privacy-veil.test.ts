/**
 * Checks for the privacy veil rules. Run: npx vitest run app/lib/privacy-veil.test.ts
 * Default OFF, storage that throws must not break anything, and coming back to the tab must not reveal by itself.
 */
import { describe, expect, it } from "vitest";
import { VEIL_KEY, isVeiled, nextCover, readVeilSetting, writeVeilSetting, type VeilStore } from "./privacy-veil";

function fakeStore(seed: Record<string, string> = {}) {
  const data = new Map(Object.entries(seed));
  return { data, getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) } satisfies VeilStore & { data: Map<string, string> };
}

const throwing: VeilStore = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
};

describe("veil setting storage", () => {
  it("is off by default and for anything that is not an explicit 1", () => {
    expect(readVeilSetting(fakeStore())).toBe(false);
    expect(readVeilSetting(fakeStore({ [VEIL_KEY]: "0" }))).toBe(false);
    expect(readVeilSetting(fakeStore({ [VEIL_KEY]: "true" }))).toBe(false);
    expect(readVeilSetting(null)).toBe(false);
  });

  it("round-trips on and off", () => {
    const store = fakeStore();
    expect(writeVeilSetting(store, true)).toBe(true);
    expect(readVeilSetting(store)).toBe(true);
    expect(writeVeilSetting(store, false)).toBe(true);
    expect(readVeilSetting(store)).toBe(false);
  });

  it("survives storage that throws or is missing", () => {
    expect(readVeilSetting(throwing)).toBe(false);
    expect(writeVeilSetting(throwing, true)).toBe(false);
    expect(writeVeilSetting(null, true)).toBe(false);
  });
});

describe("cover and reveal", () => {
  it("covers when the tab is hidden or loses focus, however often it fires", () => {
    expect(nextCover(false, "away")).toBe(true);
    expect(nextCover(true, "away")).toBe(true);
  });

  it("a tap reveals and the Hide button flips", () => {
    expect(nextCover(true, "reveal")).toBe(false);
    expect(nextCover(false, "reveal")).toBe(false);
    expect(nextCover(false, "toggle")).toBe(true);
    expect(nextCover(true, "toggle")).toBe(false);
  });

  it("only blurs when the setting is on and something covered the values", () => {
    expect(isVeiled(true, true)).toBe(true);
    expect(isVeiled(true, false)).toBe(false);
    expect(isVeiled(false, true)).toBe(false);
    expect(isVeiled(false, false)).toBe(false);
  });
});
