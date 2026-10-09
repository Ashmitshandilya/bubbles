import { describe, expect, it } from "vitest";
import {
  PACE_MAX, PACE_MIN, cardState, chartModel, chartSummary, clampPace, cmToFtIn, detailMessage, formatRange, formatRate, formatWeeks,
  ftInToCm, groceryKey, groupByMeal, macroRows, mealItemsText, microGaps, paceKgPerWeek, paceWeeksRange, parseTicks, ringFraction, ringWord,
  shiftDay, todayISO, weightFromKg, weightToKg,
} from "./fitness-calc";
import type { FoodEntry } from "./fitness-types";

describe("units", () => {
  it("round-trips pounds and feet through metric", () => {
    expect(weightToKg("176.4", "imperial")).toBeCloseTo(80, 0);
    expect(weightToKg("80", "metric")).toBe(80);
    expect(weightFromKg(80, "imperial")).toBe("176.4");
    expect(cmToFtIn(165)).toEqual({ ft: 5, inch: 5 });
    expect(ftInToCm(5, 5)).toBeCloseTo(165.1, 1);
  });
  it("treats blanks and junk as NaN, never zero", () => {
    expect(weightToKg("", "metric")).toBeNaN();
    expect(weightToKg("abc", "imperial")).toBeNaN();
    expect(weightFromKg(null, "metric")).toBe("");
  });
  it("describes a weekly rate without shaming", () => {
    expect(formatRate(-0.5, "metric")).toBe("−0.50 kg a week");
    expect(formatRate(null, "metric")).toBe("Not enough weigh-ins yet");
  });
});

describe("ranges and rings", () => {
  it("formats ranges and collapses equal ends", () => {
    expect(formatRange(1306, 2005)).toBe("1,306–2,005 kcal");
    expect(formatRange(500, 500, "g")).toBe("500 g");
  });
  it("never lets the ring exceed full and words over-budget gently", () => {
    expect(ringFraction(2400, 1600)).toBe(1);
    expect(ringFraction(0, 1600)).toBe(0);
    expect(ringFraction(100, 0)).toBe(0);
    expect(ringWord(1800, 1600)).toBe("About 200 kcal past today's estimate");
    expect(ringWord(1000, 1600)).toBe("About 600 kcal left");
    expect(ringWord(0, 1600)).toBe("Nothing logged yet");
  });
  it("macro bars cap at 100 and survive a missing target", () => {
    const rows = macroRows({ protein_g: 150, carbs_g: 50, fat_g: 10, fibre_g: 5 }, { protein_g: 100, carbs_g: 200, fat_g: 50, fibre_g: 25 });
    expect(rows[0].pct).toBe(100);
    expect(rows[1].pct).toBe(25);
    expect(macroRows({ protein_g: 5, carbs_g: 5, fat_g: 5, fibre_g: 5 }, null).every((r) => r.pct === 0)).toBe(true);
  });
});

describe("pace", () => {
  it("clamps to the 0.25-0.75 band", () => {
    expect(clampPace(2)).toBe(PACE_MAX);
    expect(clampPace(0.01)).toBe(PACE_MIN);
    expect(clampPace(Number.NaN)).toBe(0.5);
  });
  it("gives a range, not a date, and nothing when there is no gap", () => {
    expect(paceKgPerWeek(80, 0.5)).toBe(0.4);
    const r = paceWeeksRange(8, 80, 0.5);
    expect(r).toEqual([20, 31]);
    expect(formatWeeks(20, 31)).toBe("typically 20 to 31 weeks");
    expect(paceWeeksRange(0, 80, 0.5)).toBeNull();
    expect(paceWeeksRange(-3, 80, 0.5)).toBeNull();
  });
});

describe("meals", () => {
  it("builds text the food log can parse back", () => {
    expect(mealItemsText([{ food: "oats", grams: 40 }, { food: "sprouts", grams: 224.6 }, { food: "", grams: 5 }])).toBe("40 g oats, 225 g sprouts");
  });
  const entry = (id: string, meal: string | null, kcal: number): FoodEntry => ({
    id, ts: "", meal, text: id, items: [], unrecognised: [],
    totals: { kcal, kcal_low: kcal, kcal_high: kcal, protein_g: 0, carbs_g: 0, fat_g: 0, fibre_g: 0 },
  });
  it("groups by meal in day order with an Other bucket", () => {
    const g = groupByMeal([entry("a", "dinner", 500), entry("b", null, 100), entry("c", "breakfast", 300), entry("d", "dinner", 50)]);
    expect(g.map((x) => x.meal)).toEqual(["breakfast", "dinner", "other"]);
    expect(g[1].kcal).toBe(550);
  });
  it("suggests foods, never supplements, for low micronutrients", () => {
    const gaps = microGaps({ iron_mg: 3, calcium_mg: 900 });
    expect(gaps).toHaveLength(1);
    expect(gaps[0].label).toBe("Iron");
    expect(JSON.stringify(gaps)).not.toMatch(/supplement|tablet|dose/i);
    expect(microGaps(undefined)).toEqual([]);
  });
});

