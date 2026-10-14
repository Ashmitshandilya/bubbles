import { describe, expect, it } from "vitest";
import { CHAPTERS, MOBILE_LEN_FACTOR, chapterLen, resetStory, story, totalLen } from "./store";

describe("chapter lengths", () => {
  it("tells one story in six chapters, in order", () => {
    expect(CHAPTERS.map((c) => c.key)).toEqual(["enter", "listen", "confirm", "patterns", "prepare", "close"]);
    expect(CHAPTERS.map((c) => c.id)).toEqual(["top", "listen", "confirm", "patterns", "prepare", "start"]);
    expect(CHAPTERS.map((c) => c.len)).toEqual([130, 180, 190, 200, 170, 120]);
    expect(CHAPTERS.every((c) => c.tone === "light")).toBe(true);
  });

  it("totals 990vh on desktop and 792vh on phones (factor 0.8)", () => {
    expect(totalLen(false)).toBe(990);
    expect(MOBILE_LEN_FACTOR).toBe(0.8);
    expect(totalLen(true)).toBeCloseTo(792, 6);
    expect(chapterLen(200, true)).toBeCloseTo(160, 6);
    expect(chapterLen(200, false)).toBe(200);
  });
});

describe("resetStory", () => {
  it("returns the shared story to a fresh visit (nothing left over from the last one)", () => {
    story.current = 4;
    story.blend = 0.7;
    story.y = 3210;
    story.pointer.has = true;
    story.excite = 1;
    story.tier = "full";
    story.paused = true;
    story.postLive = true;
    story.chapters[2] = { p: 0.9, enter: 1, exit: 0.4 };

    resetStory();

    expect(story.current).toBe(0);
    expect(story.blend).toBe(0);
    expect(story.y).toBe(0);
    expect(story.pointer.has).toBe(false);
    expect(story.excite).toBe(0);
    expect(story.tier).toBe("lite");
    expect(story.paused).toBe(false);
    expect(story.postLive).toBe(false);
    expect(story.chapters.every((c) => c.p === 0 && c.enter === 0 && c.exit === 0)).toBe(true);
  });

  it("leaves the 3D world's own flag to the world", () => {
    story.worldReady = true;
    resetStory();
    expect(story.worldReady).toBe(true);
    story.worldReady = false;
  });
});
