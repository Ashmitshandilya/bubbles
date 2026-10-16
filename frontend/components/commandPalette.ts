/**
 * Pure logic for the "Ask or jump" command palette: which destinations exist, how a typed query ranks them, and the
 * recent-destinations store. No React and no DOM, so it runs under plain vitest.
 *
 * Privacy: the recent store keeps route ids only. A typed query (which can be a health question) is never persisted.
 */

export type NavTab = { label: string; href: string };
export type NavSection = { id: string; label: string; href: string; tabs?: readonly NavTab[] };

export type PaletteItem = {
  /** Stable route id: `tab:/sleep`, `section:track` or `action:log-water`. This is all that is ever stored. */
  id: string;
  label: string;
  /** Secondary line: the section a page lives in, or what kind of row this is. */
  hint: string;
  href: string;
  kind: "tab" | "section" | "action";
  /** Section name, matched together with the label ("Sleep, Track"). */
  section: string;
};

export type AskRow = { id: "ask"; kind: "ask"; label: string; hint: string; question: string };
export type PaletteRow = PaletteItem | AskRow;

/** Links that already exist; no new routes. */
const QUICK_ACTIONS: readonly { slug: string; label: string; href: string }[] = [
  { slug: "log-water", label: "Log water", href: "/hydration" },
  { slug: "log-sleep", label: "Log sleep", href: "/sleep" },
  { slug: "log-mood", label: "Log mood", href: "/mood" },
  { slug: "new-conversation", label: "New chat", href: "/companion?new=1" },
  { slug: "open-today", label: "Open Today", href: "/dashboard" },
  { slug: "partner-sharing", label: "Partner sharing", href: "/partner" },
  { slug: "settings", label: "Settings", href: "/settings" },
];

/** Lowercase, accent-free, single-spaced. */
export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Every tab of every section, plus a row for each section that has no tab of its own name (Today, Talk, Track, Fitness,
 * Care), plus the quick actions. A quick action that is exactly an existing tab (same label and link) is not repeated.
 */
export function buildItems(sections: readonly NavSection[]): PaletteItem[] {
  const pages: PaletteItem[] = [];
  for (const section of sections) {
    const tabs = section.tabs ?? [];
    if (!tabs.some((tab) => normalize(tab.label) === normalize(section.label))) {
      pages.push({ id: `section:${section.id}`, label: section.label, hint: "Section", href: section.href, kind: "section", section: section.label });
    }
    for (const tab of tabs) {
      pages.push({ id: `tab:${tab.href}`, label: tab.label, hint: section.label, href: tab.href, kind: "tab", section: section.label });
    }
  }
  const actions: PaletteItem[] = QUICK_ACTIONS.filter(
    (a) => !pages.some((p) => p.kind === "tab" && p.href === a.href && normalize(p.label) === normalize(a.label)),
  ).map((a) => ({ id: `action:${a.slug}`, label: a.label, hint: "Quick action", href: a.href, kind: "action", section: "" }));
  return [...actions, ...pages];
}

function isSubsequence(needle: string, haystack: string): boolean {
  let i = 0;
  for (const ch of haystack) if (ch === needle[i] && ++i === needle.length) return true;
  return false;
}

/** Lower is better; null means no match. 0 prefix, 1 word prefix, 2 substring, 3 loose subsequence, 4 label + section words. */
function score(item: PaletteItem, q: string): number | null {
  const label = normalize(item.label);
  if (label.startsWith(q)) return 0;
  if (` ${label}`.includes(` ${q}`)) return 1;
  if (label.includes(q)) return 2;
  const squeezed = q.replace(/ /g, "");
  if (squeezed.length >= 3 && isSubsequence(squeezed, label)) return 3;
  const words = `${label} ${normalize(item.section)}`.split(" ");
  if (q.split(" ").every((token) => words.some((word) => word.startsWith(token)))) return 4;
  return null;
}

/** Matching items, best first; ties keep their original order. An empty query returns the items unchanged. */
export function rank(items: readonly PaletteItem[], query: string): PaletteItem[] {
  const q = normalize(query);
  if (!q) return [...items];
  return items
    .map((item, index) => ({ item, index, s: score(item, q) }))
    .filter((r): r is { item: PaletteItem; index: number; s: number } => r.s !== null)
    .sort((a, b) => a.s - b.s || a.index - b.index)
    .map((r) => r.item);
}

/** A typed question rather than a page name: 3+ characters with a space or a question mark. */
export function isQuestionLike(query: string): boolean {
  const text = query.trim();
  return text.length >= 3 && (/\s/.test(text) || text.includes("?"));
}

/**
 * The rows the palette shows. Empty query: recent destinations, then the quick actions. Otherwise: "Ask Bubbles: ..."
 * first when the text looks like a question, then ranked destinations. With no match at all the Ask row stands alone, so
 * free text always still asks Bubbles.
 */
export function buildRows(items: readonly PaletteItem[], query: string, recentIds: readonly string[] = []): PaletteRow[] {
  const text = query.trim();
  if (!text) {
    const recent = recentIds.map((id) => items.find((i) => i.id === id)).filter((i): i is PaletteItem => !!i);
    const seen = new Set(recent.map((i) => i.id));
    return [
      ...recent.map((i) => ({ ...i, hint: `Recent, ${i.section || i.hint}` })),
      ...items.filter((i) => i.kind === "action" && !seen.has(i.id)),
    ];
  }
  const ask: AskRow = { id: "ask", kind: "ask", label: `Ask Bubbles: ${text}`, hint: "Ask in chat", question: text };
  const matches = rank(items, text);
  return isQuestionLike(text) || matches.length === 0 ? [ask, ...matches] : matches;
}

// ---- Recent destinations (route ids only) ----

export const RECENTS_KEY = "bubbles.palette.recent";
export const RECENTS_MAX = 5;

type Store = Pick<Storage, "getItem" | "setItem">;

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // blocked storage can throw on access, not only on read
  }
}

export function loadRecents(store: Store | null = browserStore()): string[] {
  try {
    const parsed: unknown = JSON.parse(store?.getItem(RECENTS_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string").slice(0, RECENTS_MAX) : [];
  } catch {
    return [];
  }
}

/**
 * Remember a visited destination, newest first, at most RECENTS_MAX. Only an id that belongs to `items` is stored, so
 * nothing the user typed can ever reach localStorage. Returns the new list even when storage is unavailable.
 */
export function recordRecent(id: string, items: readonly PaletteItem[], store: Store | null = browserStore()): string[] {
  const current = loadRecents(store);
  if (!items.some((i) => i.id === id)) return current;
  const next = [id, ...current.filter((r) => r !== id)].slice(0, RECENTS_MAX);
  try {
    store?.setItem(RECENTS_KEY, JSON.stringify(next));
  } catch {
    // not remembered; the palette still works
  }
  return next;
}
