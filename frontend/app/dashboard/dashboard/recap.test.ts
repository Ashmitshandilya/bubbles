/**
 * Checks for the "Your week" recap. Run: npx vitest run app/dashboard/dashboard/recap.test.ts
 * Built from /insights/weekly only: a missing record is a gap, and no line may imply a cause, a diagnosis or a dose.
 */
import { describe, expect, it } from "vitest";
import { buildWeekRecap, RECAP_DISCLAIMER } from "./recap";
import type { InsightItem, WeeklyInsights } from "./types";

const insight = (over: Partial<InsightItem>): InsightItem => ({
  title: "Repeated headache",
  description: "Headache was logged 4 times. This is a recurring observation worth watching over time.",
  category: "recurrence",
  confidence: 0.5,
  supporting_events: [],
  actionable: false,
  ...over,
});

const weekly = (over: Partial<WeeklyInsights> = {}): WeeklyInsights => ({
  insights: [],
  disclaimer: "Observations only.",
  data_quality: { event_count: 8, sufficient_for_pattern_detection: true },
  trend: { signals: [{ event_type: "sleep", count: 4 }, { event_type: "mood", count: 2 }, { event_type: "food", count: 2 }] },
  ...over,
});

describe("buildWeekRecap highlights", () => {
  it("counts the week, names the most recorded signals and quotes one pattern, three lines at most", () => {
    const recap = buildWeekRecap(weekly({ insights: [insight({}), insight({ description: "Cramps was logged 3 times. More text." })] }));
    expect(recap?.highlights).toEqual([
      "Bubbles recorded 8 entries this week.",
      "Most recorded: sleep (4) and mood (2).",
      "Headache was logged 4 times.",
    ]);
  });

  it("marks an association as seen together, not as a cause", () => {
    const recap = buildWeekRecap(weekly({
      trend: null,
      insights: [insight({ category: "association", description: "headache and poor sleep were recorded within 2 days of each other 3 times. This is a temporal association, not proof of causation." })],
    }));
    expect(recap?.highlights.at(-1)).toBe("headache and poor sleep were recorded within 2 days of each other 3 times. Seen together, not a cause.");
  });

  it("singular entry and unknown event types read naturally", () => {
    const recap = buildWeekRecap(weekly({ data_quality: { event_count: 1, sufficient_for_pattern_detection: false }, trend: { signals: [{ event_type: "heart_rate_note", count: 1 }] } }));
    expect(recap?.highlights).toEqual(["Bubbles recorded 1 entry this week.", "Most recorded: heart rate note (1)."]);
  });

  it("drops lines that mention causes, diagnoses or doses instead of rewording them", () => {
    const risky = [
      "Headache caused by coffee was logged 3 times.",
      "Took 500 mg of ibuprofen was logged 3 times.",
      "Migraine diagnosis was logged 3 times.",
      "Fever due to flu was logged 3 times.",
      "Antibiotic dose was logged 3 times.",
    ];
    const recap = buildWeekRecap(weekly({ trend: null, insights: risky.map((description) => insight({ description })) }));
    expect(recap?.highlights).toEqual(["Bubbles recorded 8 entries this week."]);
  });

  it("ignores the backend data_gap item and over-long lines", () => {
    const recap = buildWeekRecap(weekly({
      trend: null,
      insights: [
        insight({ category: "data_gap", description: "Bubbles doesn't have enough recent health data." }),
        insight({ description: `${"very long ".repeat(30)}was logged 3 times.` }),
      ],
    }));
    expect(recap?.highlights).toEqual(["Bubbles recorded 8 entries this week."]);
  });
});

describe("buildWeekRecap gap and next step", () => {
  it("an empty week has no highlights and says so as a gap", () => {
    const recap = buildWeekRecap(weekly({ data_quality: { event_count: 0, sufficient_for_pattern_detection: false }, trend: { signals: [{ event_type: "sleep", count: 5 }] } }));
    expect(recap?.highlights).toEqual([]);
    expect(recap?.gap).toMatch(/^Nothing was recorded in the last 7 days/);
    expect(recap?.gap).toMatch(/not a sign that all is well/);
    expect(recap?.tryNext).toBe("Tell Bubbles about one day, even in a sentence.");
  });

  it("too few entries: no pattern claims, a gap about volume", () => {
    const recap = buildWeekRecap(weekly({ data_quality: { event_count: 2, sufficient_for_pattern_detection: false } }));
    expect(recap?.gap).toBe("Only 2 entries this week, which is too few to look for patterns.");
  });

  it("names up to two everyday signals with no record and suggests logging the first", () => {
    const recap = buildWeekRecap(weekly({ trend: { signals: [{ event_type: "symptom", count: 5 }] } }));
    expect(recap?.gap).toBe("Nothing recorded for sleep and mood this week. Those stay blank rather than counting as fine.");
    expect(recap?.tryNext).toBe("Log sleep on a few days so Bubbles can compare it with your usual.");
  });

  it("does not claim a missing signal when there is no breakdown to check", () => {
    const recap = buildWeekRecap(weekly({ trend: null }));
    expect(recap?.gap).toMatch(/^No repeating patterns showed up/);
  });

  it("every signal present and a pattern found still reports the blank-days gap", () => {
    const all = ["sleep", "mood", "hydration", "activity", "food"].map((event_type) => ({ event_type, count: 2 }));
    const recap = buildWeekRecap(weekly({ trend: { signals: all }, insights: [insight({})] }));
    expect(recap?.gap).toBe("Days with nothing recorded stay blank. Bubbles does not count them as fine.");
  });

  it("never contains an em dash or an en dash, in any branch", () => {
    const cases = [
      weekly(),
      weekly({ data_quality: { event_count: 0 } }),
      weekly({ data_quality: { event_count: 1, sufficient_for_pattern_detection: false } }),
      weekly({ trend: { signals: [{ event_type: "symptom", count: 3 }] } }),
      weekly({ trend: null, insights: [insight({})] }),
    ];
    for (const c of cases) {
      const recap = buildWeekRecap(c);
      expect([...(recap?.highlights ?? []), recap?.gap, recap?.tryNext].join(" ")).not.toMatch(/[–—]/);
    }
  });
});

describe("buildWeekRecap input safety", () => {
  it("returns null when the response cannot say how much was recorded", () => {
    expect(buildWeekRecap(null)).toBeNull();
    expect(buildWeekRecap(undefined)).toBeNull();
    expect(buildWeekRecap(weekly({ data_quality: null }))).toBeNull();
    expect(buildWeekRecap(weekly({ data_quality: {} }))).toBeNull();
    expect(buildWeekRecap(weekly({ data_quality: { event_count: -1 } }))).toBeNull();
  });

  it("tolerates missing insights and keeps the API disclaimer, with a fallback", () => {
    const base = { data_quality: { event_count: 4 } } as WeeklyInsights;
    expect(buildWeekRecap(base)?.highlights).toEqual(["Bubbles recorded 4 entries this week."]);
    expect(buildWeekRecap(base)?.disclaimer).toBe(RECAP_DISCLAIMER);
    expect(buildWeekRecap(weekly())?.disclaimer).toBe("Observations only.");
  });
});
