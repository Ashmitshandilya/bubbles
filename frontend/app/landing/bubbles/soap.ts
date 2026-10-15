/**
 * The soap-bubble field: pure state and motion for the bubbles that rise through the hero and the finale
 * (and, fainter, behind the other chapters). No three.js and no DOM here, so it is unit-tested in node;
 * SoapBubbles.tsx turns these numbers into instances. Positions are viewport px, y down.
 *
 * Three depth layers (small and far, middle, large and near) rise at different speeds. Bubbles slide round
 * the copy blocks (story/keepOut.ts), fade in and out with a per-chapter level, and can be popped.
 */
import type { Tier } from "../perf/tier";
import { CHAPTERS, easeInOut, type ChapterKey } from "../story/store";
import { pushOut, type Push, type Rect } from "../story/keepOut";

export const MAX_BUBBLES = 12;

/** How many bubbles a tier draws: full 12, lite 6, static none (the page shows CSS bubbles instead). */
export function bubbleCount(tier: Tier): number {
  return tier === "static" ? 0 : tier === "full" ? MAX_BUBBLES : 6;
}

/** 0..1 share of the field that is awake in a chapter. One spectacle per view: the orb leads, so the field is quiet, and empty behind the ring and the summary. */
export const BUBBLE_LEVEL: Record<ChapterKey, number> = {
  enter: 0.35,
  listen: 0.2,
  confirm: 0,
  patterns: 0,
  prepare: 0,
  close: 1,
};

/** The level while chapter `index` hands over to the next one (`blend` 0..1). */
export function levelAt(index: number, blend: number): number {
  const last = CHAPTERS.length - 1;
  const i = Math.min(last, Math.max(0, Math.floor(index)));
  const a = BUBBLE_LEVEL[CHAPTERS[i].key];
  const b = BUBBLE_LEVEL[CHAPTERS[Math.min(last, i + 1)].key];
  return a + (b - a) * easeInOut(Math.min(1, Math.max(0, blend)));
}

/** Per depth layer: radius px, rise px/s, distance from the camera, peak opacity, pointer parallax px. */
export const LAYERS = [
  { r: 30, rise: 20, depth: 14, alpha: 0.55, shift: 5 },
  { r: 62, rise: 32, depth: 9.5, alpha: 0.8, shift: 12 },
  { r: 112, rise: 46, depth: 6.5, alpha: 1, shift: 24 },
] as const;

export const POP_S = 0.34;

const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);

/** Small deterministic generator, so a field built with the same seed always behaves the same. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type StepInput = {
  vw: number;
  vh: number;
  mobile: boolean;
  /** seconds since the world started (for sway) */
  time: number;
  /** chapter level 0..1 (see levelAt) */
  level: number;
  /** how many of the field's bubbles this tier draws */
  active: number;
  /** 0..1, the start button is hovered: bubbles swell and rise a little faster */
  excite: number;
  /** pointer in NDC (-1..1), for parallax; null when there is none */
  pointer: { x: number; y: number } | null;
  rects: readonly Rect[];
};

export class SoapField {
  readonly n = MAX_BUBBLES;
  /** centre, radius (px) and distance from the camera */
  readonly x = new Float32Array(MAX_BUBBLES);
  readonly y = new Float32Array(MAX_BUBBLES);
  readonly r = new Float32Array(MAX_BUBBLES);
  readonly depth = new Float32Array(MAX_BUBBLES);
  /** final opacity 0..1 */
  readonly alpha = new Float32Array(MAX_BUBBLES);
  /** 0 intact, 0..1 while bursting */
  readonly pop = new Float32Array(MAX_BUBBLES);
  readonly hover = new Float32Array(MAX_BUBBLES);
  readonly seed = new Float32Array(MAX_BUBBLES);
  readonly vis = new Float32Array(MAX_BUBBLES);

  private readonly rand: () => number;
  private readonly baseR = new Float32Array(MAX_BUBBLES);
  private readonly x0 = new Float32Array(MAX_BUBBLES);
  private readonly phase = new Float32Array(MAX_BUBBLES);
  private readonly speed = new Float32Array(MAX_BUBBLES);
  private readonly delay = new Float32Array(MAX_BUBBLES);
  private readonly offset = new Float32Array(MAX_BUBBLES);
  private readonly side = new Int8Array(MAX_BUBBLES);
  private readonly push: Push = { dx: 0, hide: false, side: 0 };
  private hovered = -1;
  private age = 0;
  private placed = false;

  constructor(seed = 7) {
    this.rand = mulberry32(seed);
    for (let i = 0; i < MAX_BUBBLES; i += 1) {
      this.seed[i] = this.rand();
      this.baseR[i] = 0.78 + this.rand() * 0.5;
      this.speed[i] = 0.8 + this.rand() * 0.4;
      this.phase[i] = this.rand() * Math.PI * 2;
      this.delay[i] = 0.35 + i * 0.2;
      this.depth[i] = LAYERS[i % 3].depth;
    }
  }

