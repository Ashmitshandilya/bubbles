import { describe, expect, it } from "vitest";
import { bubbleFit } from "./SpeechBubble";
import { FEEL, feelAt, feelBand } from "./feel";
import { CHAPTERS, MOBILE_LEN_FACTOR, NEVER, chapterLen, resetStory, rotateFocus, story, totalLen, trackSpeed } from "./store";

describe("chapter lengths", () => {
  it("keeps every key and id, in order, with the retimed lengths (plan 2.7)", () => {
    expect(CHAPTERS.map((c) => c.key)).toEqual([
      "enter", "body", "noise", "track", "cycle", "connect", "remember", "companion", "care", "bubbles",
    ]);
    expect(CHAPTERS.map((c) => c.id)).toEqual([
      "top", "body", "noise", "how", "cycle", "connect", "memory", "companion", "trust", "start",
    ]);
    expect(CHAPTERS.map((c) => c.len)).toEqual([140, 200, 140, 190, 300, 160, 230, 230, 160, 140]);
  });

  it("totals 1890vh on desktop and about 1510vh on phones (factor 0.8)", () => {
    expect(totalLen(false)).toBe(1890);
    expect(MOBILE_LEN_FACTOR).toBe(0.8);
    expect(totalLen(true)).toBeCloseTo(1512, 6);
    expect(chapterLen(300, true)).toBeCloseTo(240, 6);
    expect(chapterLen(300, false)).toBe(300);
  });
});

describe("resetStory", () => {
  it("returns the shared story to a fresh visit (nothing left over from the last one)", () => {
    story.focus = { x: 0.2, y: -0.4, side: 1 };
    story.gaze = { x: -0.5, y: 0.1, side: -1 };
    story.current = 4;
    story.blend = 0.7;
    story.y = 3210;
    story.pointer.has = true;
    story.bubbles.visible = true;
    story.hop.live = true;
    story.hop.head = 0.5;
    story.excite = 1;
    story.boops = 7;
    story.tier = "full";
    story.paused = true;
    story.chapters[2] = { p: 0.9, enter: 1, exit: 0.4 };

    resetStory();

    expect(story.focus).toBeNull();
    expect(story.gaze).toBeNull();
    expect(story.current).toBe(0);
    expect(story.blend).toBe(0);
    expect(story.y).toBe(0);
    expect(story.pointer.has).toBe(false);
    expect(story.bubbles.visible).toBe(false);
    expect(story.hop.live).toBe(false);
    expect(story.hop.head).toBe(0);
    expect(story.excite).toBe(0);
    expect(story.boops).toBe(0);
    expect(story.tier).toBe("lite");
    expect(story.paused).toBe(false);
    expect(story.chapters.every((c) => c.p === 0 && c.enter === 0 && c.exit === 0)).toBe(true);
  });

  it("leaves the 3D world's own flags to the world", () => {
    story.worldReady = true;
    story.bubbles.anchor.unit = 12;
    resetStory();
    expect(story.worldReady).toBe(true);
    expect(story.bubbles.anchor.unit).toBe(12);
    story.worldReady = false;
    story.bubbles.anchor.unit = 0;
  });
});

describe("rotateFocus", () => {
  it("hands last frame's claim to Bubbles and clears it, so a claim never outlives the chapter that made it", () => {
    resetStory();
    const claim = { x: 0.3, y: -0.2, side: 1 };
    story.focus = claim; // the typing chapter claims the gaze during frame 1
    rotateFocus();
    expect(story.gaze).toBe(claim);
    expect(story.focus).toBeNull();

    story.focus = claim; // still claimed in frame 2
    rotateFocus();
    expect(story.gaze).toBe(claim);

    rotateFocus(); // frame 3: the visitor scrolled away and nobody claims it any more
    expect(story.gaze).toBeNull();
    rotateFocus();
    expect(story.gaze).toBeNull();
  });

  it("lets a new owner take over in the same frame the old one lets go", () => {
    resetStory();
    story.focus = { x: 0.9, y: 0.9, side: 1 };
    rotateFocus();
    const next = { x: -0.1, y: 0.2, side: -1 };
    story.focus = next;
    rotateFocus();
    expect(story.gaze).toBe(next);
  });
});

