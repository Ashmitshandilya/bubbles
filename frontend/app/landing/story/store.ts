/**
 * Shared, mutable story state. The scroll director writes it once per animation
 * frame; the WebGL world and the small interactive islands read it. It lives
 * outside React on purpose: scroll-rate values must never trigger re-renders.
 */

import { COLOR_SCRIPT, type Grade } from "../atmosphere/palette";
import type { Tier } from "../perf/tier";

export type Tone = "light" | "dark";

/**
 * The sky on screen, written by the scroll director when it changes (`v` counts changes) and read by the sky
 * shader, the studio lights and the post stack. Colours are hex; `dark` is the lead chapter's tone eased 0
 * (light) to 1 (dark); `grade` and `bloom` are the colour script's values for this moment of the story.
 */
export type SkyState = {
  v: number;
  top: string;
  mid: string;
  horizon: string;
  sun: string;
  key: string;
  rim: string;
  accent: string;
  tone: Tone;
  dark: number;
  bloom: number;
  grade: Grade;
};

/** The opening (dawn) chapter of the colour script: where every visit starts. */
const DAWN = COLOR_SCRIPT[0];

export const CHAPTERS = [
  { id: "top", key: "enter", label: "Bubbles", len: 130, tone: "light" },
  { id: "listen", key: "listen", label: "Listen", len: 180, tone: "light" },
  { id: "confirm", key: "confirm", label: "Confirm", len: 190, tone: "light" },
  { id: "patterns", key: "patterns", label: "Patterns", len: 200, tone: "light" },
  { id: "prepare", key: "prepare", label: "Appointments", len: 170, tone: "light" },
  { id: "start", key: "close", label: "Start", len: 120, tone: "light" },
] as const satisfies ReadonlyArray<{ id: string; key: string; label: string; len: number; tone: Tone }>;

/** Phones scroll through shorter chapters: 990vh on desktop becomes 792vh. */
export const MOBILE_LEN_FACTOR = 0.8;
/** Scroll length of one chapter in vh, for the given viewport class. */
export const chapterLen = (len: number, mobile: boolean) => (mobile ? len * MOBILE_LEN_FACTOR : len);
/** Total story length in vh. */
export const totalLen = (mobile: boolean) => CHAPTERS.reduce((sum, c) => sum + chapterLen(c.len, mobile), 0);

export type ChapterKey = (typeof CHAPTERS)[number]["key"];
export const CHAPTER_INDEX = Object.fromEntries(CHAPTERS.map((c, i) => [c.key, i])) as Record<ChapterKey, number>;

export type ChapterState = {
  /** 0..1 progress through the chapter's scroll length */
  p: number;
  /** 0..1 fade-in while the previous chapter hands over */
  enter: number;
  /** 0..1 fade-out while handing over to the next chapter */
  exit: number;
};

type Listener = (dt: number) => void;

export const story = {
  active: false,
  reduced: false,
  mobile: false,
  vw: 1280,
  vh: 800,
  /** damped scroll position in px */
  y: 0,
  /** index of the chapter currently on stage */
  current: 0,
  /** 0..1 hand-over from `current` to `current + 1` */
  blend: 0,
  chapters: CHAPTERS.map(() => ({ p: 0, enter: 0, exit: 0 }) as ChapterState),
  /** pointer in normalised device coordinates (-1..1, y up) */
  pointer: { x: 0, y: 0, has: false },
  /** 0..1 spring: the visitor is about to start (CTA hover in the finale) */
  excite: 0,
  worldReady: false,
  /** the post stack drew last frame, so scene-layer shaders write linear light (post/Composer.tsx) */
  postLive: false,
  /** render quality chosen by `perf/tier.ts`; lite until the start-up measurement says otherwise */
  tier: "lite" as Tier,
  /** the 3D world's WebGL context was lost: it stays unmounted for the rest of the visit */
  worldLost: false,
  /** the visitor pressed "Pause motion": ambient motion (sky drift, soap bubbles, CSS loops) is frozen */
  paused: false,
  sky: {
    v: 0,
    top: DAWN.sky.top,
    mid: DAWN.sky.mid,
    horizon: DAWN.sky.horizon,
    sun: DAWN.lights.sun,
    key: DAWN.lights.key,
    rim: DAWN.lights.rim,
    accent: DAWN.accent,
    tone: "light",
    dark: 0,
    bloom: DAWN.bloom,
    grade: { ...DAWN.grade },
  } as SkyState,
  listeners: new Set<Listener>(),
};

/** Back to the opening (dawn) sky. */
export function resetSky() {
  const s = story.sky;
  s.top = DAWN.sky.top;
  s.mid = DAWN.sky.mid;
  s.horizon = DAWN.sky.horizon;
  s.sun = DAWN.lights.sun;
  s.key = DAWN.lights.key;
  s.rim = DAWN.lights.rim;
  s.accent = DAWN.accent;
  s.tone = "light";
  s.dark = 0;
  s.bloom = DAWN.bloom;
  Object.assign(s.grade, DAWN.grade);
  s.v += 1;
}

/**
 * Put the shared state back to a fresh visit. `story` is a module singleton, so it outlives the page: without
 * this, a visitor who leaves mid-story and comes back (client-side navigation) would find the old chapter
 * progress still in place for the first frames.
 */
export function resetStory() {
  story.current = 0;
  story.blend = 0;
  story.y = 0;
  story.pointer.has = false;
  story.excite = 0;
  story.tier = "lite";
  story.worldLost = false;
  story.postLive = false;
  story.paused = false;
  frameRects.clear();
  resetSky();
  // (worldReady belongs to the 3D world, which resets it when it unmounts.)
  for (const c of story.chapters) {
    c.p = 0;
    c.enter = 0;
    c.exit = 0;
  }
}

export function onStoryFrame(listener: Listener) {
  story.listeners.add(listener);
  return () => {
    story.listeners.delete(listener);
  };
}

/** True while chapter `index` is the one on stage (it leads the hand-over past its midpoint). */
export const isLead = (index: number) =>
  (story.current === index && story.blend < 0.5) || (story.current === index - 1 && story.blend >= 0.5);

/** Element rects measured first thing each frame, while layout is still clean from the last paint (see `rectOf`). */
const frameRects = new Map<Element, { r: DOMRect; used: boolean }>();

/**
 * An element's viewport rect as of the start of this frame. Reading layout after the frame has written styles forces a
 * synchronous layout for every read (the biggest cost of a throttled scroll); instead the director re-measures every
 * element read last frame before it writes anything (`measureRects`), and chapters read the cached value here. An
 * element seen for the first time is measured on the spot. Gaze and connector lines are one frame behind, which is invisible.
 */
export function rectOf(el: Element): DOMRect {
  const hit = frameRects.get(el);
  if (hit) {
    hit.used = true;
    return hit.r;
  }
  const r = el.getBoundingClientRect();
  frameRects.set(el, { r, used: true });
  return r;
}

/** The director calls this before it writes anything in a frame: re-measure what was read last frame, forget the rest. */
export function measureRects() {
  for (const [el, entry] of frameRects) {
    if (!entry.used || !el.isConnected) frameRects.delete(el);
    else {
      entry.r = el.getBoundingClientRect();
      entry.used = false;
    }
  }
}

export const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
/** progress of `v` through [a, b] */
export const range = (v: number, a: number, b: number) => clamp01((v - a) / (b - a));
export const smooth = (t: number) => t * t * (3 - 2 * t);
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
