// Privacy veil: blur health values and chat text when the tab is out of sight, until the person taps to show them.
// Pure parts only (setting storage and the cover/reveal rules); components/PrivacyVeil.tsx wires them to the page.

export const VEIL_KEY = "bubbles.privacy-veil";

/** Just what we use from localStorage, so tests can pass a plain object. */
export type VeilStore = Pick<Storage, "getItem" | "setItem">;

/** Default OFF: only an explicit "1" turns it on. Storage can throw (private windows, blocked site data). */
export function readVeilSetting(store: VeilStore | null): boolean {
  try {
    return store?.getItem(VEIL_KEY) === "1";
  } catch {
    return false;
  }
}

/** false = not remembered (the choice still applies until the page closes). */
export function writeVeilSetting(store: VeilStore | null, on: boolean): boolean {
  try {
    if (!store) return false;
    store.setItem(VEIL_KEY, on ? "1" : "0");
    return true;
  } catch {
    return false;
  }
}

/**
 * away   = the tab was hidden or the window lost focus: cover.
 * toggle = the Hide button: flip.
 * reveal = a tap on a covered value: uncover. Coming back to the tab does NOT uncover; only a tap or the button does.
 */
export type CoverEvent = "away" | "toggle" | "reveal";

export function nextCover(covered: boolean, event: CoverEvent): boolean {
  return event === "away" ? true : event === "reveal" ? false : !covered;
}

/** Values are blurred only when the setting is on AND something covered them. */
export function isVeiled(enabled: boolean, covered: boolean): boolean {
  return enabled && covered;
}
