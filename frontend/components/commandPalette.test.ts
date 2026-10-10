import { describe, expect, it, vi } from "vitest";

vi.mock("./Providers", () => ({ useApi: () => ({}), useAuth: () => ({}) }));
vi.mock("next/navigation", () => ({ usePathname: () => "/sleep", useRouter: () => ({}) }));
vi.mock("next/link", () => ({ default: () => null }));
vi.mock("./AskBubbles", () => ({ AskBubbles: () => null }));
vi.mock("./BubblesMascot", () => ({ BubblesMascot: () => null }));
vi.mock("./wellness/NotificationBell", () => ({ NotificationBell: () => null }));

import { ME, SECTIONS } from "./Navigation";
import {
  RECENTS_KEY,
  RECENTS_MAX,
  buildItems,
  buildRows,
  isQuestionLike,
  loadRecents,
  normalize,
  rank,
  recordRecent,
  type PaletteItem,
} from "./commandPalette";

const items = buildItems([...SECTIONS, ME]);
const labels = (list: readonly { label: string }[]) => list.map((i) => i.label);

function memoryStore(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (k: string) => data[k] ?? null,
    setItem: (k: string, v: string) => {
      data[k] = v;
    },
  };
}

describe("buildItems", () => {
  it("covers every section tab exactly once", () => {
    for (const section of [...SECTIONS, ME]) {
      for (const tab of section.tabs ?? []) {
        const hits = items.filter((i) => i.kind === "tab" && i.href === tab.href);
        expect(hits, `${section.label} / ${tab.label}`).toHaveLength(1);
        expect(hits[0].label).toBe(tab.label);
        expect(hits[0].section).toBe(section.label);
      }
    }
  });

  it("reaches every section, by its own row or a tab with the same name", () => {
    for (const section of [...SECTIONS, ME]) {
      const own = items.some((i) => i.kind === "section" && i.href === section.href && i.label === section.label);
      const namesake = items.some((i) => i.kind === "tab" && i.label === section.label && i.section === section.label);
      expect(own || namesake, section.label).toBe(true);
    }
  });

  it("has unique ids and the quick actions, without repeating a tab", () => {
    expect(new Set(items.map((i) => i.id)).size).toBe(items.length);
    const actions = items.filter((i) => i.kind === "action");
    expect(labels(actions)).toEqual(["Log water", "Log sleep", "Log mood", "New conversation", "Open Today"]);
    expect(items.filter((i) => i.label === "Settings")).toHaveLength(1);
    expect(items.filter((i) => i.label === "Partner sharing")).toHaveLength(1);
  });
});

describe("rank", () => {
  const sample: PaletteItem[] = [
    ["a", "Subsleep"], // substring
    ["b", "Deep sleep log"], // word prefix
    ["c", "Sleep"], // prefix
    ["d", "Sleeping habits"], // prefix, later than c
    ["e", "Stale loop prep"], // subsequence s-l-e-e-p? s,l,e,e,p
    ["f", "Weight"], // no match
  ].map(([id, label]) => ({ id, label, hint: "", href: `/${id}`, kind: "tab", section: "" }));

  it("orders prefix, word prefix, substring, then loose subsequence, keeping ties stable", () => {
    expect(labels(rank(sample, "sleep"))).toEqual(["Sleep", "Sleeping habits", "Deep sleep log", "Subsleep", "Stale loop prep"]);
  });

  it("ignores case and accents, in the query and in the label", () => {
    const cafe: PaletteItem[] = [{ id: "x", label: "Café Résumé", hint: "", href: "/x", kind: "tab", section: "" }];
    expect(rank(cafe, "CAFE")).toHaveLength(1);
    expect(rank(cafe, "résumé")).toHaveLength(1);
    expect(normalize("  É   Ü ")).toBe("e u");
  });

  it("matches the section name too, and returns everything for an empty query", () => {
    expect(rank(items, "sleep track").map((i) => i.id)).toContain("tab:/sleep");
    const track = rank(items, "track").filter((i) => i.kind === "tab");
    expect(track.length).toBeGreaterThanOrEqual(9);
    expect(rank(items, "   ")).toHaveLength(items.length);
  });

  it("puts a page named like the query first", () => {
    expect(rank(items, "sleep")[0].id).toBe("tab:/sleep");
    expect(rank(items, "log w")[0].label).toBe("Log water");
  });
});

describe("buildRows", () => {
  it("leads with the Ask row for a question-like query, then destinations", () => {
    const rows = buildRows(items, "log w");
    expect(rows[0]).toMatchObject({ kind: "ask", label: "Ask Bubbles: log w" });
    expect(rows[1].label).toBe("Log water");
    expect(rows.length).toBeGreaterThan(1);
  });

  it("does not lead with Ask for a short page name", () => {
    expect(buildRows(items, "sleep")[0].kind).not.toBe("ask");
    expect(isQuestionLike("hi")).toBe(false);
    expect(isQuestionLike("ok?")).toBe(true);
    expect(isQuestionLike("a b")).toBe(true);
  });

  it("falls back to the Ask row alone when nothing matches", () => {
    const rows = buildRows(items, "zzzqq");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: "ask", question: "zzzqq" });
  });

  it("shows recents first, then quick actions, for an empty query", () => {
    const rows = buildRows(items, "", ["tab:/mood", "bogus", "action:log-water"]);
    expect(rows.slice(0, 2).map((r) => r.id)).toEqual(["tab:/mood", "action:log-water"]);
    expect(rows.filter((r) => r.id === "action:log-water")).toHaveLength(1);
    expect(rows.every((r) => r.kind !== "ask")).toBe(true);
  });
});

describe("recent items", () => {
  it("keeps the newest five route ids, without duplicates", () => {
    const store = memoryStore();
    const ids = items.slice(0, 8).map((i) => i.id);
    for (const id of ids) recordRecent(id, items, store);
    recordRecent(ids[5], items, store);
    const saved = loadRecents(store);
    expect(saved).toHaveLength(RECENTS_MAX);
    expect(saved[0]).toBe(ids[5]);
    expect(new Set(saved).size).toBe(RECENTS_MAX);
  });

  it("never stores free text: unknown ids are dropped and only route ids reach storage", () => {
    const store = memoryStore();
    const typed = "my chest hurts when I run";
    recordRecent(typed, items, store);
    recordRecent("ask", items, store);
    expect(store.data[RECENTS_KEY]).toBeUndefined();

    recordRecent("tab:/sleep", items, store);
    const raw = store.data[RECENTS_KEY];
    expect(JSON.parse(raw)).toEqual(["tab:/sleep"]);
    expect(raw).not.toContain("chest");
  });

  it("survives blocked or corrupt storage", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(loadRecents(broken)).toEqual([]);
    expect(recordRecent("tab:/sleep", items, broken)).toEqual(["tab:/sleep"]);
    expect(loadRecents(memoryStore({ [RECENTS_KEY]: "{not json" }))).toEqual([]);
    expect(loadRecents(memoryStore({ [RECENTS_KEY]: '[1,"tab:/sleep",null]' }))).toEqual(["tab:/sleep"]);
    expect(loadRecents(null)).toEqual([]);
  });
});
