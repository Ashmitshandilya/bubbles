/**
 * Keep-out zones: the copy blocks of each chapter, in viewport px, so decorative soap bubbles slide
 * around headlines, forms and buttons instead of floating over them. Measuring touches the DOM and is done
 * on resize and on chapter change only; `pushOut` is pure and allocation-free (unit-tested).
 */
import type { ChapterKey } from "./store";

export type Rect = { l: number; t: number; r: number; b: number };

/** Breathing room kept between a bubble's edge and the copy, in px. */
export const KEEP_OUT_PAD = 14;

/** Selectors (inside the chapter's section) of the blocks bubbles must not cover. */
export const KEEP_OUT: Record<ChapterKey, string> = {
  enter: ".cw-copy, .cw-hero-orb",
  listen: ".cw-copy, .cw-listen-orb, .cw-say",
  confirm: ".cw-copy, .cw-chat",
  patterns: ".cw-copy, .cw-ring",
  prepare: ".cw-copy, .cw-sheet",
  close: ".cw-copy, .cw-close-orb, .cw-promises",
};

/** Rects of a chapter's copy blocks. Reuses `out` (cleared first). */
export function measureKeepOut(root: ParentNode, key: ChapterKey, out: Rect[] = []): Rect[] {
  out.length = 0;
  const nodes = root.querySelectorAll(`section[data-chapter="${key}"] :is(${KEEP_OUT[key]})`);
  nodes.forEach((el) => {
    const b = el.getBoundingClientRect();
    if (b.width > 1 && b.height > 1) out.push({ l: b.left, t: b.top, r: b.right, b: b.bottom });
  });
  return out;
}

export type Push = {
  /** horizontal move (px) that clears the copy; 0 when the bubble is already clear */
  dx: number;
  /** no free side on screen (a phone, full-width copy): the bubble should fade instead */
  hide: boolean;
  /** -1 left, 1 right, 0 none: pass it back as `sticky` next frame so the bubble does not flip sides */
  side: number;
};

/**
 * How far to move a bubble (centre `cx, cy`, radius `r`) sideways so it clears every rect plus the pad.
 * Only horizontal, because bubbles rise: they slip round a block instead of stopping against it. A side
 * whose destination would be off screen is not offered; with no side left the bubble is told to hide.
 */
export function pushOut(cx: number, cy: number, r: number, rects: readonly Rect[], vw: number, sticky: number, out: Push): Push {
  out.dx = 0;
  out.hide = false;
  out.side = 0;
  let best = 0;
  for (let k = 0; k < rects.length; k += 1) {
    const q = rects[k];
    if (cy <= q.t - KEEP_OUT_PAD - r || cy >= q.b + KEEP_OUT_PAD + r) continue;
    const left = q.l - KEEP_OUT_PAD - r;
    const right = q.r + KEEP_OUT_PAD + r;
    if (cx <= left || cx >= right) continue;
    const okL = left >= -r * 0.25;
    const okR = right <= vw + r * 0.25;
    let side = 0;
    if (sticky < 0 && okL) side = -1;
    else if (sticky > 0 && okR) side = 1;
    else if (okL && okR) side = cx - left <= right - cx ? -1 : 1;
    else if (okL) side = -1;
    else if (okR) side = 1;
    if (side === 0) {
      out.hide = true;
      continue;
    }
    const dx = side < 0 ? left - cx : right - cx;
    if (Math.abs(dx) > best) {
      best = Math.abs(dx);
      out.dx = dx;
      out.side = side;
    }
  }
  return out;
}
