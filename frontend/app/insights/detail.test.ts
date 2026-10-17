// Run: npx vitest run app/insights/detail.test.ts
import { describe, expect, it } from "vitest";
import { fromApi, goneMessage, toDetail, type TodayDetailSource } from "./detail";
import type { Association } from "./associations";
import type { CoOccurrence, Recurrence } from "./patterns";

const pattern: Recurrence = {
  id: "rec:symptom:headache",
  confidence_label: "medium",
  occurrences: [
    { id: "e1", date: "2026-10-10" },
    { id: "e2", date: "2026-10-10" },
    { id: "e3", date: "2026-10-03" },
  ],
  event_type: "symptom",
  subject: "headache",
  occurrence_count: 5,
  average_confidence: 0.8,
  first_seen: "2026-09-20",
  last_seen: "2026-10-10",
  span_days: 20,
};

const together: CoOccurrence = {
  id: "co:symptom:headache|symptom:poor sleep",
  confidence_label: "low",
  pairs: [{ a: { id: "a1", date: "2026-10-10" }, b: { id: "b1", date: "2026-10-09" } }],
  a: { event_type: "symptom", subject: "headache" },
  b: { event_type: "symptom", subject: "poor sleep" },
  pair_count: 3,
  window_days: 2,
  interpretation: "Headache and poor sleep were logged close together.",
};

const link: Association = {
  id: "sleep_hours->mood",
  status: "repeated_pattern",
  strength: "moderate",
  domains: ["sleep_hours", "mood"],
  lag_days: 1,
  n_days: 21,
  text: "On days you sleep more, your mood tends to be higher the next day.",
  repeated: true,
  limitations: ["Fewer than 30 days of data."],
  pairs: [{ date: "2026-10-10", x: 7.5, y: 4 }],
};

const today: TodayDetailSource = {
  id: "review-sleep_hours",
  label: "Sleep",
  title: "Your sleep has moved compared with your usual.",
  body: "From chat.",
  level: "Low",
  tryThis: "Log sleep.",
  askQuestion: "What changed in my sleep?",
  change: { name: "sleep", current: 5.5, usual: 7, percent: -21.4 },
};

const SECTION_KEYS = ["id", "kindLabel", "title", "saw", "numbers", "sure", "not", "tryThis", "ask"];

describe("toDetail", () => {
  it("returns the same sections for every kind", () => {
    for (const input of [
      { kind: "pattern", item: pattern, days: 30 },
      { kind: "correlation", item: together, days: 30 },
      { kind: "association", item: link },
      { kind: "today", item: today },
    ] as const) {
      const detail = toDetail(input);
      expect(Object.keys(detail)).toEqual(SECTION_KEYS);
      expect(detail.not.length).toBeGreaterThan(0);
      expect(detail.ask.href).toContain("/companion?ask=");
    }
  });

  it("builds a pattern table of days with entry counts, newest first", () => {
    const detail = toDetail({ kind: "pattern", item: pattern, days: 30 });
    expect(detail.id).toBe("rec:symptom:headache");
    expect(detail.sure.word).toBe("Medium");
    if (!("table" in detail.numbers)) throw new Error("expected a table");
    expect(detail.numbers.table.head).toEqual(["Day", "Entries"]);
    expect(detail.numbers.table.rows.map((r) => r[1])).toEqual(["2", "1"]);
    expect(detail.numbers.table.caption).toContain("Showing the newest 3 of 5");
  });

  it("says out loud when the single days are missing", () => {
    const detail = toDetail({ kind: "pattern", item: { ...pattern, occurrences: undefined }, days: 30 });
    expect(detail.numbers).toEqual({ gap: expect.stringContaining("not the single days") });
  });

  it("lists pairs with the gap in days", () => {
    const detail = toDetail({ kind: "correlation", item: together, days: 30 });
    if (!("table" in detail.numbers)) throw new Error("expected a table");
    expect(detail.numbers.table.rows[0][2]).toBe("1");
    expect(detail.sure.word).toBe("Low");
  });

  it("uses the engine's own limits for what a link does not mean and states the lag", () => {
    const detail = toDetail({ kind: "association", item: link });
    expect(detail.not).toEqual(["Fewer than 30 days of data."]);
    if (!("table" in detail.numbers)) throw new Error("expected a table");
    expect(detail.numbers.table.caption).toContain("the next day");
    expect(detail.numbers.table.head[1]).toContain("(hours)");
    expect(detail.sure.word).toBe("High");
  });

  it("shows this week against the usual on a Today card and a gap card says it is a gap", () => {
    const detail = toDetail({ kind: "today", item: today });
    if (!("table" in detail.numbers)) throw new Error("expected a table");
    expect(detail.numbers.table.rows[0]).toEqual(["Sleep", "5.5", "7", "-21.4%"]);
    const gap = toDetail({ kind: "today", item: { ...today, change: undefined, level: null } });
    expect(gap.sure.word).toBe("Not enough data");
    expect(gap.not[0]).toMatch(/gap is not a sign/i);
  });

  it("never names an authority or claims a cause or a diagnosis", () => {
    const text = JSON.stringify([
      toDetail({ kind: "pattern", item: pattern, days: 30 }),
      toDetail({ kind: "correlation", item: together, days: 30 }),
      toDetail({ kind: "association", item: link }),
      toDetail({ kind: "today", item: today }),
    ]);
    expect(text).not.toMatch(/\b(NHS|WHO|CDC|NICE|studies show|according to)\b/);
    expect(text).not.toContain("—");
  });
});

describe("fromApi", () => {
  it("maps the endpoint's kind to a detail input and rejects anything else", () => {
    expect(fromApi({ kind: "pattern", ...pattern }, 30)?.kind).toBe("pattern");
    expect(fromApi({ kind: "correlation", ...together }, 30)?.kind).toBe("correlation");
    expect(fromApi({ kind: "association", ...link }, 90)?.kind).toBe("association");
    expect(fromApi({ kind: "other" }, 30)).toBeNull();
    expect(fromApi(null, 30)).toBeNull();
  });

  it("words a stale link plainly", () => {
    expect(goneMessage(30)).toBe("This pattern is no longer in the last 30 days.");
  });
});
