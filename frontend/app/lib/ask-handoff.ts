/**
 * Hand a question from anywhere in the app to the companion chat without putting health text in the URL.
 *
 * A short question travels as `?ask=`. Anything longer (a daily log can run to 8,000 characters) is stored under a
 * short key and only the key travels, as `?askref=`. The companion page reads the key once and clears it. The
 * text lives in sessionStorage, with an in-memory copy for when storage is blocked: the hand-off is a client-side
 * navigation, so module state survives it.
 */

/** Longest question that may appear in the URL. */
export const ASK_INLINE_MAX = 200;

const STORAGE_PREFIX = "bubbles:ask:";

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const memory = new Map<string, string>();

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null; // blocked storage can throw on access, not only on read
  }
}

/** The /companion URL that will open with `question` sent to Bubbles. */
export function askHref(question: string, store: Store | null = browserStore()): string {
  const text = question.trim();
  if (text.length <= ASK_INLINE_MAX) return `/companion?ask=${encodeURIComponent(text)}`;

  const key = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  memory.set(key, text);
  try {
    store?.setItem(STORAGE_PREFIX + key, text);
  } catch {
    // The in-memory copy still covers the client-side navigation.
  }
  return `/companion?askref=${key}`;
}

/** Identifies the hand-off in a URL, so the page can tell whether it already handled it. */
export function askHandle(params: URLSearchParams): string | null {
  return params.get("ask") || params.get("askref") || null;
}

/** The question carried by the URL, or null. A stored question is removed as it is read. */
export function readAsk(params: URLSearchParams, store: Store | null = browserStore()): string | null {
  const inline = params.get("ask");
  if (inline) return inline;
  const key = params.get("askref");
  if (!key) return null;

  let text = memory.get(key) ?? null;
  memory.delete(key);
  try {
    text ??= store?.getItem(STORAGE_PREFIX + key) ?? null;
    store?.removeItem(STORAGE_PREFIX + key);
  } catch {
    // Unreadable storage: fall back to whatever the in-memory copy gave us.
  }
  return text;
}
