// Pure helpers for the Fitness section: units, ranges, ring and chart geometry, meal text, error text.
// No React, no fetch. Every rule here is unit-tested in fitness-calc.test.ts.

import type { FoodEntry, FoodItem, Eaten } from "./fitness-types";

/* ── Units (the API always receives metric) ─────────────────────────── */

export const LB_PER_KG = 2.2046226218;
export type Units = "metric" | "imperial";

const round1 = (n: number) => Math.round(n * 10) / 10;

export const kgToLb = (kg: number) => round1(kg * LB_PER_KG);
export const lbToKg = (lb: number) => Math.round((lb / LB_PER_KG) * 100) / 100;

export function cmToFtIn(cm: number): { ft: number; inch: number } {
  const totalIn = Math.round(cm / 2.54);
  return { ft: Math.floor(totalIn / 12), inch: totalIn % 12 };
}
export const ftInToCm = (ft: number, inch: number) => round1((ft * 12 + inch) * 2.54);

/** Value typed in the user's units -> kg. NaN for anything that is not a number. */
export function weightToKg(value: string, units: Units): number {
  const n = Number(value.trim());
  if (value.trim() === "" || !Number.isFinite(n)) return NaN;
  return units === "imperial" ? lbToKg(n) : round1(n);
}

export function weightFromKg(kg: number | null | undefined, units: Units): string {
  if (kg == null || !Number.isFinite(kg)) return "";
  return String(units === "imperial" ? kgToLb(kg) : round1(kg));
}

export function formatWeight(kg: number | null | undefined, units: Units): string {
  if (kg == null || !Number.isFinite(kg)) return "—";
  return units === "imperial" ? `${kgToLb(kg)} lb` : `${round1(kg)} kg`;
}

export function formatRate(kgPerWeek: number | null | undefined, units: Units): string {
  if (kgPerWeek == null || !Number.isFinite(kgPerWeek)) return "Not enough weigh-ins yet";
  const v = units === "imperial" ? kgPerWeek * LB_PER_KG : kgPerWeek;
  const unit = units === "imperial" ? "lb" : "kg";
  const sign = v > 0.005 ? "+" : v < -0.005 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(2)} ${unit} a week`;
}

/* ── Numbers shown to people ────────────────────────────────────────── */

export const fmt = (n: number | null | undefined) => (n == null || !Number.isFinite(n) ? "—" : Math.round(n).toLocaleString("en-US"));

/** "1,300–1,900 kcal"; a single number if the range collapses. */
export function formatRange(low: number, high: number, unit = "kcal"): string {
  const a = Math.round(Math.min(low, high));
  const b = Math.round(Math.max(low, high));
  const body = a === b ? fmt(a) : `${fmt(a)}–${fmt(b)}`;
  return unit ? `${body} ${unit}` : body;
}

/** Fraction of the daily budget eaten, 0..1 (never more: the ring is not an alarm). */
export function ringFraction(eaten: number, budget: number): number {
  if (!(budget > 0) || !(eaten > 0)) return 0;
  return Math.min(1, eaten / budget);
}

/** A calm word for where the day is. Over budget is information, not a warning. */
export function ringWord(eaten: number, budget: number): string {
  if (!(budget > 0)) return "No target yet";
  if (eaten <= 0) return "Nothing logged yet";
  const left = budget - eaten;
  if (left >= 0) return `About ${fmt(left)} kcal left`;
  return `About ${fmt(-left)} kcal past today's estimate`;
}

export interface MacroRow { key: "protein" | "carbs" | "fat" | "fibre"; label: string; eaten: number; target: number; pct: number }

export function macroRows(eaten: Pick<Eaten, "protein_g" | "carbs_g" | "fat_g" | "fibre_g">, target: { protein_g: number; carbs_g: number; fat_g: number; fibre_g: number } | null): MacroRow[] {
  const rows: Array<[MacroRow["key"], string, number, number]> = [
    ["protein", "Protein", eaten.protein_g, target?.protein_g ?? 0],
    ["carbs", "Carbs", eaten.carbs_g, target?.carbs_g ?? 0],
    ["fat", "Fat", eaten.fat_g, target?.fat_g ?? 0],
    ["fibre", "Fibre", eaten.fibre_g, target?.fibre_g ?? 0],
  ];
  return rows.map(([key, label, e, t]) => ({ key, label, eaten: round1(e), target: Math.round(t), pct: t > 0 ? Math.min(100, Math.round((e / t) * 100)) : 0 }));
}

