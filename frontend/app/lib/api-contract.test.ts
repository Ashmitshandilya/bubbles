// Run: npx vitest run app/lib/api-contract.test.ts
//
// Frontend <-> backend contract. The fixtures are real response shapes captured from the running FastAPI app
// (in-memory Supabase; see the C2 audit in .omc/plans/health-intel/), pushed through the same pure functions the
// screens render from. Dates are generated relative to a fixed local "now" so the suite passes in any time zone.
// If the backend changes a key or a unit, the screen that reads it fails here instead of showing an empty page.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { computeStat, dayLabel, daysAgo, timeLabel, type Entry } from "../../components/tracking/data";
import { buildPatterns, buildTodayItems, dayKey, readTracker, summarizeCycle, summarizeSignal, upcomingVisits } from "../dashboard/dashboard/today";
import { mergeRecords } from "../care/prep";
import { CARD_LIMIT, toCards, weeklyCounts } from "../insights/patterns";
import { adaptTrackerEntry, readCycleSummary, readEntries, readHealthSummary } from "./api-adapters";
import { adaptHealthEvents, adaptReplySafety } from "./bubbles-events";
import { calendarDay, formatWhen, parseWhen } from "./dates";

const NOW = new Date(2026, 9, 7, 9, 0); // 7 Oct 2026, 09:00 local

