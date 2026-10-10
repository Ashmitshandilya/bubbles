/**
 * Render quality ladder for the landing (plan section 3.2). Pure functions and one small
 * ring buffer: nothing here touches the DOM, so it is unit-tested in node.
 *
 *   static  calm document: poster, CSS sky, same copy (reduced motion, no WebGL2, Save-Data, paused)
 *   lite    relief grid 48x64, baked sky, few bubbles, 30 fps idle throttle
 *   full    live sky, refraction, composer (desktop that measures well)
 */

export type Tier = "static" | "lite" | "full";

export type TierEnv = {
  reducedMotion: boolean;
  webgl2: boolean;
  saveData: boolean;
  mobile: boolean;
  /** navigator.deviceMemory in GB, when the browser reports it */
  deviceMemory?: number | null;
  /** navigator.hardwareConcurrency, when the browser reports it */
  hardwareConcurrency?: number | null;
  /** the visitor pressed "Pause motion" */
  pausedByUser: boolean;
  /** a demotion remembered from earlier in this session (sessionStorage) */
  storedTier?: Tier | null;
};

export const TIER_STORAGE_KEY = "bubbles-tier";

const isTier = (v: unknown): v is Tier => v === "static" || v === "lite" || v === "full";

/** Desktop-class hardware may be promoted to full. Phones never are; few cores or little memory stay lite. */
export function canPromote(env: Pick<TierEnv, "mobile" | "deviceMemory" | "hardwareConcurrency">) {
  if (env.mobile) return false;
  if (typeof env.deviceMemory === "number" && env.deviceMemory < 4) return false;
  if (typeof env.hardwareConcurrency === "number" && env.hardwareConcurrency <= 4) return false;
  return true;
}

/**
 * Where a visit starts. Everything that can render 3D starts in lite (phones stay there; desktop is
 * promoted later by the frame monitor). Few cores or low memory no longer mean static, only "not promotable".
 */
export function pickInitialTier(env: TierEnv): Tier {
  if (env.reducedMotion || !env.webgl2 || env.saveData || env.pausedByUser) return "static";
  // A remembered demotion is honoured: a stored "static" stays static, a stored "lite" or "full" starts in lite.
  return env.storedTier === "static" ? "static" : "lite";
}

/** One step down the ladder. */
export const demote = (tier: Tier): Tier => (tier === "full" ? "lite" : "static");
/** One step up the ladder (lite to full only; static never comes back by itself). */
export const promote = (tier: Tier): Tier => (tier === "lite" ? "full" : tier);

export function readStoredTier(storage: Pick<Storage, "getItem"> | null | undefined): Tier | null {
  try {
    const v = storage?.getItem(TIER_STORAGE_KEY);
    return isTier(v) ? v : null;
  } catch {
    return null;
  }
}

export function writeStoredTier(storage: Pick<Storage, "setItem"> | null | undefined, tier: Tier) {
  try {
    storage?.setItem(TIER_STORAGE_KEY, tier);
  } catch {
    // private mode or blocked storage: the demotion just is not remembered
  }
}

export const DEMOTE_FRAMES = 90;
export const DEMOTE_P95_MS = 24;
export const PROMOTE_FRAMES = 60;
/** Promotion judges the display's own rhythm, not an absolute budget: a 60 Hz screen can never beat 16.7 ms. */
export const PROMOTE_MEDIAN_MAX_MS = 17.5;
/** p95 may be at most this multiple of the median frame interval (a steady clock, few hitches). */
export const PROMOTE_P95_RATIO = 1.35;

/**
 * Fixed-size ring buffer of frame times in ms. No allocation after construction except the
 * transient view used for sorting, and only when a decision is asked for.
 */
export class FrameMonitor {
  private readonly buf = new Float32Array(DEMOTE_FRAMES);
  private readonly scratch = new Float32Array(DEMOTE_FRAMES);
  private head = 0;
  private count = 0;
  private readonly promotable: boolean;

  /** `mobile` phones are never promoted; pass `promotable: canPromote(env)` to also hold back weak desktops. */
  constructor(opts: { mobile: boolean; promotable?: boolean }) {
    this.promotable = !opts.mobile && opts.promotable !== false;
  }

  push(ms: number) {
    if (!Number.isFinite(ms) || ms < 0) return;
    this.buf[this.head] = ms;
    this.head = (this.head + 1) % this.buf.length;
    if (this.count < this.buf.length) this.count += 1;
  }

  get size() {
    return this.count;
  }

  reset() {
    this.head = 0;
    this.count = 0;
  }

  /** 95th percentile (nearest rank) of the newest `n` samples; 0 when there are fewer than `n`. */
  p95(n: number = DEMOTE_FRAMES): number {
    const len = Math.min(Math.max(1, Math.floor(n)), this.buf.length);
    if (this.count < len) return 0;
    for (let i = 0; i < len; i += 1) {
      this.scratch[i] = this.buf[(this.head - 1 - i + this.buf.length * 2) % this.buf.length];
    }
    const view = this.scratch.subarray(0, len).sort();
    return view[Math.ceil(0.95 * len) - 1];
  }

  /** Median of the newest `n` samples; 0 when there are fewer than `n`. */
  median(n: number = DEMOTE_FRAMES): number {
    const len = Math.min(Math.max(1, Math.floor(n)), this.buf.length);
    if (this.count < len) return 0;
    for (let i = 0; i < len; i += 1) {
      this.scratch[i] = this.buf[(this.head - 1 - i + this.buf.length * 2) % this.buf.length];
    }
    const view = this.scratch.subarray(0, len).sort();
    return (view[Math.ceil(len / 2) - 1] + view[Math.floor(len / 2)]) / 2;
  }

  /** Slow for a full 90 frames: p95 above 24 ms. */
  shouldDemote(): boolean {
    return this.count >= DEMOTE_FRAMES && this.p95(DEMOTE_FRAMES) > DEMOTE_P95_MS;
  }

  /**
   * Smooth for 60 frames on a promotable desktop: the median frame interval is at least 57 fps
   * (60, 120 or 144 Hz screens all qualify) and p95 stays within 1.35x of that median. Never true for mobile.
   */
  shouldPromote(): boolean {
    if (!this.promotable || this.count < PROMOTE_FRAMES) return false;
    const median = this.median(PROMOTE_FRAMES);
    return median > 0 && median <= PROMOTE_MEDIAN_MAX_MS && this.p95(PROMOTE_FRAMES) <= median * PROMOTE_P95_RATIO;
  }
}