/* ── Strict-mode pace ───────────────────────────────────────────────── */

export const PACE_MIN = 0.25;
export const PACE_MAX = 0.75;
export const PACE_DEFAULT = 0.5;

export const clampPace = (pct: number) => (Number.isFinite(pct) ? Math.min(PACE_MAX, Math.max(PACE_MIN, Math.round(pct * 20) / 20)) : PACE_DEFAULT);

export const paceKgPerWeek = (weightKg: number, pct: number) => Math.round(weightKg * (clampPace(pct) / 100) * 100) / 100;

/** Indicative weeks to goal as a RANGE (real progress is slower than the plan on a bad week). Null when there is no gap. */
export function paceWeeksRange(gapKg: number, weightKg: number, pct: number): [number, number] | null {
  const rate = paceKgPerWeek(weightKg, pct);
  if (!(gapKg > 0) || !(rate > 0)) return null;
  return [Math.max(1, Math.round(gapKg / rate)), Math.max(2, Math.round(gapKg / (rate * 0.65)))];
}

export function formatWeeks(low: number, high: number): string {
  return low === high ? `about ${low} weeks` : `typically ${low} to ${high} weeks`;
}

/* ── Meals ──────────────────────────────────────────────────────────── */

/** Text the food-log endpoint can parse back: "225 g sprouts, 40 g oats". */
export function mealItemsText(items: Pick<FoodItem, "food" | "grams">[]): string {
  return items.filter((i) => i.food && i.grams > 0).map((i) => `${Math.round(i.grams)} g ${i.food}`).join(", ");
}

export const MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "other"] as const;

export function groupByMeal(entries: FoodEntry[]): { meal: string; entries: FoodEntry[]; kcal: number }[] {
  const buckets = new Map<string, FoodEntry[]>();
  for (const e of entries) {
    const key = (MEAL_ORDER as readonly string[]).includes(e.meal ?? "") ? (e.meal as string) : "other";
    buckets.set(key, [...(buckets.get(key) ?? []), e]);
  }
  return MEAL_ORDER.filter((m) => buckets.has(m)).map((meal) => {
    const list = buckets.get(meal) ?? [];
    return { meal, entries: list, kcal: list.reduce((s, e) => s + (e.totals?.kcal ?? 0), 0) };
  });
}

/** Micronutrient names the API sends -> friendly names + foods that are good sources (food only, never supplements). */
const MICRO_FOODS: Record<string, { label: string; foods: string }> = {
  iron_mg: { label: "Iron", foods: "rajma, chana, spinach, jaggery, sesame" },
  calcium_mg: { label: "Calcium", foods: "curd, milk or fortified plant milk, ragi, paneer, tofu" },
  folate_ug: { label: "Folate", foods: "dals, leafy greens, sprouts, oranges" },
  b12_ug: { label: "Vitamin B12", foods: "eggs, dairy, or fortified foods if you eat no animal foods" },
};
const MICRO_DAILY: Record<string, number> = { iron_mg: 15, calcium_mg: 1000, folate_ug: 300, b12_ug: 2.4 };

/** Gaps against rough daily reference amounts; only nutrients Bubbles actually measured. Food suggestions only. */
export function microGaps(micros: Record<string, number> | undefined): { label: string; foods: string }[] {
  if (!micros) return [];
  return Object.keys(MICRO_FOODS)
    .filter((k) => k in micros && micros[k] < MICRO_DAILY[k] * 0.5)
    .map((k) => MICRO_FOODS[k]);
}

/* ── Weight chart geometry ──────────────────────────────────────────── */

export interface ChartPoint { x: number; y: number; date: string; raw: number | null; trend: number | null }
export interface ChartModel { points: ChartPoint[]; rawPath: string; trendPath: string; yMin: number; yMax: number; ticks: { y: number; label: number }[]; xTicks: { x: number; date: string }[] }

const ts = (d: string) => new Date(`${d.slice(0, 10)}T00:00:00Z`).getTime();

