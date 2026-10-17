// Negative and edge cases for the insight detail view: empty, huge, hostile and malformed input, plus the keyboard and
// screen-reader contract of the sheet (checked in its source, since the suite has no DOM).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { fromApi, toDetail, type TodayDetailSource } from "./detail";
import { associationLevel, levelFromLabel, levelFromScore } from "./confidence";
import type { Association } from "./associations";
import type { CoOccurrence, Recurrence } from "./patterns";

const rec = (over: Partial<Recurrence> = {}): Recurrence => ({
  event_type: "symptom", subject: "headache", occurrence_count: 3, average_confidence: 0.9,
  first_seen: "2026-10-01", last_seen: "2026-10-09", span_days: 8, ...over,
});
const co = (over: Partial<CoOccurrence> = {}): CoOccurrence => ({
  a: { event_type: "symptom", subject: "a" }, b: { event_type: "symptom", subject: "b" }, pair_count: 2, window_days: 2, interpretation: "", ...over,
});
const link = (over: Partial<Association> = {}): Association => ({
  id: "sleep_hours->mood", status: "candidate_association", strength: "weak", domains: ["sleep_hours", "mood"], lag_days: 0,
  n_days: 12, text: "On days you sleep more, your mood tends to be higher.", ...over,
} as Association);
const today = (over: Partial<TodayDetailSource> = {}): TodayDetailSource => ({ id: "t", label: "Sleep", title: "T", level: "Low", tryThis: "x", askQuestion: "q", ...over });

describe("empty and missing data", () => {
  it("says it is a gap when a pattern has no single days, and never shows an empty table", () => {
    const d = toDetail({ kind: "pattern", item: rec({ occurrences: [] }), days: 30 });
    expect("gap" in d.numbers && d.numbers.gap).toMatch(/not the single days/);
    expect("table" in d.numbers).toBe(false);
  });
  it("copes with a pattern with no occurrences field at all", () => {
    expect("gap" in toDetail({ kind: "pattern", item: rec(), days: 30 }).numbers).toBe(true);
  });
  it("copes with a correlation and a link with no pairs", () => {
    expect("gap" in toDetail({ kind: "correlation", item: co(), days: 30 }).numbers).toBe(true);
    expect("gap" in toDetail({ kind: "association", item: link({ pairs: [] }) }).numbers).toBe(true);
  });
  it("a link without domains does not crash or invent topics", () => {
    const d = toDetail({ kind: "association", item: link({ domains: undefined, pairs: [{ date: "2026-10-01", x: 1, y: 2 }] }) });
    expect("gap" in d.numbers).toBe(true);
    expect(d.ask.label).not.toContain("undefined");
  });
  it("a Today card with nothing is a gap that reads as 'not enough data', never as good news", () => {
    const d = toDetail({ kind: "today", item: today({ level: null }) });
    expect(d.sure.word).toBe("Not enough data");
    expect(d.not.join(" ")).toMatch(/not a sign that all is well/);
    expect(JSON.stringify(d)).not.toMatch(/undefined|NaN/);
  });
  it("a Today change with no percent says so", () => {
    const d = toDetail({ kind: "today", item: today({ change: { name: "sleep", current: 5, usual: 7, percent: null } }) });
    expect("table" in d.numbers && d.numbers.table.rows[0][3]).toBe("Not available");
  });
});

describe("huge data", () => {
  it("keeps one row per day and says the list is the newest N of M", () => {
    const occurrences = Array.from({ length: 14 }, (_, i) => ({ id: `e${i}`, date: `2026-10-${String(i + 1).padStart(2, "0")}` }));
    const d = toDetail({ kind: "pattern", item: rec({ occurrence_count: 400, occurrences }), days: 30 });
    if (!("table" in d.numbers)) throw new Error("table expected");
    expect(d.numbers.table.rows).toHaveLength(14);
    expect(d.numbers.table.caption).toContain("newest 14 of 400");
  });
  it("a very long subject stays text", () => {
    const d = toDetail({ kind: "pattern", item: rec({ subject: "<img src=x onerror=alert(1)>".repeat(50) }), days: 30 });
    expect(typeof d.title).toBe("string");
  });
});