  private unit(vw: number, vh: number, mobile: boolean) {
    return clamp(Math.min(vw, vh) / 900, 0.6, 1.3) * (mobile ? 0.8 : 1);
  }

  private spawn(i: number, vw: number, vh: number, mobile: boolean, scatter: boolean) {
    this.x0[i] = this.rand() * vw;
    this.phase[i] = this.rand() * Math.PI * 2;
    this.baseR[i] = 0.78 + this.rand() * 0.5;
    const r = LAYERS[i % 3].r * this.baseR[i] * this.unit(vw, vh, mobile);
    this.r[i] = r;
    this.y[i] = scatter ? vh * (0.3 + this.rand() * 0.75) : vh + r * 1.3 + this.rand() * vh * 0.25;
    this.x[i] = this.x0[i];
    this.offset[i] = 0;
    this.side[i] = 0;
  }

  /** Advance everything by `dt` seconds. */
  step(dt: number, o: StepInput) {
    if (!this.placed) {
      this.placed = true;
      for (let i = 0; i < MAX_BUBBLES; i += 1) this.spawn(i, o.vw, o.vh, o.mobile, true);
    }
    this.age += dt;
    const unit = this.unit(o.vw, o.vh, o.mobile);
    const swell = 1 + 0.12 * o.excite;
    for (let i = 0; i < MAX_BUBBLES; i += 1) {
      const layer = LAYERS[i % 3];
      const r = layer.r * this.baseR[i] * unit * swell;
      this.r[i] = r;

      // A burst runs its course, then the bubble is reborn below the screen.
      if (this.pop[i] > 0) {
        this.pop[i] += dt / POP_S;
        if (this.pop[i] >= 1) {
          this.pop[i] = 0;
          this.vis[i] = 0;
          this.spawn(i, o.vw, o.vh, o.mobile, false);
        }
      } else {
        this.y[i] -= layer.rise * this.speed[i] * unit * (1 + 0.6 * o.excite) * dt;
        if (this.y[i] < -r * 1.3) this.spawn(i, o.vw, o.vh, o.mobile, false);
      }

      const sway = (14 + 16 * (i % 3)) * unit * Math.sin(o.time * (0.5 + 0.1 * (i % 3)) + this.phase[i]);
      const shift = o.pointer ? -o.pointer.x * layer.shift : 0;
      const baseX = this.x0[i] + sway + shift;

      // Slide round the copy; with no free side (a phone, full-width copy) the bubble fades instead.
      const p = pushOut(baseX, this.y[i], r, o.rects, o.vw, this.side[i], this.push);
      this.side[i] = p.side;
      this.offset[i] += (p.dx - this.offset[i]) * (1 - Math.exp(-7 * dt));
      this.x[i] = baseX + this.offset[i];

      const awake = this.age >= this.delay[i] && i < o.active && !p.hide;
      const want = awake ? 1 : 0;
      this.vis[i] += (want - this.vis[i]) * (1 - Math.exp(-(want ? 2.4 : 4) * dt));
      this.hover[i] += ((i === this.hovered ? 1 : 0) - this.hover[i]) * (1 - Math.exp(-10 * dt));
      // The chapter level also dims the whole field a little, so a calm chapter reads calm.
      this.alpha[i] = layer.alpha * this.vis[i] * (0.5 + 0.5 * clamp(o.level * 1.3, 0, 1));
    }
  }

  /** The bubble under (px, py) that a click would pop: the one the point is deepest inside. -1 for none. */
  hit(px: number, py: number): number {
    let best = -1;
    let bestScore = 1.08;
    for (let i = 0; i < MAX_BUBBLES; i += 1) {
      if (this.pop[i] > 0 || this.vis[i] < 0.35) continue;
      const score = Math.hypot(px - this.x[i], py - this.y[i]) / Math.max(1, this.r[i]);
      if (score < bestScore) {
        bestScore = score;
        best = i;
      }
    }
    return best;
  }

  /** Light up the bubble under a hovering pointer. Returns whether there is one. */
  hoverAt(px: number, py: number): boolean {
    this.hovered = this.hit(px, py);
    return this.hovered >= 0;
  }

  clearHover() {
    this.hovered = -1;
  }

  /** Burst bubble `i`. False when it cannot be popped (already bursting, or not yet visible). */
  popAt(i: number): boolean {
    if (i < 0 || i >= MAX_BUBBLES || this.pop[i] > 0 || this.vis[i] < 0.35) return false;
    this.pop[i] = 1e-4;
    return true;
  }
}