/** Scales raw weigh-ins and the smoothed trend into SVG coordinates. */
export function chartModel(
  raw: { date: string; weight_kg: number }[],
  trend: { date: string; trend_kg: number }[],
  width: number,
  height: number,
  pad = { l: 44, r: 12, t: 12, b: 28 },
  units: Units = "metric",
): ChartModel {
  const conv = (kg: number) => (units === "imperial" ? kgToLb(kg) : kg);
  const dates = Array.from(new Set([...raw.map((r) => r.date.slice(0, 10)), ...trend.map((t) => t.date.slice(0, 10))])).sort();
  if (dates.length === 0) return { points: [], rawPath: "", trendPath: "", yMin: 0, yMax: 0, ticks: [], xTicks: [] };
  const rawBy = new Map(raw.map((r) => [r.date.slice(0, 10), conv(r.weight_kg)]));
  const trendBy = new Map(trend.map((t) => [t.date.slice(0, 10), conv(t.trend_kg)]));
  const values = [...rawBy.values(), ...trendBy.values()];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = Math.max(hi - lo, units === "imperial" ? 2 : 1);
  const yMin = lo - span * 0.15;
  const yMax = hi + span * 0.15;
  const t0 = ts(dates[0]);
  const t1 = ts(dates[dates.length - 1]);
  const w = width - pad.l - pad.r;
  const h = height - pad.t - pad.b;
  const x = (d: string) => pad.l + (t1 === t0 ? w / 2 : ((ts(d) - t0) / (t1 - t0)) * w);
  const y = (v: number) => pad.t + h - ((v - yMin) / (yMax - yMin)) * h;
  const points: ChartPoint[] = dates.map((d) => ({ x: x(d), y: y(rawBy.get(d) ?? trendBy.get(d) ?? lo), date: d, raw: rawBy.get(d) ?? null, trend: trendBy.get(d) ?? null }));
  const path = (vals: Map<string, number>) => dates.filter((d) => vals.has(d)).map((d, i) => `${i === 0 ? "M" : "L"}${x(d).toFixed(1)} ${y(vals.get(d) as number).toFixed(1)}`).join(" ");
  const ticks = [0, 1, 2, 3].map((i) => {
    const v = yMin + ((yMax - yMin) * i) / 3;
    return { y: y(v), label: Math.round(v * 10) / 10 };
  });
  const xTicks = [dates[0], dates[Math.floor((dates.length - 1) / 2)], dates[dates.length - 1]].filter((d, i, a) => a.indexOf(d) === i).map((d) => ({ x: x(d), date: d }));
  return { points, rawPath: path(rawBy), trendPath: path(trendBy), yMin, yMax, ticks, xTicks };
}

/** One plain sentence describing the chart for screen readers and the text summary. */
export function chartSummary(raw: { date: string; weight_kg: number }[], trend: { trend_kg: number }[], units: Units = "metric"): string {
  if (raw.length === 0) return "No weigh-ins yet.";
  const first = raw[0];
  const last = raw[raw.length - 1];
  if (raw.length === 1) return `One weigh-in so far: ${formatWeight(last.weight_kg, units)}.`;
  const t = trend.length ? trend[trend.length - 1].trend_kg : last.weight_kg;
  const diff = t - first.weight_kg;
  const dir = Math.abs(diff) < 0.2 ? "about the same as" : diff < 0 ? "lower than" : "higher than";
  return `${raw.length} weigh-ins from ${first.date.slice(0, 10)} to ${last.date.slice(0, 10)}. The smoothed trend is ${formatWeight(t, units)}, ${dir} your first weigh-in of ${formatWeight(first.weight_kg, units)}. Single days move up and down; the trend is what matters.`;
}

/* ── Errors ─────────────────────────────────────────────────────────── */

/**
 * The server's own sentence for a rejected request. fetchBubbles' general classifier turns every 403 into "session expired",
 * but the Fitness routes use 403 for "not available for you" with a kind explanation in `detail`, so read `detail` first.
 */
export function detailMessage(status: number, body: unknown, fallback: string): string {
  if (status === 401 || status >= 500) return fallback;
  const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => (d && typeof d === "object" && typeof (d as { msg?: unknown }).msg === "string" ? (d as { msg: string }).msg : "")).filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

