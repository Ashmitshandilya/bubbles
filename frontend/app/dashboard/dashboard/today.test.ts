// Run: npx vitest run app/dashboard/dashboard/today.test.ts
import { describe, expect, it } from "vitest";
import { buildPatterns, buildTodayItems, daysAgo, livingSignalLine, plainMetric, summarizeCycle, summarizeSignal, upcomingVisits } from "./today";
import type { TrackerEntry } from "./types";

const now = new Date(2026, 9, 6, 9, 0); // 6 Oct 2026, local time
const day = (ago: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - ago);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const sleep = (ago: number, duration: number): TrackerEntry => ({ id: `s${ago}`, date: day(ago), duration });

describe("today derivations", () => {
  it("counts calendar days for date-only and future values", () => {
    expect(daysAgo(day(0), now)).toBe(0);
    expect(daysAgo(day(3), now)).toBe(3);
    expect(daysAgo(day(-2), now)).toBe(-2);
    expect(Number.isNaN(daysAgo("not a date", now))).toBe(true);
  });

  it("flags a change only with enough days on both sides", () => {
    const usual = [8, 9, 10, 11, 12, 13].map((ago) => sleep(ago, 7.5));
    const short = [0, 1, 2].map((ago) => sleep(ago, 5.5));
    const s = summarizeSignal("sleep", [...short, ...usual], now);
    expect(s.value).toBe("5.5\u00A0h");
    expect(s.change?.direction).toBe("down");
    expect(s.change?.confidence).toBe("low");
    expect(s.detail).toBe("Below your usual 7.5\u00A0h");

    const thin = summarizeSignal("sleep", [...short, sleep(9, 7.5)], now);
    expect(thin.change).toBeUndefined();
    expect(thin.detail).toBe("Average of 3 logged nights");
  });

  it("shows gaps honestly and never invents values", () => {
    const empty = summarizeSignal("hydration", [], now);
    expect(empty.value).toBeUndefined();
    expect(empty.logged).toBe(false);
    expect(empty.bars).toEqual([0, 0, 0, 0, 0, 0, 0]);

    const items = buildTodayItems([empty, summarizeSignal("sleep", [], now)], null, []);
    expect(items.map((i) => i.id)).toEqual(["gap-hydration", "gap-sleep"]);
    expect(items[0].primary).toBe("add-water");
  });

  it("predicts the next period only from the backend summary", () => {
    const cycle = summarizeCycle(
      { entries: [{ id: "c1", date: day(26), phase: "period" }], summary: { period_start_count: 3, last_period: day(26), average_cycle_length: 28, next_predicted: day(-2) } },
      now,
    );
    expect(cycle.day).toBe(27);
    expect(cycle.daysUntil).toBe(2);
    expect(buildTodayItems([], cycle, [])[0].id).toBe("cycle-next");

    const none = summarizeCycle({ entries: [], summary: { period_start_count: 0 } }, now);
    expect(none.logged).toBe(false);
    expect(none.value).toBeUndefined();
  });

  it("lists upcoming visits soonest first", () => {
    const visits = upcomingVisits([{ id: "a", date: day(-10) }, { id: "b", date: day(5) }, { id: "c", date: day(-1) }], now);
    expect(visits.map((v) => v.id)).toEqual(["c", "a"]);
  });
});

describe("living map wording", () => {
  it("reads metric ids with underscores or spaces", () => {
    expect(plainMetric("sleep_hours")).toBe("sleep");
    expect(plainMetric("Water ml")).toBe("water intake");
    expect(plainMetric("resting heart rate bpm")).toBe("resting heart rate");
  });

  it("says a baseline change in plain words and never claims a cause", () => {
    expect(livingSignalLine({ kind: "baseline_change", direction: "down", evidence: "observed personal-baseline deviation" })).toBe("Lower than your usual lately.");
    expect(livingSignalLine({ kind: "baseline_change", direction: "up", evidence: "" })).toBe("Higher than your usual lately.");
    expect(livingSignalLine({ kind: "repeated_cooccurrence", direction: "context", evidence: "" })).toMatch(/not proof/);
    expect(livingSignalLine({ kind: "something_new", evidence: "As sent" })).toBe("As sent");
  });
});

describe("insight ids and details on Today", () => {
  it("keeps the server id and its one confidence word for a weekly insight and a correlation", () => {
    const [insight, corr] = buildPatterns(
      [{ id: "rec:symptom:headache", confidence_label: "medium", title: "Headache came up 5 times", description: "d", category: "recurring_symptom", confidence: 0.9 } as never],
      [{ id: "co:a|b", confidence_label: "low", kind: "co", pair_count: 3, strength: 0.4, interpretation: "A and B show up together" } as never],
    );
    expect(insight.insightId).toBe("rec:symptom:headache");
    expect(insight.pill.text).toBe("Medium confidence");
    expect(insight.source.level).toBe("Medium");
    expect(corr.insightId).toBe("co:a|b");
    expect(corr.source.level).toBe("Low");
  });

  it("falls back to a positional id and the score when an older server sends neither", () => {
    const [insight] = buildPatterns([{ title: "t", description: "d", category: "c", confidence: 0.8 } as never], []);
    expect(insight.id).toBe("insight-0");
    expect(insight.insightId).toBeUndefined();
    expect(insight.pill.text).toBe("High confidence");
  });

  it("gives a chat-derived card this week against the usual from the brief", () => {
    const [item] = buildTodayItems([], null, [{ id: "review-sleep_hours", priority: "high" } as never], {
      sleep_hours: { current: 5.5, baseline: 7, percent: -21.4 },
    });
    expect(item.source.change).toEqual({ name: plainMetric("sleep_hours"), current: 5.5, usual: 7, percent: -21.4 });
    expect(item.source.level).toBe("Low");
  });
});