/** Calendar day, `ago` days before NOW: how sleep, cycle and report dates arrive. */
const ymd = (ago: number) => {
  const d = new Date(2026, 9, 7 - ago);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
/** Instant at local `hour` on that day, in the backend's isoformat style. */
const stamp = (ago: number, hour = 12) => new Date(2026, 9, 7 - ago, hour).toISOString().replace(/\.000Z$/, "+00:00");

const sleepList = {
  status: "success",
  entries: [
    { id: "sl0", date: ymd(0), duration: 6.5, quality: 6 },
    { id: "sl1", date: ymd(1), duration: 7.17, quality: 7 },
    { id: "sl2", date: ymd(2), duration: 7.67, quality: 8 },
    { id: "sl3", date: ymd(3), duration: 6.83, quality: 6 },
  ],
};

const cycleList = {
  status: "success",
  entries: [
    { id: "cy-fol", date: ymd(3), phase: "follicular" },
    { id: "cy2", date: ymd(8), phase: "period" },
    { id: "cy1", date: ymd(36), phase: "period" },
    { id: "cy0", date: ymd(64), phase: "period" },
  ],
  summary: { period_start_count: 3, last_period: ymd(8), average_cycle_length: 28.0, next_predicted: ymd(-20) },
};

const hydrationList = {
  status: "success",
  entries: [
    { id: "hy0", date: stamp(0, 8), volume: 500, type: "water" },
    { id: "hy0b", date: stamp(0, 11), volume: 250, type: "tea" },
    { id: "hy1", date: stamp(1, 12), volume: 750, type: "water" },
  ],
};

const moodList = { status: "success", entries: [{ id: "mo0", date: stamp(0), mood: 8, notes: "ok | Stress 3/10; Anxiety 0/10" }, { id: "mo1", date: stamp(1), mood: 6 }] };
const activityList = { status: "success", entries: [{ id: "ac0", date: stamp(0), type: "Walk", duration: 30, intensity: "moderate" }] };
const nutritionList = {
  status: "success",
  entries: [{ id: "he1", date: stamp(0), meal_type: "lunch", description: "Dal and rice", calories: 450, notes: "Felt full" }],
};

/** The visit form's "Next visit" comes back inside `recommendations`; a day-only pick comes back as UTC midnight. */
const visitsList = {
  status: "success",
  entries: [
    { id: "dv-past", date: `${ymd(5)}T00:00:00+00:00`, doctor_name: "Dr Rao", specialty: "Gynaecology", reason: "checkup", recommendations: `Next visit: ${ymd(-30)}` },
    { id: "dv-future", date: `${ymd(-12)}T00:00:00+00:00`, doctor_name: "Dr Iyer", specialty: "GP" },
    { id: "dv-old", date: `${ymd(90)}T00:00:00+00:00`, doctor_name: "Dr Old" },
  ],
};

const labsList = {
  status: "success",
  entries: [
    { id: "l1", date: `${ymd(10)}T00:00:00+00:00`, test_name: "Ferritin", value: 8.0, unit: "ng/mL", reference_range: "15-150" },
    { id: "l2", date: `${ymd(10)}T00:00:00+00:00`, test_name: "HbA1c", value: 5.8, unit: "%", reference_range: "4-6" },
    { id: "l3", date: stamp(2), test_name: "Pregnancy test", notes: "Result: positive" },
  ],
};

const briefResponse = {
  status: "success",
  brief: {
    generated_at: "2026-10-07T12:08:39+00:00",
    window_days: 14,
    state: {
      window_days: 14,
      event_count: 45,
      baseline: {},
      deviations: { sleep_hours: null, water_ml: null },
      data_gaps: { gaps: ["weight_kg"] },
      correlations: {
        items: [
          {
            kind: "temporal_correlation",
            a: { event_type: "hydration", subject: "water" },
            b: { event_type: "sleep", subject: "sleep" },
            pair_count: 54,
            window_days: 2,
            strength: 1.0,
            interpretation: "water and sleep were recorded within 2 days of each other 54 times. This is a temporal association, not proof of causation.",
          },
        ],
      },
      status: "active",
    },
    companion: {
      headline: "Your Bubbles daily check-in",
      state_status: "active",
      focus: [],
      learning_signals: 15,
      data_gaps: ["weight_kg"],
      safety_note: "If symptoms are severe, rapidly worsening, or feel urgent, seek appropriate medical care rather than relying on Bubbles.",
      disclaimer: "Daily guidance is based on logged data and is not a diagnosis or proof of causation.",
    },
    actions: [
      { id: "review-sleep_hours", title: "Review sleep hours", detail: "Bubbles observed a change relative to your baseline.", target: "intelligence", priority: "high" },
      { id: "ask-bubbles", title: "Ask Bubbles what changed", detail: "Review recent evidence.", target: "companion", priority: "normal" },
    ],
  },
};

/** GET /companion/daily returns the same `companion` block next to the state. */
const companionDaily = { status: "success", companion: briefResponse.brief.companion, state: briefResponse.brief.state };

const weeklyResponse = {
  status: "success",
  insights: {
    period: { days: 7 },
    data_quality: { event_count: 23, sufficient_for_pattern_detection: true },
    insights: [
      {
        title: "Repeated sleep",
        description: "Sleep was logged 14 times. This is a recurring observation worth watching over time.",
        category: "recurrence",
        confidence: 0.85,
        supporting_events: ["ev43", "ev38", "ev36", "ev33", "ev30", "ev26", "ev24", "ev20"], // a capped sample, not all 14
        actionable: false,
        suggested_action: null,
      },
      {
        title: "Repeated headache",
        description: "Headache was logged 7 times. This is a recurring observation worth watching over time.",
        category: "recurrence",
        confidence: 0.65,
        supporting_events: ["ev40", "ev35"],
        actionable: false,
        suggested_action: null,
      },
      { title: "Not much logged", description: "Only a little data.", category: "data_gap", confidence: 0.3, supporting_events: [], actionable: false, suggested_action: null },
    ],
    disclaimer: "These are observations from your logged data, not diagnoses or proof that one health factor caused another.",
  },
};

const patternsResponse = {
  status: "success",
  analysis: {
    period_days: 30,
    event_count: 45,
    patterns: [
      {
        kind: "recurrence", event_type: "sleep", subject: "sleep", occurrence_count: 14, average_confidence: 0.9,
        first_seen: stamp(13), last_seen: stamp(0), span_days: 13.0, source_event_ids: ["ev43", "ev38"], observation: "sleep was recorded 14 times.",
      },
      {
        kind: "recurrence", event_type: "symptom", subject: "headache", occurrence_count: 3, average_confidence: 0.9,
        first_seen: stamp(10), last_seen: stamp(1), span_days: 9.0, source_event_ids: [], observation: "headache was recorded 3 times.",
      },
    ],
    correlations: [
      {
        kind: "temporal_correlation", a: { event_type: "hydration", subject: "water" }, b: { event_type: "sleep", subject: "sleep" },
        pair_count: 54, window_days: 2, strength: 1.0, interpretation: "water and sleep were recorded within 2 days of each other 54 times.", source_event_ids: ["ev44"],
      },
    ],
  },
};

describe("tracker lists: GET /health/<slug>", () => {
  it("sleep: hours in, hours shown, newest night first", () => {
    const entries = readEntries(sleepList.entries);
    expect(entries).toHaveLength(4);
    const last = computeStat({ label: "Last night", kind: "latest", field: "duration", unit: "h" }, entries, NOW);
    expect(last.value).toMatch(/^6[.,]5 h$/);
    expect(last.note).toBe("Today");
    const avg = computeStat({ label: "7-night average", kind: "avg", field: "duration", days: 7, unit: "h" }, entries, NOW);
    expect(avg.value).toMatch(/^7[.,]0 h$|^7 h$/);
    expect(computeStat({ label: "Nights logged", kind: "count" }, entries, NOW).value).toBe("4");
  });

  it("hydration is millilitres, and 'today' is the viewer's local day", () => {
    const entries = readEntries(hydrationList.entries);
    const today = computeStat({ label: "Today", kind: "sum", field: "volume", days: 1, unit: "ml", decimals: 0 }, entries, NOW);
    expect(today.value).toBe("750 ml");
    const signal = summarizeSignal("hydration", readTracker(hydrationList).entries, NOW);
    expect(signal.weekDays).toBe(2);
    expect(signal.value).toMatch(/^750\u00A0ml$|^0\.75\u00A0L$/); // average of 750 and 750 ml/day
  });

  it("activity is minutes, mood is 1-10, nutrition counts meals", () => {
    const activity = summarizeSignal("activity", readTracker(activityList).entries, NOW);
    expect(activity.value).toBe("30\u00A0min");
    expect(summarizeSignal("mood", readTracker(moodList).entries, NOW).value).toMatch(/^7\u00A0\/\u00A010$/);
    expect(summarizeSignal("nutrition", readTracker(nutritionList).entries, NOW).value).toBe("1 meal");
  });

  it("a day-only pick (UTC midnight) stays on the picked day and gets no invented time", () => {
    const picked = `${ymd(5)}T00:00:00+00:00`;
    expect(calendarDay(picked)).toBe(ymd(5));
    expect(calendarDay("2026-10-02T14:03:11+00:00")).toBeNull(); // a real instant is not a calendar day
    const local = parseWhen(picked);
    expect([local.getFullYear(), local.getMonth(), local.getDate(), local.getHours()]).toEqual([2026, 9, 2, 0]);
    expect(timeLabel(picked)).toBe("");
    expect(timeLabel(stamp(0, 15))).not.toBe("");
    expect(daysAgo(picked, NOW)).toBe(5);
    expect(dayLabel(picked, NOW)).not.toBe("Undated");
    expect(dayKey(picked)).toBe(ymd(5));
    expect(formatWhen(picked)).not.toBe("—");
  });

  it("survives rows with no id, no date or nested values", () => {
    const rows = readEntries([
      { id: 7, date: "2026-10-01", duration: 7 },
      null,
      "text",
      [1, 2],
      { duration: 5 },
      { id: "x", date: null, created_at: "2026-10-02T10:00:00+00:00" },
      { id: "n", date: "2026-10-03", nested: { a: 1 }, list: [1], ok: "yes" },
    ]);
    expect(rows.map((r) => r.id)).toEqual(["7", "row-4", "x", "n"]);
    expect(rows[1].date).toBe(""); // undated: shown as "Undated", never a throw
    expect(rows[2].date).toBe("2026-10-02T10:00:00+00:00");
    expect(rows[3]).toEqual({ id: "n", date: "2026-10-03", ok: "yes" });
    expect(readEntries(undefined)).toEqual([]);
    expect(readEntries({ entries: [] })).toEqual([]);
    expect(summarizeSignal("sleep", readTracker({ entries: [{ id: "a" }, { id: "b", date: null }] }).entries, NOW).logged).toBe(false);
  });
});

describe("form fields the backend folds into text come back as fields", () => {
  // The forms POST these (see mood/weight/visits pages); GET returns the folded text (backend/health_logs.py).
  it("mood: stress and anxiety return from the notes", () => {
    const entry = { id: "mo", date: stamp(0), mood: 8, notes: "ok | Stress 3/10; Anxiety 0/10" };
    expect(adaptTrackerEntry("mood", entry)).toEqual({ id: "mo", date: entry.date, mood: 8, notes: "ok", stress: 3, anxiety: 0 });
    expect(adaptTrackerEntry("mood", { id: "mo", date: "d", mood: 6, notes: "Stress 7/10" })).toEqual({ id: "mo", date: "d", mood: 6, stress: 7 });
    const plain = { id: "mo", date: "d", mood: 6, notes: "Stress 4/10 at work, then fine" };
    expect(adaptTrackerEntry("mood", plain)).toEqual(plain); // only the trailing machine-written part is read back
  });

  it("weight: time of day returns from the notes", () => {
    expect(adaptTrackerEntry("weight", { id: "w", date: "d", weight: 140.5, notes: "Before breakfast | morning" })).toEqual({
      id: "w", date: "d", weight: 140.5, notes: "Before breakfast", time_of_day: "morning",
    });
    expect(adaptTrackerEntry("weight", { id: "w", date: "d", weight: 140.5, notes: "evening" })).toEqual({ id: "w", date: "d", weight: 140.5, time_of_day: "evening" });
    const plain = { id: "w", date: "d", weight: 140.5, notes: "after a workout" };
    expect(adaptTrackerEntry("weight", plain)).toEqual(plain);
  });

  it("visits: the next visit returns from recommendations, other advice stays as written", () => {
    expect(adaptTrackerEntry("visits", { id: "v", date: "d", recommendations: "Next visit: 2027-01-02" })).toEqual({ id: "v", date: "d", next_visit: "2027-01-02" });
    const advice = { id: "v", date: "d", recommendations: "Rest and fluids" };
    expect(adaptTrackerEntry("visits", advice)).toEqual(advice);
  });

  it("other trackers pass through untouched", () => {
    const sleep = { id: "s", date: ymd(0), duration: 7, notes: "Stress 3/10" };
    expect(adaptTrackerEntry("sleep", sleep)).toEqual(sleep);
  });
});

describe("cycle: GET /health/cycle with summary", () => {
  it("reads the backend summary as the Cycle page shows it", () => {
    expect(readCycleSummary(cycleList.summary)).toEqual({ count: 3, last: ymd(8), average: 28, next: ymd(-20) });
    expect(readCycleSummary({ period_start_count: 0 })).toEqual({ count: 0, last: null, average: null, next: null });
    expect(readCycleSummary(null)).toEqual({ count: 0, last: null, average: null, next: null });
    expect(readEntries(cycleList.entries).map((e) => e.phase)).toEqual(["follicular", "period", "period", "period"]);
  });

  it("feeds Today: cycle day counts from the last logged period start", () => {
    const cycle = summarizeCycle(readTracker(cycleList), NOW);
    expect(cycle.logged).toBe(true);
    expect(cycle.day).toBe(9);
    expect(cycle.value).toBe("Day 9");
    expect(cycle.average).toBe(28);
    expect(cycle.daysUntil).toBe(20);
    expect(cycle.detail).toBe("Next period in about 20 days");
    expect(summarizeCycle(readTracker({ status: "success", entries: [], summary: { period_start_count: 0 } }), NOW).logged).toBe(false);
  });
});

describe("Today: what matters, patterns and coming up", () => {
  const trackers = {
    sleep: readTracker(sleepList), mood: readTracker(moodList), activity: readTracker(activityList),
    hydration: readTracker(hydrationList), nutrition: readTracker(nutritionList),
  };
  const signals = (Object.keys(trackers) as Array<keyof typeof trackers>).map((slug) => summarizeSignal(slug, trackers[slug].entries, NOW));

  it("builds at most three items and turns a high-priority review action into a card", () => {
    const items = buildTodayItems(signals, summarizeCycle(readTracker(cycleList), NOW), briefResponse.brief.actions);
    expect(items.length).toBeLessThanOrEqual(3);
    const review = items.find((i) => i.id === "review-sleep_hours");
    expect(review?.slug).toBe("sleep");
    expect(review?.whyHref).toBe("/insights");
  });

  it("does not understate how many logs back a weekly insight", () => {
    const items = buildPatterns(weeklyResponse.insights.insights, briefResponse.brief.state.correlations.items);
    expect(items.map((i) => i.title)).toEqual(["Repeated sleep", "Repeated headache", briefResponse.brief.state.correlations.items[0].interpretation]);
    expect(items[0].pill.text).toBe("High confidence"); // 0.85; supporting_events is a capped sample so no "8 logs"
    expect(items[1].pill.text).toBe("Medium confidence");
    expect(items.some((i) => i.title === "Not much logged")).toBe(false); // data_gap rows are not patterns
  });

  it("lists visits from today on, including a 'Next visit' named by a past visit", () => {
    const upcoming = upcomingVisits(readTracker(visitsList).entries, NOW);
    expect(upcoming.map((v) => v.id)).toEqual(["dv-future", "dv-past-next"]);
    expect(dayKey(upcoming[0].date)).toBe(ymd(-12));
    expect(dayKey(upcoming[1].date)).toBe(ymd(-30));
    expect(upcoming[1].doctor_name).toBe("Dr Rao");
  });

  it("companion block (brief and /companion/daily) has the fields Today and the chat read", () => {
    for (const companion of [briefResponse.brief.companion, companionDaily.companion]) {
      expect(typeof companion.safety_note).toBe("string");
      expect(Array.isArray(companion.focus)).toBe(true);
      expect(Array.isArray(companion.data_gaps)).toBe(true);
      expect(typeof companion.headline).toBe("string");
    }
    expect(companionDaily.state.correlations.items).toHaveLength(1);
  });
});

describe("health summary: GET /health/summary", () => {
  it("reads the counts the Health hub shows", () => {
    const summary = readHealthSummary({ status: "success", categories_with_data: 15, total_entries: 71, days_tracked: 21, last_update: "2026-10-07T09:00:00+00:00" });
    expect(summary).toEqual({ categories: 15, entries: 71, days: 21, lastUpdate: "2026-10-07T09:00:00+00:00" });
  });

  it("an empty or broken payload reads as nothing logged, never NaN", () => {
    const empty = { categories: 0, entries: 0, days: 0, lastUpdate: null };
    expect(readHealthSummary({ status: "success", categories_with_data: 0, total_entries: 0, days_tracked: 0, last_update: null })).toEqual(empty);
    expect(readHealthSummary(undefined)).toEqual(empty);
    expect(readHealthSummary({ total_entries: "71", days_tracked: Number.NaN })).toEqual(empty);
  });
});

describe("patterns: POST /patterns/analyze and /intelligence/longitudinal", () => {
  it("turns recurrences and co-occurrences into cards, strongest first", () => {
    const cards = toCards(patternsResponse.analysis, 30);
    expect(cards.map((c) => c.headline)).toEqual([
      "Water and sleep often show up together",
      "Sleep came up 14 times",
      "Headache came up 3 times",
    ]);
    expect(cards.map((c) => c.confidence)).toEqual(["High", "Medium", "Low"]);
    expect(cards[1].signals).toEqual([{ subject: "sleep", toneKey: "sleep sleep" }]);
    expect(cards[1].evidence[0]).toBe("Logged 14 times over about 13 days.");
    expect(cards[1].window).not.toContain("—");
    expect(toCards({ event_count: 0 }, 30)).toEqual([]);
  });

  it("a regular logger's long list keeps the strongest patterns first, so the first page is the best of them", () => {
    const pair = (n: number) => ({
      kind: "temporal_correlation", a: { event_type: "mood", subject: `m${n}` }, b: { event_type: "sleep", subject: "sleep" },
      pair_count: n, window_days: 2, strength: 1, interpretation: `m${n} and sleep`, source_event_ids: [],
    });
    const analysis = { event_count: 99, patterns: [], correlations: [3, 9, 4, 20, 1, 7, 12, 5, 8, 2, 6, 15].map(pair) };
    const cards = toCards(analysis, 30);
    expect(cards).toHaveLength(12);
    expect(cards.length).toBeGreaterThan(CARD_LIMIT);
    const firstPage = cards.slice(0, CARD_LIMIT).map((c) => c.confidence);
    expect(firstPage.filter((c) => c === "High")).toHaveLength(7); // pair_count 6, 7, 8, 9, 12, 15 and 20 are High
    expect(firstPage).toEqual([...firstPage].sort((a, b) => ["High", "Medium", "Low"].indexOf(a) - ["High", "Medium", "Low"].indexOf(b)));
  });

  it("counts logs per week from calendar-day timeline dates", () => {
    const timeline = [
      { date: ymd(0), domain: "sleep" }, { date: ymd(0), domain: "mood" }, { date: ymd(2), domain: "hydration" },
      { date: ymd(8), domain: "sleep" }, { date: stamp(9), domain: "sleep" }, // a full timestamp is read, not skipped
      { date: ymd(-3), domain: "sleep" }, // future: outside every bucket
      { date: null, domain: "sleep" }, { domain: "sleep" },
    ];
    const counts = weeklyCounts(timeline, 30, NOW);
    expect(counts).toHaveLength(5);
    expect(counts[4]).toBe(3);
    expect(counts[3]).toBe(2);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(5);
    expect(weeklyCounts(undefined, 90, NOW)).toHaveLength(13);
  });
});

describe("doctor prep: records on file", () => {
  const summary = { lab_count: 1, report_count: 1, flagged_labs: [] }; // /medical/summary: lab_results has no `flag` key

  it("flags a result outside the range the user entered, and counts what the Labs page lists", () => {
    const labs = readEntries<Entry>(labsList.entries);
    const records = mergeRecords(summary, labs, readEntries<Entry>([{ id: "r1", date: ymd(20), title: "Pelvic ultrasound" }]));
    expect(records.labCount).toBe(3);
    expect(records.reportCount).toBe(1);
    expect(records.flagged).toEqual([{ label: "Ferritin", flag: "low", value: 8, unit: "ng/mL" }]);
  });

  it("compatibility mode: the summary reads empty tables, the tracker lists still count", () => {
    const empty = { lab_count: 0, report_count: 0, flagged_labs: [] };
    const records = mergeRecords(empty, readEntries<Entry>(labsList.entries), readEntries<Entry>([{ id: "r1", date: ymd(20), title: "Scan" }]));
    expect(records.labCount).toBe(3);
    expect(records.reportCount).toBe(1);
    expect(records.flagged).toHaveLength(1);
  });

  it("falls back to the summary alone, and never double-lists a lab the backend flagged", () => {
    expect(mergeRecords(summary, null, null)).toEqual({ labCount: 1, reportCount: 1, flagged: [] });
    expect(mergeRecords(undefined, null, null)).toEqual({ labCount: 0, reportCount: 0, flagged: [] });
    const flaggedByBackend = { lab_count: 1, report_count: 0, flagged_labs: [{ label: "Ferritin", flag: "low", value: 8, unit: "ng/mL" }] };
    expect(mergeRecords(flaggedByBackend, readEntries<Entry>(labsList.entries), null).flagged).toHaveLength(1);
  });
});

describe("companion: POST /chat reply and GET /chat/conversations/{id}/messages", () => {
  const event = (id: string, event_type: string, extracted_data: Record<string, unknown>) => ({
    id, event_type, extracted_data, confidence: 0.95, assertion: "present", temporal: "current", status: "pending",
    provenance: { source: "user_message", extractor: "rules" },
  });
  const dailyLogReply = {
    response: "Got it. I've logged today.",
    kind: "daily_log_summary",
    safety: { level: "GREEN", state: "NO_REDFLAG", reasons: [], concepts: [], retracted: false },
    health_events: [
      event("9d48087b", "sleep", { name: "sleep", duration_minutes: 420, hours: 7, unit: "hours", date: "2026-10-07" }),
      event("fb2b467f", "hydration", { name: "water", amount_ml: 2000, unit: "ml", date: "2026-10-07" }),
    ],
    health_event_ids: ["9d48087b", "fb2b467f"],
    message_id: "m-c", user_message_id: "m-u", conversation_id: "11111111-1111-1111-1111-111111111111", evidence: [],
  };
  const emergencyReply = {
    ...dailyLogReply,
    kind: "emergency",
    safety: { level: "RED", state: "EMERGENCY", reasons: ["chest pain or pressure", "breathing difficulty"], concepts: ["chest_pain"], retracted: false },
    health_events: [event("adc47d47", "symptom", { symptom: "chest pain", name: "chest pain", date: "2026-10-07" })],
    health_event_ids: ["adc47d47"],
  };

  it("a daily-log reply is calm, and every staged event can be confirmed by its inline id", () => {
    const safety = adaptReplySafety(dailyLogReply.safety, undefined, dailyLogReply.kind);
    expect(safety).toMatchObject({ safetyLevel: "GREEN", safetyState: "NO_REDFLAG", retracted: false, kind: "daily_log_summary" });
    const events = adaptHealthEvents(dailyLogReply.health_events, dailyLogReply.health_event_ids);
    expect(events.map((e) => e.id)).toEqual(["9d48087b", "fb2b467f"]);
    expect(events.every((e) => e.isConfirmable)).toBe(true);
  });

  it("an emergency reply is RED with its reasons", () => {
    const safety = adaptReplySafety(emergencyReply.safety, undefined, emergencyReply.kind);
    expect(safety).toMatchObject({ safetyLevel: "RED", safetyState: "EMERGENCY", kind: "emergency" });
    expect(safety.safetyReasons).toEqual(["chest pain or pressure", "breathing difficulty"]);
  });

  it("reloaded history rows carry the same safety object, kind and events", () => {
    const row = {
      id: "m-c", role: "bubbles", content: "Got it.", created_at: stamp(0), safety_level: "GREEN",
      safety: { level: "GREEN", state: "NO_REDFLAG", reasons: [], retracted: false, retracted_at: null, retracted_by_message_id: null },
      kind: "daily_log_summary",
      health_events: dailyLogReply.health_events.map(({ id, event_type, extracted_data, confidence, status, assertion, temporal }) => ({ id, event_type, extracted_data, confidence, status, assertion, temporal })),
    };
    expect(adaptReplySafety(row.safety, row.safety_level, row.kind).safetyLevel).toBe("GREEN");
    expect(adaptHealthEvents(row.health_events, undefined).map((e) => e.id)).toEqual(["9d48087b", "fb2b467f"]);
    // A pre-contract row (only safety_level) still reads.
    expect(adaptReplySafety(undefined, "RED", undefined).safetyLevel).toBe("RED");
  });
});

describe("endpoint inventory: every /health/<slug> the screens call is served by the backend", () => {
  const frontendRoot = resolve(__dirname, "../..");
  const backendFile = resolve(frontendRoot, "../backend/health_logs.py");

  function sourceFiles(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return name === "node_modules" || name === ".next" ? [] : sourceFiles(path);
      return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
    });
  }

  it.skipIf(!existsSync(backendFile))("tracker slugs exist in backend DOMAINS", () => {
    const served = new Set([...readFileSync(backendFile, "utf8").matchAll(/^\s{4}"(\w+)": dict\(table=/gm)].map((m) => m[1]));
    expect(served.size).toBeGreaterThanOrEqual(15);

    const used = new Set<string>();
    for (const file of [...sourceFiles(join(frontendRoot, "app")), ...sourceFiles(join(frontendRoot, "components"))]) {
      const text = readFileSync(file, "utf8");
      for (const m of text.matchAll(/["'`]\/health\/([a-z]+)/g)) used.add(m[1]);
      const tiles = /TILE_ORDER: SignalSlug\[\] = \[([^\]]*)\]/.exec(text); // the Today screen builds /health/${slug}
      if (tiles) for (const m of tiles[1].matchAll(/"(\w+)"/g)) used.add(m[1]);
    }
    used.delete("summary"); // GET /health/summary is its own route
    expect([...used].length).toBeGreaterThanOrEqual(15);
    const missing = [...used].filter((slug) => !served.has(slug));
    expect(missing).toEqual([]);
  });

  // health_logs.py keeps at most MAX_TEXT characters of any text and cuts the rest without a word, so a box that
  // accepts more would lose the user's writing on save.
  it.skipIf(!existsSync(backendFile))("notes boxes stop typing at what the backend keeps", () => {
    const limit = Number(/^MAX_TEXT = (\d+)/m.exec(readFileSync(backendFile, "utf8"))?.[1]);
    expect(limit).toBeGreaterThan(0);
    const pages = readdirSync(join(frontendRoot, "app")).flatMap((dir) => {
      const path = join(frontendRoot, "app", dir, "page.tsx");
      return existsSync(path) ? [path] : [];
    });
    const unbounded: string[] = [];
    let checked = 0;
    for (const page of pages) {
      for (const line of readFileSync(page, "utf8").split(/\r?\n/)) {
        if (!line.includes('type: "textarea"')) continue;
        checked += 1;
        const max = Number(/maxLength: (\d+)/.exec(line)?.[1]);
        if (!(max > 0 && max <= limit)) unbounded.push(`${page.replace(frontendRoot, "")}: ${line.trim().slice(0, 60)}`);
      }
    }
    for (const client of ["sleep/SleepClient.tsx", "symptoms/SymptomsClient.tsx", "activity/ActivityClient.tsx", "cycle/CycleClient.tsx"]) {
      const text = readFileSync(join(frontendRoot, "app", client), "utf8");
      for (const tag of text.match(/<TextArea [^>]*\/>/g) ?? []) {
        checked += 1;
        const max = Number(/maxLength=\{(\d+)\}/.exec(tag)?.[1]);
        if (!(max > 0 && max <= limit)) unbounded.push(`${client}: ${tag.slice(0, 60)}`);
      }
    }
    // Wellness clients: the backend keeps up to 5000 characters for journal and check-in notes (wellness_common text limits).
    for (const client of ["mood/MoodClient.tsx", "medications/MedicationsClient.tsx", "medications/Glp1AndLogbook.tsx", "mind/CheckIn.tsx", "mind/Journal.tsx"]) {
      const text = readFileSync(join(frontendRoot, "app", client), "utf8");
      for (const tag of text.match(/<(?:textarea|TextArea)[\s\S]*?>/g) ?? []) {
        checked += 1;
        const max = Number(/maxLength=\{?["']?(\d+)/.exec(tag)?.[1] ?? /maxLength=\{([A-Z_]+)\}/.exec(tag)?.[1]);
        if (!(max > 0 && max <= 5000) && !/maxLength=\{[A-Za-z_.]+\}/.test(tag)) unbounded.push(`${client}: ${tag.slice(0, 60)}`);
      }
    }
    expect(checked).toBeGreaterThanOrEqual(12); // tracker forms + the wellness clients above (several tracker pages moved into clients)
    expect(unbounded).toEqual([]);
  });
});