describe("NEVER", () => {
  it("is never 'recent', whatever the clock says (a -10 ms sentinel made Bubbles cheer at page load)", () => {
    for (const now of [0, 120, 1100, 1490, 60_000]) {
      expect((now - NEVER) / 1000).toBe(Infinity);
      expect((now - NEVER) / 1000 < 1.5).toBe(false);
      expect(now - NEVER < 900).toBe(false);
    }
  });
});

describe("trackSpeed", () => {
  it("is zero for a sprite that was just placed or teleported, however far it jumped", () => {
    expect(trackSpeed(0, null, 700, 0.016)).toBe(0);
    expect(trackSpeed(1200, null, 700, 0.016)).toBe(0);
    // the old formula measured the jump from x = 0: ~5000 px/s on the first frame, far above the "flying" threshold
    const oldFirstFrame = 0 + ((700 - 0) / 0.016 - 0) * (1 - Math.exp(-8 * 0.016));
    expect(oldFirstFrame).toBeGreaterThan(0.35 * 1280);
    expect(Math.abs(trackSpeed(0, null, 700, 0.016))).toBeLessThan(0.35 * 1280);
  });

  it("follows real motion and decays when the sprite stops", () => {
    let v = 0;
    for (let i = 0; i < 120; i += 1) v = trackSpeed(v, 100 + i, 101 + i, 1 / 60); // 60 px/s
    expect(v).toBeGreaterThan(55);
    expect(v).toBeLessThan(61);
    for (let i = 0; i < 120; i += 1) v = trackSpeed(v, 300, 300, 1 / 60);
    expect(Math.abs(v)).toBeLessThan(0.05);
  });

  it("stays finite for a zero or tiny frame time", () => {
    expect(Number.isFinite(trackSpeed(10, 0, 5, 0))).toBe(true);
    expect(Number.isFinite(trackSpeed(10, 0, 5, 1e-9))).toBe(true);
  });
});

describe("bubbleFit", () => {
  it("opens toward the roomier side on a phone and always fits inside the screen", () => {
    for (let vw = 320; vw <= 430; vw += 5) {
      for (let x = 24; x <= vw - 24; x += 4) {
        const { left, room } = bubbleFit(x, vw, true);
        const edge = left ? x - 40 - room : x + 40 + room;
        if (left) expect(edge).toBeGreaterThanOrEqual(12);
        else expect(edge).toBeLessThanOrEqual(vw - 12);
      }
    }
  });

  it("keeps the desktop behaviour: right of Bubbles until 70% of the width, and a full line of room", () => {
    expect(bubbleFit(800, 1280, false).left).toBe(false);
    expect(bubbleFit(1000, 1280, false).left).toBe(true);
    expect(bubbleFit(800, 1280, false).room).toBeGreaterThan(330);
    expect(bubbleFit(1000, 1280, false).room).toBeGreaterThan(330);
  });

  it("never returns a non-positive width", () => {
    expect(bubbleFit(0, 0, true).room).toBeGreaterThan(0);
    expect(bubbleFit(24, 100, false).room).toBeGreaterThan(0);
  });
});

describe("feel", () => {
  it("stays finite and within 0..1 across the whole cycle, including the last fractional day", () => {
    for (let d = 0; d <= 27.999; d += 0.037) {
      const m = feelAt(d);
      expect(Number.isFinite(m)).toBe(true);
      expect(m).toBeGreaterThanOrEqual(0);
      expect(m).toBeLessThanOrEqual(1);
    }
    expect(feelAt(0)).toBe(FEEL[0]);
    expect(feelAt(27.999)).toBeCloseTo(FEEL[27], 5);
  });

  it("makes day 22 the first heavier day (the cycle check-in fires when the counter reaches index 21)", () => {
    expect(FEEL.findIndex((m) => feelBand(m) === "heavy")).toBe(21);
    expect(feelBand(FEEL[11])).toBe("bright");
  });
});