describe("confidence never over-claims", () => {
  it("unknown, empty or wrongly typed labels are not a level", () => {
    for (const bad of ["", "certain", "HIGHEST", null, undefined, 3, {}]) expect(levelFromLabel(bad)).toBeNull();
  });
  it("a missing label falls back to the weak side for small counts", () => {
    expect(toDetail({ kind: "pattern", item: rec({ occurrence_count: 2, span_days: 1 }), days: 30 }).sure.word).toBe("Low");
    expect(toDetail({ kind: "correlation", item: co({ pair_count: 1 }), days: 30 }).sure.word).toBe("Low");
  });
  it("a weak, unrepeated link is never High; NaN and negative scores are Low", () => {
    expect(associationLevel("weak", "candidate_association")).toBe("Low");
    expect(associationLevel("strong", "candidate_association")).not.toBe("High");
    expect(levelFromScore(Number.NaN)).toBe("Low");
    expect(levelFromScore(-1)).toBe("Low");
  });
  it("the server word wins over the count", () => {
    expect(toDetail({ kind: "pattern", item: rec({ occurrence_count: 50, confidence_label: "low" }), days: 30 }).sure.word).toBe("Low");
  });
});

describe("fromApi rejects what it cannot read", () => {
  it("returns null for every wrong shape", () => {
    for (const bad of [undefined, null, 0, "x", [], {}, { kind: 5 }, { kind: "Pattern" }, { kind: "__proto__" }]) expect(fromApi(bad, 30)).toBeNull();
  });
});

describe("wording rules on every kind, including empty ones", () => {
  it("no authority names, no cause claims, no em dash", () => {
    const all = [
      toDetail({ kind: "pattern", item: rec(), days: 30 }),
      toDetail({ kind: "correlation", item: co(), days: 30 }),
      toDetail({ kind: "association", item: link() }),
      toDetail({ kind: "association", item: link({ domains: undefined }) }),
      toDetail({ kind: "today", item: today({ level: null }) }),
    ];
    const text = JSON.stringify(all);
    expect(text).not.toMatch(/\b(NHS|WHO|CDC|NICE|ICMR|AIIMS|studies|research shows|according to|doctors say)\b/i);
    expect(text).not.toContain("—");
    for (const d of all) expect(d.not.length).toBeGreaterThan(0);
  });
});

describe("sheet keyboard and screen-reader contract (source check)", () => {
  const src = readFileSync(new URL("./InsightDetailSheet.tsx", import.meta.url), "utf8");
  it("is a modal dialog named by its heading, which takes focus", () => {
    expect(src).toContain("showModal()");
    expect(src).toContain("aria-labelledby={titleId}");
    expect(src).toMatch(/<h2 id=\{titleId\} ref=\{headingRef\} tabIndex=\{-1\}/);
  });
  it("locks scroll and restores it, returns focus to the trigger, closes on Esc and backdrop", () => {
    expect(src).toContain('root.style.overflow = "hidden"');
    expect(src).toContain("root.style.overflow = overflow");
    expect(src).toContain("from.focus()");
    expect(src).toContain("onClose={onClose}"); // the native close event covers Esc and Android back
    expect(src).toContain("e.target === e.currentTarget");
  });
  it("every button is at least 44 px and the Details name carries the headline", () => {
    const buttons = src.match(/<button[\s\S]*?<\/button>/g) ?? [];
    expect(buttons.length).toBeGreaterThanOrEqual(3);
    for (const b of buttons) expect(b).toMatch(/min-h-\[44px\]|h-11 w-11/);
    expect(src).toContain("about {headline}");
  });
  it("the six sections are headings in the agreed order", () => {
    const order = ["-saw", "-numbers", "-sure", "-not", "-try", "-ask"].map((k) => src.indexOf("${titleId}" + k));
    expect(order.every((i) => i > 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });
  it("the deep link is read once and removed from the address", () => {
    expect(src).toContain('url.searchParams.delete("item")');
    expect(src).toContain("window.history.replaceState");
  });
});
