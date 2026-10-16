/**
 * Remembering a "No, not now" on this device, so the outside-AI question is not put again on every message.
 * The server's consent record is the real answer; this only keeps the screen calm between visits, and the
 * question comes back after 14 days. A per-viewer convenience: every storage call can fail and is allowed to.
 */
export const DECLINE_KEY = "bubbles:ai-decline-at";
export const DECLINE_DAYS = 14;

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** True while a stored decline is younger than DECLINE_DAYS. Junk, a future date or nothing counts as not declined. */
export function declineActive(raw: string | null, now: number = Date.now()): boolean {
  const at = raw ? Date.parse(raw) : NaN;
  if (!Number.isFinite(at) || at > now) return false;
  return now - at < DECLINE_DAYS * 86_400_000;
}

export function readDecline(store: Store | null = browserStore(), now: number = Date.now()): boolean {
  try {
    return declineActive(store?.getItem(DECLINE_KEY) ?? null, now);
  } catch {
    return false;
  }
}

export function writeDecline(store: Store | null = browserStore(), now: number = Date.now()): void {
  try {
    store?.setItem(DECLINE_KEY, new Date(now).toISOString());
  } catch {
    // storage blocked: the decline still holds for this page
  }
}

export function clearDecline(store: Store | null = browserStore()): void {
  try {
    store?.removeItem(DECLINE_KEY);
  } catch {
    // nothing to clear
  }
}
