import { describe, expect, it } from "vitest";
import { measureRects, rectOf, resetStory } from "./store";

const fakeEl = (top: number) => {
  const el = { calls: 0, top, isConnected: true, getBoundingClientRect() { el.calls += 1; return { top: el.top } as DOMRect; } };
  return el;
};

describe("rectOf: layout read once per frame, at the start", () => {
  it("measures a new element on the spot, then serves the cached rect until the next frame", () => {
    resetStory();
    const el = fakeEl(10);
    expect(rectOf(el as unknown as Element).top).toBe(10);
    el.top = 20;
    expect(rectOf(el as unknown as Element).top).toBe(10); // same frame: cached, no second layout
    expect(el.calls).toBe(1);
    measureRects(); // next frame starts: re-measured once
    expect(rectOf(el as unknown as Element).top).toBe(20);
    expect(el.calls).toBe(2);
  });

  it("forgets elements nobody read last frame, and detached ones", () => {
    resetStory();
    const idle = fakeEl(1);
    const gone = fakeEl(2);
    rectOf(idle as unknown as Element);
    rectOf(gone as unknown as Element);
    measureRects(); // both re-measured (read last frame)
    gone.isConnected = false;
    rectOf(gone as unknown as Element);
    measureRects(); // idle was not read: dropped; gone is detached: dropped
    const before = idle.calls + gone.calls;
    measureRects();
    expect(idle.calls + gone.calls).toBe(before);
  });
});