/* ── Grocery ticks ──────────────────────────────────────────────────── */

export const groceryKey = (created: string | undefined) => `bubbles.grocery.${(created ?? "plan").slice(0, 19)}`;

export function parseTicks(raw: string | null): Record<string, boolean> {
  if (!raw) return {};
  try {
    const v: unknown = JSON.parse(raw);
    if (!v || typeof v !== "object" || Array.isArray(v)) return {};
    return Object.fromEntries(Object.entries(v as Record<string, unknown>).filter(([, x]) => x === true).map(([k]) => [k, true as boolean]));
  } catch {
    return {};
  }
}

/* ── Dates (local calendar day, matching app/lib/dates.ts conventions) ─ */

export function todayISO(now = new Date()): string {
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${m}-${d}`;
}

export function shiftDay(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return todayISO(new Date(y, m - 1, d + delta));
}

/* ── Review banner state ────────────────────────────────────────────── */

export const reviewPending = (review: { reviewed?: boolean } | null | undefined) => review?.reviewed === false;

/** Plan state word for the four big cards on the hub. */
export function cardState(kind: "diet" | "workouts" | "calories" | "transform", s: { has_diet_plan: boolean; has_workout_plan: boolean; entries: number; transform: { status: string } | null; hasTargets: boolean }): "Set up" | "Plan ready" | "Active" {
  if (kind === "diet") return s.has_diet_plan ? "Plan ready" : "Set up";
  if (kind === "workouts") return s.has_workout_plan ? "Plan ready" : "Set up";
  if (kind === "calories") return s.entries > 0 ? "Active" : s.hasTargets ? "Plan ready" : "Set up";
  return s.transform?.status === "active" ? "Active" : s.transform ? "Plan ready" : "Set up";
}

/* ── Plain-language "why" for a planned meal (derived from tags; never moralises food) ─ */

const WHY: Record<string, string> = {
  lowgi: "Slow-release carbs help keep your energy steady.",
  highprotein: "Protein-rich, so it keeps you fuller for longer.",
  iron: "Includes iron-rich foods. A squeeze of lemon alongside helps your body use it.",
  light: "A lighter meal that sits easily.",
};

export function whyForMeal(meal: { tags?: string[]; target_kcal?: number; label?: string }): string {
  const parts = (meal.tags ?? []).map((t) => WHY[t]).filter(Boolean);
  const size = meal.target_kcal ? `Sized to about ${Math.round(meal.target_kcal)} kcal for your ${(meal.label ?? "meal").toLowerCase()}.` : "";
  return [...parts.slice(0, 2), size].filter(Boolean).join(" ");
}

/** Adds up per-item micronutrients across the day's entries (items without micro data contribute nothing). */
export function sumMicros(entries: FoodEntry[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of entries) for (const i of e.items ?? []) for (const [k, v] of Object.entries(i.micros ?? {})) if (typeof v === "number") out[k] = Math.round(((out[k] ?? 0) + v) * 10) / 10;
  return out;
}

/** The text appended to the meal box when a search result is added. Custom foods are counted in servings. */
export function foodAddText(f: { name: string; category?: string; serving_g: number }): string {
  return f.category === "custom" ? `1 ${f.name}` : `${Math.round(f.serving_g)} g ${f.name}`;
}

/** Plan slots are breakfast / main1 / snack / main2; the food log only knows breakfast, lunch, dinner, snack. */
export function slotToMeal(label: string): "breakfast" | "lunch" | "dinner" | "snack" {
  const l = label.toLowerCase();
  return l.includes("breakfast") ? "breakfast" : l.includes("lunch") ? "lunch" : l.includes("dinner") ? "dinner" : "snack";
}

/** Food-only ideas for a protein-light day, matched to the diet style (never a supplement). */
export function proteinHint(dietStyle: string | undefined): string {
  const s = (dietStyle ?? "").toLowerCase();
  if (s === "vegan") return "dal, chana, rajma, tofu, soya chunks, sprouts or nuts";
  if (s === "jain") return "dal, chana, rajma, curd, paneer or sprouts";
  if (s === "vegetarian") return "curd, paneer, dal, chana, rajma or sprouts";
  return "eggs, fish, chicken, curd, paneer, dal or sprouts";
}