describe("weight chart", () => {
  const raw = [{ date: "2026-09-01", weight_kg: 80 }, { date: "2026-09-08", weight_kg: 81 }, { date: "2026-09-15", weight_kg: 79.5 }];
  const trend = raw.map((r, i) => ({ date: r.date, trend_kg: 80 - i * 0.2 }));
  it("keeps every point inside the plot and draws two lines", () => {
    const m = chartModel(raw, trend, 600, 240);
    expect(m.points).toHaveLength(3);
    for (const p of m.points) {
      expect(p.x).toBeGreaterThanOrEqual(44);
      expect(p.x).toBeLessThanOrEqual(588);
      expect(p.y).toBeGreaterThanOrEqual(12);
      expect(p.y).toBeLessThanOrEqual(212);
    }
    expect(m.rawPath.startsWith("M")).toBe(true);
    expect(m.trendPath).not.toBe(m.rawPath);
  });
  it("copes with one point and none", () => {
    expect(chartModel([], [], 600, 240).points).toEqual([]);
    const one = chartModel([raw[0]], [], 600, 240);
    expect(one.points).toHaveLength(1);
    expect(Number.isFinite(one.points[0].x) && Number.isFinite(one.points[0].y)).toBe(true);
  });
  it("describes the trend in words", () => {
    expect(chartSummary([], [])).toBe("No weigh-ins yet.");
    expect(chartSummary(raw, trend)).toMatch(/3 weigh-ins from 2026-09-01 to 2026-09-15/);
    expect(chartSummary(raw, trend)).toMatch(/trend is what matters/);
  });
});

describe("errors and storage", () => {
  it("prefers the server sentence, even on 403, and hides 5xx internals", () => {
    expect(detailMessage(403, { detail: "Strict mode is not available for you." }, "fallback")).toBe("Strict mode is not available for you.");
    expect(detailMessage(422, { detail: [{ msg: "height must be a number" }] }, "fallback")).toBe("height must be a number");
    expect(detailMessage(500, { detail: "secret db detail" }, "fallback")).toBe("fallback");
    expect(detailMessage(401, { detail: "x" }, "fallback")).toBe("fallback");
    expect(detailMessage(409, null, "fallback")).toBe("fallback");
  });
  it("reads saved grocery ticks defensively", () => {
    expect(parseTicks(null)).toEqual({});
    expect(parseTicks("not json")).toEqual({});
    expect(parseTicks("[1,2]")).toEqual({});
    expect(parseTicks('{"a":true,"b":false,"c":"yes"}')).toEqual({ a: true });
    expect(groceryKey("2026-10-07T21:07:03.133898+00:00")).toBe("bubbles.grocery.2026-10-07T21:07:03");
  });
});

describe("dates and card state", () => {
  it("shifts calendar days across month ends", () => {
    expect(todayISO(new Date(2026, 9, 7))).toBe("2026-10-07");
    expect(shiftDay("2026-10-01", -1)).toBe("2026-09-30");
    expect(shiftDay("2026-12-31", 1)).toBe("2027-01-01");
  });
  it("labels the hub cards", () => {
    const base = { has_diet_plan: false, has_workout_plan: true, entries: 0, transform: null, hasTargets: true };
    expect(cardState("diet", base)).toBe("Set up");
    expect(cardState("workouts", base)).toBe("Plan ready");
    expect(cardState("calories", { ...base, entries: 2 })).toBe("Active");
    expect(cardState("transform", { ...base, transform: { status: "active" } })).toBe("Active");
    expect(cardState("transform", { ...base, transform: { status: "paused" } })).toBe("Plan ready");
  });
});

import { whyForMeal } from "./fitness-calc";

describe("why text", () => {
  it("explains from tags, skips judgemental ones, and sizes the meal", () => {
    const why = whyForMeal({ tags: ["fried", "lowgi", "highprotein", "iron"], target_kcal: 408, label: "Breakfast" });
    expect(why).toMatch(/Slow-release/);
    expect(why).toMatch(/Protein-rich/);
    expect(why).not.toMatch(/fried|bad|cheat/i);
    expect(why).toMatch(/408 kcal for your breakfast/);
    expect(whyForMeal({})).toBe("");
  });
});

import { foodAddText, sumMicros } from "./fitness-calc";

describe("calorie log helpers", () => {
  it("adds micros across entries and ignores items without data", () => {
    const item = (micros?: Record<string, number>) => ({ food: "x", quantity: 1, unit: "g", grams: 1, kcal: 1, kcal_low: 1, kcal_high: 1, protein_g: 0, carbs_g: 0, fat_g: 0, fibre_g: 0, micros });
    const e = (items: ReturnType<typeof item>[]) => ({ id: "a", ts: "", meal: null, text: "", unrecognised: [], items, totals: { kcal: 0, kcal_low: 0, kcal_high: 0, protein_g: 0, carbs_g: 0, fat_g: 0, fibre_g: 0 } });
    expect(sumMicros([e([item({ iron_mg: 2.1 }), item()]), e([item({ iron_mg: 1.2, calcium_mg: 20 })])])).toEqual({ iron_mg: 3.3, calcium_mg: 20 });
    expect(sumMicros([])).toEqual({});
  });
  it("words search additions so the parser reads them back", () => {
    expect(foodAddText({ name: "paneer", category: "protein", serving_g: 100 })).toBe("100 g paneer");
    expect(foodAddText({ name: "amma's laddoo", category: "custom", serving_g: 40 })).toBe("1 amma's laddoo");
  });
});

import { proteinHint, slotToMeal } from "./fitness-calc";

describe("diet plan helpers", () => {
  it("maps plan slots to the meal names the food log accepts", () => {
    expect(slotToMeal("Breakfast")).toBe("breakfast");
    expect(slotToMeal("Lunch")).toBe("lunch");
    expect(slotToMeal("Dinner")).toBe("dinner");
    expect(slotToMeal("Evening snack")).toBe("snack");
  });
  it("keeps protein ideas inside the diet style", () => {
    expect(proteinHint("vegan")).not.toMatch(/egg|paneer|curd|chicken|fish/);
    expect(proteinHint("vegetarian")).not.toMatch(/egg|chicken|fish/);
    expect(proteinHint("")).toMatch(/eggs/);
  });
});
