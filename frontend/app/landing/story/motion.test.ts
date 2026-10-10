import { beforeEach, describe, expect, it } from "vitest";
import { PAUSE_STORAGE_KEY, applyPaused, readPaused, restorePaused, writePaused } from "./motion";
import { resetStory, story } from "./store";

/** A storage that remembers, like localStorage. */
const memory = () => {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

/** A storage that throws on every use, like a blocked or full one. */
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

/** The one thing the page root has to do. */
const root = () => {
  const attrs = new Set<string>();
  return {
    attrs,
    toggleAttribute(name: string, force?: boolean) {
      if (force) attrs.add(name);
      else attrs.delete(name);
      return attrs.has(name);
    },
  };
};

beforeEach(() => resetStory());

describe("remembering Pause motion", () => {
  it("is off by default and when nothing is stored", () => {
    expect(readPaused(memory())).toBe(false);
    expect(readPaused(null)).toBe(false);
    expect(readPaused(undefined)).toBe(false);
  });

  it("stores the choice and clears it again when motion is switched back on", () => {
    const store = memory();
    writePaused(store, true);
    expect(store.data.get(PAUSE_STORAGE_KEY)).toBe("1");
    expect(readPaused(store)).toBe(true);
    writePaused(store, false);
    expect(store.data.has(PAUSE_STORAGE_KEY)).toBe(false);
    expect(readPaused(store)).toBe(false);
  });

  it("only treats the exact stored value as paused", () => {
    const store = memory();
    store.data.set(PAUSE_STORAGE_KEY, "true");
    expect(readPaused(store)).toBe(false);
  });

  it("works without storage: reading or writing a blocked storage never throws", () => {
    expect(() => readPaused(blocked)).not.toThrow();
    expect(readPaused(blocked)).toBe(false);
    expect(() => writePaused(blocked, true)).not.toThrow();
    expect(() => writePaused(blocked, false)).not.toThrow();
    expect(() => writePaused(null, true)).not.toThrow();
  });
});

describe("applying a choice", () => {
  it("sets the story flag, the page attribute and storage together", () => {
    const store = memory();
    const el = root();
    expect(applyPaused(el, true, true, store)).toBe(true);
    expect(story.paused).toBe(true);
    expect(el.attrs.has("data-paused")).toBe(true);
    expect(readPaused(store)).toBe(true);

    expect(applyPaused(el, false, true, store)).toBe(false);
    expect(story.paused).toBe(false);
    expect(el.attrs.has("data-paused")).toBe(false);
    expect(readPaused(store)).toBe(false);
  });

  it("still pauses when storage is blocked (the choice just is not remembered)", () => {
    const el = root();
    applyPaused(el, true, true, blocked);
    expect(story.paused).toBe(true);
    expect(el.attrs.has("data-paused")).toBe(true);
  });

  it("works with no root element yet", () => {
    expect(() => applyPaused(null, true, false, memory())).not.toThrow();
    expect(story.paused).toBe(true);
  });

  it("restoring a remembered choice does not write anything", () => {
    const store = memory();
    store.data.set(PAUSE_STORAGE_KEY, "1");
    const el = root();
    expect(restorePaused(el, store)).toBe(true);
    expect(story.paused).toBe(true);
    expect(el.attrs.has("data-paused")).toBe(true);
    expect(store.data.get(PAUSE_STORAGE_KEY)).toBe("1");

    resetStory();
    const fresh = memory();
    expect(restorePaused(root(), fresh)).toBe(false);
    expect(fresh.data.size).toBe(0);
  });

  it("is forgotten by resetStory, like the rest of a visit", () => {
    applyPaused(root(), true, false, memory());
    resetStory();
    expect(story.paused).toBe(false);
  });
});
