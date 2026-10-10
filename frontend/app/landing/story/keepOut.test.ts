import { describe, expect, it } from "vitest";
import { KEEP_OUT, KEEP_OUT_PAD, pushOut, type Push, type Rect } from "./keepOut";
import { CHAPTERS } from "./store";

const out = (): Push => ({ dx: 0, hide: false, side: 0 });
// the hero copy block on a 1440 x 900 screen: bottom left
const hero: Rect[] = [{ l: 80, t: 440, r: 740, b: 820 }];

describe("keep-out selectors", () => {
  it("has one entry per chapter", () => {
    expect(Object.keys(KEEP_OUT).sort()).toEqual(CHAPTERS.map((c) => c.key).sort());
  });
});

describe("pushOut", () => {
  it("leaves a clear bubble alone", () => {
    const p = pushOut(1100, 600, 60, hero, 1440, 0, out());
    expect(p).toEqual({ dx: 0, hide: false, side: 0 });
    expect(pushOut(400, 200, 60, hero, 1440, 0, out()).dx).toBe(0); // above the block
    expect(pushOut(400, 900, 60, hero, 1440, 0, out()).dx).toBe(0); // below it
  });

  it("slides a bubble inside the block to the nearer free side, clear of the pad", () => {
    const right = pushOut(600, 600, 60, hero, 1440, 0, out());
    expect(right.side).toBe(1);
    expect(600 + right.dx).toBe(740 + KEEP_OUT_PAD + 60);
    // a bubble just inside the block's left edge goes out the left side
    const left = pushOut(300, 600, 60, [{ l: 300, t: 440, r: 740, b: 820 }], 1440, 0, out());
    expect(left.side).toBe(-1);
    expect(300 + left.dx).toBe(300 - KEEP_OUT_PAD - 60);
  });

  it("keeps the side it chose, so a swaying bubble does not flip", () => {
    const first = pushOut(420, 600, 60, hero, 1440, 0, out());
    const flipped = pushOut(420, 600, 60, hero, 1440, first.side === 1 ? -1 : 1, out());
    // the sticky side is honoured when it is on screen
    expect(Math.sign(flipped.dx)).toBe(first.side === 1 ? -1 : 1);
  });

  it("never pushes a bubble off screen: with no free side it is told to hide", () => {
    const fullWidth: Rect[] = [{ l: 20, t: 440, r: 370, b: 800 }]; // a phone, 390 wide
    const p = pushOut(200, 600, 50, fullWidth, 390, 0, out());
    expect(p.hide).toBe(true);
    expect(p.dx).toBe(0);
  });

  it("takes the largest push when several blocks overlap, and reuses its output object", () => {
    const rects: Rect[] = [
      { l: 80, t: 440, r: 400, b: 820 },
      { l: 380, t: 440, r: 740, b: 820 },
    ];
    const o = out();
    const p = pushOut(390, 600, 40, rects, 1440, 0, o);
    expect(p).toBe(o);
    expect(p.side).not.toBe(0);
  });
});
