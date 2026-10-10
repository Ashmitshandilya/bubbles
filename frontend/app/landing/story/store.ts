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
  { id: "top", key: "enter", label: "Bubbles", len: 140, tone: "light" },
  { id: "body", key: "body", label: "Body", len: 200, tone: "dark" },
  { id: "noise", key: "noise", label: "Numbers", len: 140, tone: "light" },
  { id: "how", key: "track", label: "Track", len: 190, tone: "light" },
  { id: "cycle", key: "cycle", label: "Cycle", len: 300, tone: "dark" },
  { id: "connect", key: "connect", label: "Connect", len: 160, tone: "dark" },
  { id: "memory", key: "remember", label: "Memory", len: 230, tone: "dark" },
  { id: "companion", key: "companion", label: "Companion", len: 230, tone: "dark" },
  { id: "trust", key: "care", label: "Care", len: 160, tone: "light" },
  { id: "start", key: "bubbles", label: "Start", len: 140, tone: "light" },
] as const satisfies ReadonlyArray<{ id: string; key: string; label: string; len: number; tone: Tone }>;

/** Phones scroll through shorter chapters: 1890vh on desktop becomes about 1510vh. */
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

/** A point on screen (NDC) that Bubbles looks at, and which side of Bubbles it is on. */
export type Focus = { x: number; y: number; side: number };

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
  /** a DOM point Bubbles should look at (NDC), e.g. a hovered signal. Claimed again every frame by whichever chapter owns the gaze. */
  focus: null as null | Focus,
  /** last frame's claim: what Bubbles actually follows (see `rotateFocus`) */
  gaze: null as null | Focus,
  /** Bubbles' head on screen in CSS px, written by the world each frame */
  bubbles: {
    x: 0, y: 0, horn: { x: 0, y: 0 }, visible: false,
    anchor: { x: 0, y: 0, unit: 0 },
    /** Bubbles' hooves on screen (px) and the pelvis-to-hoof distance */
    feet: { x: 0, y: 0, dy: 0 },
  },
  /** the carry-hop route (Track to Cycle), sampled in screen px by the world or the host */
  hop: { live: false, n: 33, pts: new Float32Array(66), head: 0, dest: { x: 0, y: 0 } },
  /** 0..1 spring: the visitor is about to start (CTA hover in the finale) */
  excite: 0,
  /** HTML labels the world positions over 3D anchors */
  labels: new Map<string, HTMLElement>(),
  worldReady: false,
  /** render quality chosen by `perf/tier.ts`; lite until the start-up measurement says otherwise */
  tier: "lite" as Tier,
  /** the visitor pressed "Pause motion": ambient motion (sky drift, bubbles, spine, fireflies, CSS loops) is frozen */
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
  boops: 0,
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
 * Put the shared state back to a fresh visit. `story` is a module singleton, so it
 * outlives the page: without this, a visitor who leaves mid-story and comes back
 * (client-side navigation) would find the old gaze, boop count, hop route and chapter
 * progress still in place for the first frames.
 */
export function resetStory() {
  story.current = 0;
  story.blend = 0;
  story.y = 0;
  story.focus = null;
  story.gaze = null;
  story.pointer.has = false;
  story.bubbles.visible = false;
  story.hop.live = false;
  story.hop.head = 0;
  story.excite = 0;
  story.boops = 0;
  story.tier = "lite";
  story.paused = false;
  resetSky();
  // (worldReady and the anchor belong to the 3D world, which resets them when it unmounts.)
  for (const c of story.chapters) {
    c.p = 0;
    c.enter = 0;
    c.exit = 0;
  }
}

/**
 * Called once per frame before the chapter islands run. Whatever they claimed last frame
 * becomes the gaze and the claim is cleared, so a chapter that stops claiming (scrolled
 * past, or never released it) cannot leave Bubbles staring at a spot that is gone.
 */
export function rotateFocus() {
  story.gaze = story.focus;
  story.focus = null;
}

/** A timestamp for "this has not happened yet": `now - NEVER` is always huge, whatever `now` is. */
export const NEVER = Number.NEGATIVE_INFINITY;

/**
 * Smoothed horizontal speed in px/s. Pass `from = null` for a sprite that was just
 * placed or teleported (first frame, or the 3D anchor taking over): it has not
 * travelled anywhere, so its speed is 0 rather than the jump divided by one frame.
 */
export function trackSpeed(speed: number, from: number | null, to: number, dt: number) {
  if (from === null) return 0;
  return speed + ((to - from) / Math.max(dt, 1e-3) - speed) * (1 - Math.exp(-8 * dt));
}

/** 0..1 progress of the carry hop from Track into the cycle ring. */
export const hopT = () =>
  story.current === CHAPTER_INDEX.track ? story.blend : story.current > CHAPTER_INDEX.track ? 1 : 0;

/** Make Bubbles say something in its speech bubble. */
export const say = (text: string, ms = 2600) =>
  window.dispatchEvent(new CustomEvent("bubbles:say", { detail: { text, ms } }));

export function onStoryFrame(listener: Listener) {
  story.listeners.add(listener);
  return () => {
    story.listeners.delete(listener);
  };
}

/** True while chapter `index` is the one on stage (it leads the hand-over past its midpoint). */
export const isLead = (index: number) =>
  (story.current === index && story.blend < 0.5) || (story.current === index - 1 && story.blend >= 0.5);

/** NDC focus point for Bubbles from a DOM element's centre. */
export function focusOn(el: Element | null): Focus | null {
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const x = ((r.left + r.width / 2) / story.vw) * 2 - 1;
  const y = -(((r.top + r.height / 2) / story.vh) * 2 - 1);
  return { x, y, side: x >= 0 ? 1 : -1 };
}

export const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
/** progress of `v` through [a, b] */
export const range = (v: number, a: number, b: number) => clamp01((v - a) / (b - a));
export const smooth = (t: number) => t * t * (3 - 2 * t);
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
