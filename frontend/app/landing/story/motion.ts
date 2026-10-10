/**
 * "Pause motion" (WCAG 2.2.2: moving content that lasts more than five seconds needs a way to stop it).
 *
 * One flag, `story.paused`, is read by everything that moves on its own clock (the sky drift, the soap bubbles,
 * the spine, the fireflies); the page attribute `data-paused` tells the CSS to settle every loop and entrance
 * animation (landing.css). Scrolling still scrubs the story: that motion belongs to the visitor.
 *
 * The choice is remembered in localStorage. Storage can be missing or throw (private windows, blocked site
 * data), so every access is guarded and the page works without it.
 */
import { story } from "./store";

export const PAUSE_STORAGE_KEY = "bubbles-pause-motion";

type Read = Pick<Storage, "getItem">;
type Write = Pick<Storage, "setItem" | "removeItem">;

/** `window.localStorage`, or null where reading the property itself throws. */
export function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readPaused(storage: Read | null | undefined): boolean {
  try {
    return storage?.getItem(PAUSE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function writePaused(storage: Write | null | undefined, paused: boolean) {
  try {
    if (paused) storage?.setItem(PAUSE_STORAGE_KEY, "1");
    else storage?.removeItem(PAUSE_STORAGE_KEY);
  } catch {
    // blocked or full storage: the choice just is not remembered
  }
}

/** The page element that carries `data-paused` (anything with `toggleAttribute`, so tests need no DOM). */
type Root = Pick<Element, "toggleAttribute">;

/**
 * Apply a pause choice everywhere it matters: the story flag, the page attribute and (when `remember`) storage.
 * Returns the new value so a caller can mirror it in its own state.
 */
export function applyPaused(root: Root | null, paused: boolean, remember: boolean, storage: Write | null = browserStorage()): boolean {
  story.paused = paused;
  root?.toggleAttribute("data-paused", paused);
  if (remember) writePaused(storage, paused);
  return paused;
}

/** At the start of a visit: restore the remembered choice (nothing is stored until the visitor chooses once). */
export function restorePaused(root: Root | null, storage: Read | null = browserStorage()): boolean {
  return applyPaused(root, readPaused(storage), false);
}
