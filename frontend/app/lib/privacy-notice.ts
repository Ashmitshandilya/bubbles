/** The small storage notice. Bubbles sets no tracking or advertising cookies and loads no analytics, so this is a notice with one button, not a consent wall. */

export const NOTICE_KEY = "bubbles.notice.v1";

/** Anything with the two storage methods we use; a real Storage, a test double, or null when storage is blocked. */
export type NoticeStore = Pick<Storage, "getItem" | "setItem"> | null;

/** True when the notice should be shown: it has not been dismissed yet. Storage that is missing or throws counts as "not dismissed". */
export function shouldShowNotice(store: NoticeStore): boolean {
  try {
    return store?.getItem(NOTICE_KEY) !== "1";
  } catch {
    return true;
  }
}

/** Remembers the dismissal. Failure is fine: the notice then simply appears again next visit. */
export function dismissNotice(store: NoticeStore): void {
  try {
    store?.setItem(NOTICE_KEY, "1");
  } catch {
    /* storage is blocked or full */
  }
}

/** The browser's localStorage, or null where even reading the property throws (some privacy modes). */
export function browserStore(): NoticeStore {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** The notice is for first-time visitors: the home page, sign-in, the legal pages and share links. It stays out of the signed-in app. */
export function noticeBelongsOn(pathname: string): boolean {
  return pathname === "/" || ["/login", "/privacy", "/terms"].includes(pathname) || pathname.startsWith("/partner/") || pathname.startsWith("/cycle/partner/");
}

export const NOTICE_TEXT =
  "Bubbles keeps only what it needs in your browser: your sign-in and your settings. There are no ads, no tracking cookies and no analytics.";
